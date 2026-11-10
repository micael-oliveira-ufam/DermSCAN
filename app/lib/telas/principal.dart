import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../classificador.dart';
import '../marca/simbolo.dart';
import 'sobre.dart';

class TelaPrincipal extends StatefulWidget {
  const TelaPrincipal({super.key, required this.modelo});
  final Future<Classificador> modelo;

  @override
  State<TelaPrincipal> createState() => _TelaPrincipalState();
}

class _TelaPrincipalState extends State<TelaPrincipal> {
  Classificador? _classificador;
  Uint8List? _imagem;
  Resultado? _resultado;
  String? _erro;
  bool _processando = false;

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
              'Uso restrito à pesquisa. A imagem é processada somente neste aparelho. '
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
      ],
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
