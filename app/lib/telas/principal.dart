import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../classificador.dart';
import '../clinico/armazenamento.dart';
import '../clinico/dados_clinicos.dart';
import '../clinico/indicador.dart';
import '../marca/simbolo.dart';
import 'clinico.dart';
import 'sobre.dart';

class TelaPrincipal extends StatefulWidget {
  const TelaPrincipal({super.key, required this.modelo, this.armazenamento});
  final Future<Classificador> modelo;

  /// Armazenamento dos dados clínicos. Padrão: arquivo criptografado no aparelho.
  final ArmazenamentoClinico? armazenamento;

  @override
  State<TelaPrincipal> createState() => _TelaPrincipalState();
}

class _TelaPrincipalState extends State<TelaPrincipal> {
  Classificador? _classificador;
  Uint8List? _imagem;
  Resultado? _resultado;
  String? _erro;
  bool _processando = false;

  late final ArmazenamentoClinico _arm = widget.armazenamento ?? ArmazenamentoCriptografado();
  RegistroClinico _registro = const RegistroClinico();
  String? _avisoClinico;

  @override
  void initState() {
    super.initState();
    _carregarRegistro();
  }

  Future<void> _carregarRegistro() async {
    try {
      final r = await _arm.carregar();
      if (mounted) setState(() => _registro = r);
    } on ArmazenamentoCorrompido {
      // Arquivo adulterado ou chave perdida: nada é usado; o usuário pode apagar e recomeçar.
      if (mounted) {
        setState(() {
          _registro = const RegistroClinico();
          _avisoClinico = 'Os dados clínicos salvos estão ilegíveis ou foram adulterados e não foram usados. Abra o formulário e use "Apagar dados e chave" para recomeçar.';
        });
      }
    } catch (_) {
      if (mounted) setState(() => _avisoClinico = 'Não foi possível acessar o armazenamento seguro neste aparelho.');
    }
  }

  Future<void> _abrirClinico() async {
    var registro = _registro;
    if (!registro.consentido) {
      final aceitou = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => const TelaConsentimentoClinico()));
      if (aceitou != true || !mounted) return;
      registro = RegistroClinico(consentido: true, dados: registro.dados);
      try {
        await _arm.salvar(registro);
      } catch (_) {
        if (mounted) setState(() => _avisoClinico = 'Não foi possível salvar com criptografia neste aparelho; nada foi registrado.');
        return;
      }
      if (mounted) setState(() => _registro = registro);
    }
    if (!mounted) return;
    final resp = await Navigator.of(context).push<RespostaFormulario>(
      MaterialPageRoute(builder: (_) => TelaFormularioClinico(inicial: registro.dados ?? const DadosClinicos())),
    );
    if (resp == null || !mounted) return;
    try {
      if (resp.apagar) {
        await _arm.apagarTudo();
        setState(() {
          _registro = const RegistroClinico();
          _avisoClinico = null;
        });
      } else {
        final novo = RegistroClinico(consentido: true, dados: resp.dados);
        await _arm.salvar(novo);
        setState(() {
          _registro = novo;
          _avisoClinico = null;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _avisoClinico = 'Não foi possível salvar com criptografia neste aparelho; nada foi registrado.');
    }
  }

  @override
  void dispose() {
    _classificador?.liberar();
    super.dispose();
  }

  Future<void> _escolher(ImageSource origem) async {
    final arquivo = await ImagePicker().pickImage(source: origem);
    if (arquivo == null || _classificador == null) return;
    setState(() {
      _processando = true;
      _erro = null;
      _resultado = null;
    });
    try {
      final bytes = await arquivo.readAsBytes();
      final resultado = await _classificador!.classificar(bytes);
      setState(() {
        _imagem = bytes;
        _resultado = resultado;
      });
    } catch (e) {
      setState(() => _erro = 'Não foi possível classificar esta imagem: $e');
    } finally {
      setState(() => _processando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final escuro = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(children: [
          Simbolo(tamanho: 30, escuro: escuro),
          const SizedBox(width: 10),
          Nome(tamanho: 22, escuro: escuro),
        ]),
        actions: [
          IconButton(
            tooltip: 'Sobre o DermSCAN',
            icon: const Icon(Icons.info_outline),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const TelaSobre())),
          ),
        ],
      ),
      body: FutureBuilder<Classificador>(
        future: widget.modelo,
        builder: (context, snap) {
          if (snap.hasError) {
            return Center(
              child: Padding(padding: const EdgeInsets.all(16), child: Text('Falha ao carregar o modelo: ${snap.error}')),
            );
          }
          if (!snap.hasData) {
            return const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('Carregando modelo…'),
            ]));
          }
          _classificador ??= snap.data;
          return _conteudo(context, snap.data!);
        },
      ),
    );
  }

  Widget _conteudo(BuildContext context, Classificador c) {
    final tema = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          color: tema.colorScheme.tertiaryContainer,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Text(
              'Uso restrito à pesquisa. A imagem e os dados clínicos opcionais ficam somente neste aparelho. '
              'O resultado não é diagnóstico nem substitui avaliação médica ou laboratorial.',
              style: tema.textTheme.bodyMedium?.copyWith(color: tema.colorScheme.onTertiaryContainer),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: _processando ? null : () => _escolher(ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: const Text('Galeria'),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: FilledButton.tonalIcon(
              onPressed: _processando ? null : () => _escolher(ImageSource.camera),
              icon: const Icon(Icons.photo_camera),
              label: const Text('Câmera'),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        _cartaoClinico(tema),
        if (_processando) ...[const SizedBox(height: 16), const LinearProgressIndicator()],
        if (_erro != null) ...[
          const SizedBox(height: 16),
          Text(_erro!, style: TextStyle(color: tema.colorScheme.error)),
        ],
        if (_imagem != null) ...[
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.memory(_imagem!, height: 260, fit: BoxFit.contain),
          ),
        ],
        if (_resultado != null) ...[
          const SizedBox(height: 16),
          _cartaoResultado(tema, c.info, _resultado!),
        ],
        if (_registro.dados != null && !_registro.dados!.vazio) ...[
          const SizedBox(height: 16),
          _cartaoIndicador(tema, _registro.dados!, _resultado),
        ],
      ],
    );
  }

  Widget _cartaoClinico(ThemeData tema) {
    final d = _registro.dados;
    final tem = d != null && !d.vazio;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.lock_outline, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text('Dados clínicos (opcional)', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
          ]),
          const SizedBox(height: 6),
          Text(
            tem
                ? 'Dados salvos neste aparelho, criptografados. Nada é enviado.'
                : 'Registre dados clínicos e epidemiológicos para ver um indicador de suspeita por regras do Ministério da Saúde. Ficam só neste aparelho, criptografados.',
            style: tema.textTheme.bodySmall,
          ),
          if (_avisoClinico != null) ...[
            const SizedBox(height: 6),
            Text(_avisoClinico!, style: tema.textTheme.bodySmall?.copyWith(color: tema.colorScheme.error)),
          ],
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _abrirClinico,
            icon: Icon(tem ? Icons.edit_outlined : Icons.assignment_outlined),
            label: Text(tem ? 'Editar dados clínicos' : 'Registrar dados clínicos'),
          ),
        ]),
      ),
    );
  }

  Widget _cartaoIndicador(ThemeData tema, DadosClinicos d, Resultado? r) {
    final ind = avaliarIndicador(d);
    IconData icone(Estado e) => switch (e) {
          Estado.atendido => Icons.check_circle,
          Estado.naoAtendido => Icons.cancel_outlined,
          Estado.semInformacao => Icons.help_outline,
        };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Indicador clínico-epidemiológico', style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text(ind.titulo, style: tema.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          for (final c in ind.criterios)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(icone(c.estado), size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text(c.texto, style: tema.textTheme.bodyMedium)),
              ]),
            ),
          for (final a in ind.apoio) ...[
            const SizedBox(height: 4),
            Text('• $a', style: tema.textTheme.bodySmall),
          ],
          for (final a in ind.alertas) ...[
            const SizedBox(height: 4),
            Text('Atenção: $a', style: tema.textTheme.bodySmall?.copyWith(color: tema.colorScheme.onTertiaryContainer)),
          ],
          if (r != null) ...[
            const SizedBox(height: 12),
            Text('Imagem (IA) × dados clínicos', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(compararComIa(ind, r), style: tema.textTheme.bodyMedium),
          ],
          const SizedBox(height: 12),
          Text(
            'Regras da definição de caso suspeito do $fonteManual. Não é probabilidade de doença nem escore validado, '
            'e não altera o resultado da IA. Não substitui avaliação médica ou exame laboratorial.',
            style: tema.textTheme.bodySmall,
          ),
        ]),
      ),
    );
  }

  Widget _cartaoResultado(ThemeData tema, ModeloInfo info, Resultado r) {
    final limiar = (info.limiarInconclusivo * 100).toStringAsFixed(0);
    final topo = r.principal;
    final pct = (topo.probabilidade * 100).toStringAsFixed(1);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Resultado', style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
              r.inconclusivo
                  ? 'Inconclusivo: a maior probabilidade é ${topo.nome} ($pct%), abaixo do limiar de $limiar%.'
                  : 'Classe mais provável: ${topo.nome} ($pct%).',
              style: tema.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            for (final item in r.ranking) ...[
              Text('${item.nome}: ${(item.probabilidade * 100).toStringAsFixed(1)}%'),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(value: item.probabilidade, minHeight: 8),
              ),
              const SizedBox(height: 10),
            ],
            Text(
              'Tempo de inferência: ${r.milissegundos} ms. Temperatura de calibração: '
              '${info.temperatura.toStringAsFixed(3)} (ajustada na validação).',
              style: tema.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
