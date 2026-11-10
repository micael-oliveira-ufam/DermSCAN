# DermSCAN (app Android, Flutter)

Classifica uma foto de lesão cutânea no próprio aparelho com o mesmo modelo do site (ViT-B/16 int8, ONNX). Sem servidor.
Ferramenta de apoio à pesquisa; não é diagnóstico. Licenças e atribuições: `../NOTICE.md`.

## Estrutura
- `lib/main.dart`: tema da marca (claro e escuro), fluxo splash → tela principal; o modelo começa a carregar já na splash.
- `lib/telas/splash.dart`: splash animada (~2,2 s; respeita "reduzir animações").
- `lib/telas/principal.dart`, `lib/telas/sobre.dart`: interface e tela "Sobre" (limitações e créditos).
- `lib/marca/`: cores e símbolo desenhado em Dart, com a mesma geometria de `../brand/gerar_marca.py`.
- `lib/preprocessamento.dart`, `lib/classificador.dart`: pipeline idêntico ao do site (ver `assets/model/modelo_info.json`).
- `assets/brand/`: PNGs da marca usados para ícone e splash nativa. `assets/fonts/`: Sora (OFL 1.1).
- `assets/model/`: **gerado** por `../tools/sync_model.sh` (a única cópia versionada do modelo fica em `../docs/model/`).

## Compilar
Requisitos: Flutter 3.47.x (Dart 3.13), Android SDK 36, JDK 17+.
```bash
../tools/sync_model.sh
flutter pub get
flutter analyze && flutter test
flutter build apk --release
```
Ícones e splash nativa foram gerados com `dart run flutter_launcher_icons` e `dart run flutter_native_splash:create`
(configuração no `pubspec.yaml`); só precisam ser repetidos se os PNGs da marca mudarem.

## Observações
- `android/build.gradle.kts` eleva o `compileSdk` das bibliotecas para 36 (o plugin onnxruntime 1.4.1 compila contra 33; só compilação).
- O release usa a chave de depuração do Flutter. Para a Play Store, configure um keystore próprio.
- **Inferência não testada em aparelho ou emulador.** Os testes cobrem pré-processamento e splash.
