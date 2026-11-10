import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:dermscan/preprocessamento.dart';

const _media = [0.485, 0.456, 0.406];
const _desvio = [0.229, 0.224, 0.225];

void main() {
  test('pesos de cada pixel de saída somam 1 (redução e ampliação)', () {
    // Redução 300 -> 224 e ampliação 50 -> 224 exercitam os dois ramos do filtro.
    for (final par in [[300, 224], [50, 224]]) {
      final src = Uint8List.fromList(List.filled(par[0] * 3, 120));
      final out = reamostrarPIL(src, par[0], 1, par[1], 1);
      expect(out.length, par[1] * 3);
      // Entrada constante: a saída também deve ser constante e igual ao valor original.
      expect(out.every((v) => v == 120), isTrue, reason: 'entrada ${par[0]}->${par[1]}');
    }
  });

  test('imagem uniforme mantém a cor após reamostragem', () {
    final src = Uint8List(40 * 30 * 3);
    for (var i = 0; i < src.length; i += 3) {
      src[i] = 200;
      src[i + 1] = 100;
      src[i + 2] = 50;
    }
    final out = reamostrarPIL(src, 40, 30, 224, 224);
    for (var i = 0; i < out.length; i += 3) {
      expect(out[i], 200);
      expect(out[i + 1], 100);
      expect(out[i + 2], 50);
    }
  });

  test('tensor CHW tem o tamanho certo e normalização correta para cor uniforme', () {
    final imagem = img.Image(width: 64, height: 48);
    img.fill(imagem, color: img.ColorRgb8(128, 64, 255));
    final bytes = Uint8List.fromList(img.encodePng(imagem));

    final t = preprocessarBytes(bytes, media: _media, desvio: _desvio, tamanho: 224);
    expect(t.length, 3 * 224 * 224);

    final n = 224 * 224;
    final esperado = [
      (128 / 255 - _media[0]) / _desvio[0],
      (64 / 255 - _media[1]) / _desvio[1],
      (255 / 255 - _media[2]) / _desvio[2],
    ];
    // PNG é sem perdas, então os valores devem ser exatos (salvo arredondamento float32).
    for (var c = 0; c < 3; c++) {
      expect(t[c * n], closeTo(esperado[c], 1e-5), reason: 'canal $c, pixel 0');
      expect(t[c * n + n - 1], closeTo(esperado[c], 1e-5), reason: 'canal $c, último pixel');
    }
  });

  test('formato inválido gera FormatException', () {
    expect(
      () => preprocessarBytes(Uint8List.fromList([1, 2, 3]), media: _media, desvio: _desvio, tamanho: 224),
      throwsA(isA<FormatException>()),
    );
  });
}
