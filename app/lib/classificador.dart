// Carrega o modelo ONNX (int8) dos assets e classifica imagens localmente, sem servidor.
// Usa o plugin onnxruntime (1.4.1), cuja API foi conferida no código-fonte do pacote.

import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:onnxruntime/onnxruntime.dart';

import 'preprocessamento.dart';

class ModeloInfo {
  ModeloInfo({
    required this.arquivo,
    required this.nomeEntrada,
    required this.tamanho,
    required this.media,
    required this.desvio,
    required this.classes,
    required this.nomesExibicao,
    required this.temperatura,
    required this.limiarInconclusivo,
    required this.aviso,
  });

  final String arquivo;
  final String nomeEntrada;
  final int tamanho;
  final List<double> media;
  final List<double> desvio;
  final List<String> classes;
  final Map<String, String> nomesExibicao;
  final double temperatura;
  final double limiarInconclusivo;
  final String aviso;

  factory ModeloInfo.fromJson(Map<String, dynamic> j) {
    final entrada = j['entrada'] as Map<String, dynamic>;
    return ModeloInfo(
      arquivo: j['arquivo'] as String,
      nomeEntrada: entrada['nome'] as String,
      tamanho: (entrada['tamanho'] as num).toInt(),
      media: (entrada['media'] as List).map((e) => (e as num).toDouble()).toList(),
      desvio: (entrada['desvio'] as List).map((e) => (e as num).toDouble()).toList(),
      classes: (j['classes'] as List).cast<String>(),
      nomesExibicao: (j['nomes_exibicao'] as Map<String, dynamic>).cast<String, String>(),
      temperatura: ((j['calibracao'] as Map<String, dynamic>)['temperatura'] as num).toDouble(),
      limiarInconclusivo: (j['limiar_inconclusivo'] as num).toDouble(),
      aviso: j['aviso'] as String,
    );
  }
}

class ItemRanking {
  const ItemRanking(this.classe, this.nome, this.probabilidade);
  final String classe;
  final String nome;
  final double probabilidade;
}

class Resultado {
  const Resultado({
    required this.ranking,
    required this.inconclusivo,
    required this.milissegundos,
  });
  final List<ItemRanking> ranking;
  final bool inconclusivo;
  final int milissegundos;

  ItemRanking get principal => ranking.first;
}

List<double> softmaxComTemperatura(List<double> logits, double temperatura) {
  final z = logits.map((v) => v / temperatura).toList();
  final m = z.reduce(math.max);
  final e = z.map((v) => math.exp(v - m)).toList();
  final soma = e.reduce((a, b) => a + b);
  return e.map((v) => v / soma).toList();
}

class _PedidoPreprocessamento {
  const _PedidoPreprocessamento(this.bytes, this.media, this.desvio, this.tamanho);
  final Uint8List bytes;
  final List<double> media;
  final List<double> desvio;
  final int tamanho;
}

Float32List _preprocessarEmIsolado(_PedidoPreprocessamento p) => preprocessarBytes(
      p.bytes,
      media: p.media,
      desvio: p.desvio,
      tamanho: p.tamanho,
    );

class Classificador {
  Classificador._(this.info, this._sessao, this._opcoes);

  final ModeloInfo info;
  final OrtSession _sessao;
  final OrtSessionOptions _opcoes;

  static Future<Classificador> carregar() async {
    final texto = await rootBundle.loadString('assets/model/modelo_info.json');
    final info = ModeloInfo.fromJson(jsonDecode(texto) as Map<String, dynamic>);
    final bytes = (await rootBundle.load('assets/model/${info.arquivo}')).buffer.asUint8List();

    OrtEnv.instance.init();
    final opcoes = OrtSessionOptions()
      ..setIntraOpNumThreads(2)
      ..setSessionGraphOptimizationLevel(GraphOptimizationLevel.ortEnableAll);
    final sessao = OrtSession.fromBuffer(bytes, opcoes);
    return Classificador._(info, sessao, opcoes);
  }

  Future<Resultado> classificar(Uint8List imagem) async {
    final dados = await compute(
      _preprocessarEmIsolado,
      _PedidoPreprocessamento(imagem, info.media, info.desvio, info.tamanho),
    );

    final entrada = OrtValueTensor.createTensorWithDataList(
      [dados],
      [1, 3, info.tamanho, info.tamanho],
    );
    final execucao = OrtRunOptions();
    final cronometro = Stopwatch()..start();
    final saidas = _sessao.run(execucao, {_sessao.inputNames.first: entrada});
    cronometro.stop();

    try {
      final valor = saidas.first!.value as List;
      final linha = (valor.first as List).map((e) => (e as num).toDouble()).toList();
      if (linha.length != info.classes.length) {
        throw StateError('Saída com ${linha.length} valores; esperado ${info.classes.length}.');
      }
      final probs = softmaxComTemperatura(linha, info.temperatura);
      final ranking = <ItemRanking>[
        for (var i = 0; i < probs.length; i++)
          ItemRanking(info.classes[i], info.nomesExibicao[info.classes[i]] ?? info.classes[i], probs[i]),
      ]..sort((a, b) => b.probabilidade.compareTo(a.probabilidade));

      return Resultado(
        ranking: ranking,
        inconclusivo: ranking.first.probabilidade < info.limiarInconclusivo,
        milissegundos: cronometro.elapsedMilliseconds,
      );
    } finally {
      entrada.release();
      execucao.release();
      for (final s in saidas) {
        s?.release();
      }
    }
  }

  void liberar() {
    _sessao.release();
    _opcoes.release();
    OrtEnv.instance.release();
  }
}
