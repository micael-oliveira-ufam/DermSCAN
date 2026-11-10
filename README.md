<p align="center"><img src="brand/png/logotipo-claro.png" alt="DermSCAN" width="360"></p>

# DermSCAN

Triagem visual de lesões cutâneas (incluindo leishmaniose) em 10 categorias, **no navegador e no Android, sem servidor**.
A imagem nunca sai do dispositivo. **Ferramenta de apoio à pesquisa; não é diagnóstico.**

- Site: https://micael-oliveira-ufam.github.io/DermSCAN/ (GitHub Pages, pasta `docs/`)
- App Android: `app/` (Flutter), com splash animada e a mesma identidade visual

## Modelo
ViT-B/16 (ImageNet) com cabeça de 10 classes, quantizado em int8 (ONNX opset 17, 87,3 MB), seed 42.

| Versão | Acurácia | Acurácia balanceada | F1 macro | ECE |
|---|---|---|---|---|
| fp32 | 0,6292 | 0,5476 | 0,5622 | 0,2092 |
| int8 (usado) | 0,6180 | 0,4976 | 0,5097 | 0,1633 |
| int8 + temperatura 1,524 | 0,6180 | 0,4976 | 0,5097 | 0,0828 |

Medido em **89 imagens de teste** de um único atlas: a incerteza é grande. **Esporotricose: 0 de 3 reconhecidas.**
Detalhes e limitações em [`documentacao/RELATORIO_VERIFICACAO.md`](documentacao/RELATORIO_VERIFICACAO.md).

Classes: carcinoma basocelular, carcinoma espinocelular, esporotricose, hanseníase, leishmaniose cutânea (úlcera),
leishmaniose cutânea (outras formas), leishmaniose mucosa, outras dermatoses, tuberculose e micobacterioses, úlceras vasculares.

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `docs/` | Site estático (GitHub Pages): HTML, JS, modelo, onnxruntime-web, fontes |
| `app/` | App Flutter (Android) |
| `brand/` | Identidade visual: gerador dos SVGs, PNGs, paleta, contraste, guia (`BRAND.md`) |
| `ml/` | Código de treino, exportação para ONNX e preparo de dados (sem dados) |
| `tools/` | `sync_model.sh`: copia o modelo de `docs/model/` para o app |
| `documentacao/` | Relatório de verificação |

## Pré-processamento (idêntico em treino, web e app)
RGB com orientação EXIF → 224×224 esticado, bilinear com antialias → /255 → normalização (média 0,485/0,456/0,406; desvio 0,229/0,224/0,225)
→ `softmax(logits / 1,524)`. Resultado abaixo de 50% é "inconclusivo" (escolha de interface, sem validação clínica).
O int8 é 5 a 8 vezes mais sensível que o fp32 a diferenças de 1 nível de cor na entrada, então não altere esse pipeline.
Especificação em `docs/model/modelo_info.json`.

## Rodar localmente
```bash
# Site
cd docs && python3 -m http.server 8000      # abra http://127.0.0.1:8000

# App (Flutter 3.47.x, Android SDK 36, JDK 17+)
./tools/sync_model.sh
cd app && flutter pub get && flutter analyze && flutter test
flutter build apk --release                 # app/build/app/outputs/flutter-apk/app-release.apk
```
O APK de release usa a chave de depuração do Flutter; para a Play Store, configure um keystore próprio.

## Identidade visual
`python3 brand/gerar_marca.py --fontes brand/fontes --saida brand` · `node brand/exportar_png.js brand` · `python3 brand/gerar_brand_md.py`
(requer `fonttools`, `brotli` e `playwright`). Ver `brand/BRAND.md`.

## Estado da verificação
- Site: no Chromium headless, classe prevista idêntica à referência em Python em **13 de 13** imagens (dif. máx. de probabilidade 0,0168).
- App: `flutter analyze` sem problemas; testes de unidade e de widget passando; APK de release compilado.
- **Inferência no Android não testada em aparelho ou emulador.**
- Ajuste de build: o plugin onnxruntime 1.4.1 compila contra Android 33; `app/android/build.gradle.kts` eleva o `compileSdk` das bibliotecas para 36.

## Licenças
Código: MIT. **Pesos do modelo: somente pesquisa e uso não comercial (CC BY-NC-SA 3.0 IGO)**, por terem sido treinados com imagens do atlas OPAS 2020, que não são distribuídas aqui. Ver [`NOTICE.md`](NOTICE.md).
