# Relatório de verificação: plataforma de classificação de lesões cutâneas

Data: 2026-11-09. Modelo: ViT-B/16 (seed 42), quantizado em int8 (dinâmico), ONNX opset 17.

## 1. Integridade do modelo e do treino

- Hash do manifesto do dataset: igual ao registrado no treino (`50839b9fb00384727f1eb8fd0e46571b91474c28ff0b032b3e4ce840d0b5aab1`).
- Métricas de teste (89 imagens) recalculadas a partir de `predictions_test.csv`: acurácia 0,6292 e F1 macro 0,5622, idênticas às do treino.
- PyTorch 2.11.0 em CPU reproduz as métricas do treino.
- ECE: 0,20918 aqui contra 0,20908 no treino. A diferença de 1e-4 vem da implementação, não do modelo.

## 2. Exportação e quantização

| Versão | Acurácia | Acurácia balanceada | F1 macro | ECE | Tamanho |
|---|---|---|---|---|---|
| fp32 (PyTorch) | 0,6292 | 0,5476 | 0,5622 | 0,2092 | 343 MB |
| fp32 (ONNX) | 0,6292 | 0,5476 | 0,5622 | 0,2092 | 343 MB |
| int8 (ONNX) | 0,6180 | 0,4976 | 0,5097 | 0,1633 | 87 MB |
| int8 + temperatura 1,524 | 0,6180 | 0,4976 | 0,5097 | 0,0828 | 87 MB |

- ONNX fp32 vs PyTorch: diferença máxima nos logits de 8e-6; classe predita igual em 100% das imagens.
- int8 muda 2 de 89 predições em relação ao fp32.
- A queda de F1 de 0,052 vem de uma única imagem da classe `carcinoma_espinocelular` (2 imagens no teste). Com n tão pequeno, é ruído, mas não deve ser lido como queda real.

### Sensibilidade do int8 a pequenas diferenças de entrada

Medido com 3 imagens de teste, com entrada modificada por diferença máxima de 0,018 no tensor normalizado (1 nível de cor):

| Imagem | Dif. máx. na entrada | Dif. máx. nos logits (int8) | Dif. máx. nos logits (fp32) | Mesma classe (int8) |
|---|---|---|---|---|
| p364_2393.jpg | 0,018 | 0,091 | 0,012 | sim |
| p371_2456.jpg | 0,018 | 0,103 | 0,025 | sim |
| p296_1847.jpg | 0,018 | 0,128 | 0,012 | sim |

**Conclusão:** o int8 é cerca de 5 a 8 vezes mais sensível a diferenças de pré-processamento do que o fp32. Por isso o pré-processamento precisa ser idêntico entre treino, web e app.

## 3. Versão web (Chromium headless, onnxruntime-web 1.24.2)

Teste com 13 imagens do conjunto de teste (uma ou duas por classe), enviadas pelo campo de arquivo da página.

- Mesma classe predita que a referência em Python: **13 de 13**.
- Acertos (contra o rótulo verdadeiro): 8 de 13, tanto na referência quanto no navegador.
- Diferença máxima de probabilidade: 0,0168 (mediana 0,0081).
- Diferença máxima de logits: 0,194 (mediana 0,117). Essa diferença é consequência da sensibilidade do int8 descrita acima.
- Tempo mediano de inferência no navegador (WASM, 1 thread, máquina de teste): 772 ms.

### Reamostragem em relação ao PIL

Mesma entrada decodificada, comparada com `Image.resize(BILINEAR)` do PIL 13.0.0:

| Imagem | Dif. máx. (níveis de cor) | Pixels diferentes |
|---|---|---|
| 1 | 1 | 12,87% |
| 2 | 1 | 9,34% |
| 3 | 1 | 16,68% |

- O decodificador JPEG do navegador é idêntico ao do PIL nas imagens testadas (diferença máxima 0).
- Uma versão em ponto fixo, que tentei primeiro, divergia em até 2 níveis em ~92% dos pixels. Por isso adotei a versão em ponto flutuante.
- A origem exata da diferença restante não foi identificada. A versão do PIL usada pode ter detalhes internos que não reproduzi.

### Aviso no console

O onnxruntime registra `Unknown CPU vendor` no Chromium headless. É um aviso de detecção de CPU, sem efeito sobre a inferência.

## 4. Versão Android (Flutter 3.47.9, Dart 3.13, onnxruntime 1.4.1)

- `flutter analyze`: sem problemas.
- `flutter test`: 4 testes passando (pesos somam 1 para redução e ampliação; imagem uniforme preservada; normalização do tensor CHW; formato inválido gera exceção).
- `flutter build apk --release`: concluído. APK de **131,8 MB**, com o modelo de 87 MB e as bibliotecas nativas.

### Ajuste de build necessário

O plugin `onnxruntime` 1.4.1 compila contra Android 33, mas duas dependências AndroidX exigem API 34 ou superior. O Gradle recusou o build com 15 problemas de metadados. A correção foi elevar o `compileSdk` das bibliotecas para 36, em `android/build.gradle.kts`, via `afterEvaluate`. Isso afeta só a compilação. O `minSdk` e o `targetSdk` não mudaram.

### Não verificado no app

- **A inferência no Android ainda não foi executada em aparelho ou emulador.** Os testes unitários cobrem o pré-processamento, mas não o carregamento do modelo nem a inferência nativa.
- A paridade app × PyTorch × navegador, nas mesmas imagens, é um passo pendente.
- O APK usa a chave de depuração do Flutter. Para publicação, é preciso um keystore próprio.

## 5. Pré-processamento (especificação única)

Definida em `web/model/modelo_info.json` e replicada em `web/app.js` e `app_flutter/lib/preprocessamento.dart`:

1. Decodificar a imagem em RGB, com orientação EXIF aplicada.
2. Redimensionar para 224×224, esticando, com reamostragem bilinear com antialias (versão em ponto flutuante).
3. Escalar para [0,1] e normalizar com média `[0,485; 0,456; 0,406]` e desvio `[0,229; 0,224; 0,225]`.
4. Calcular `softmax(logits / 1,524)`.

## 6. Pendências

1. **Licença (bloqueante para publicação).** Os pesos foram treinados com imagens CC BY-NC-SA 3.0 IGO. Não publicar o site nem distribuir o APK antes da decisão.
2. Testar a inferência no Android (aparelho ou emulador) e medir o tempo real.
3. Fechar a paridade entre PyTorch, navegador e app nas mesmas imagens.
4. Esporotricose: não foi reconhecida nas 3 imagens de teste (recall zero, nos dois modelos). Antes de publicar, decidir entre reforçar a classe, agrupá-la ou sinalizar a limitação.
5. Avaliar o int8 com calibração estática, para reduzir a sensibilidade mostrada na seção 2.
