import 'package:flutter/material.dart';

import '../marca/simbolo.dart';

class TelaSobre extends StatelessWidget {
  const TelaSobre({super.key});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final escuro = tema.brightness == Brightness.dark;
    Widget secao(String titulo, List<String> itens) => Padding(
          padding: const EdgeInsets.only(top: 20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(titulo, style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            for (final i in itens)
              Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('• $i', style: tema.textTheme.bodyMedium)),
          ]),
        );
    return Scaffold(
      appBar: AppBar(title: const Text('Sobre')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Row(children: [
            Simbolo(tamanho: 56, escuro: escuro),
            const SizedBox(width: 14),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Nome(tamanho: 30, escuro: escuro),
              Text('Versão 1.0.0', style: tema.textTheme.bodySmall),
            ]),
          ]),
          secao('O que é', const [
            'Triagem visual de lesões cutâneas, incluindo leishmaniose, em 10 categorias. Ferramenta de apoio à pesquisa; não é diagnóstico.',
            'A imagem é processada somente neste aparelho. Nenhuma foto é enviada a servidor.',
          ]),
          secao('Limitações conhecidas', const [
            'Medido em 89 imagens de teste: acurácia 61,8%, acurácia balanceada 49,8%, F1 macro 0,510. Conjunto pequeno, incerteza grande.',
            'Esporotricose: 0 de 3 imagens reconhecidas no teste.',
            'Treinado com imagens de um único atlas; desempenho em fotos de celular não foi medido.',
            'Resultado abaixo de 50% de probabilidade é marcado como inconclusivo (escolha de interface, sem validação clínica).',
          ]),
          secao('Créditos e licenças', const [
            'Dados de treino: atlas OPAS 2020, CC BY-NC-SA 3.0 IGO (uso não comercial). As imagens não são distribuídas, apenas o modelo treinado.',
            'Modelo-base: ViT-B/16 do torchvision (ImageNet).',
            'Inferência: onnxruntime (MIT).',
            'Tipografia: Sora, SIL Open Font License 1.1.',
            'Código: github.com/micael-oliveira-ufam/DermSCAN',
          ]),
        ],
      ),
    );
  }
}
