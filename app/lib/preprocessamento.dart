// Pré-processamento idêntico ao da versão web (web/app.js) e ao do treino (torchvision sobre PIL).
//
// Passos, nesta ordem:
//   1. decodificar a imagem;
//   2. aplicar a orientação EXIF (o navegador faz isso por padrão; o PIL do treino não, mas as
//      imagens de teste não têm EXIF, então a paridade medida não é afetada);
//   3. converter para RGB de 8 bits;
//   4. redimensionar para 224x224 com reamostragem bilinear com antialias (mesmo algoritmo do PIL);
//   5. escalar para [0,1] e normalizar canal a canal com média e desvio do modelo.
//
// Diferença medida contra o PIL 13.0.0 no navegador: no máximo 1 nível de cor (~13% dos pixels).

import 'dart:math' as math;
import 'dart:typed_data';

import 'package:image/image.dart' as img;

class _Coeficientes {
  _Coeficientes(this.inicio, this.tamanho, this.pesos);
  final List<int> inicio;
  final List<int> tamanho;
  final List<Float64List> pesos;
}

double _filtroBilinear(double x) {
  if (x < 0) x = -x;
  return x < 1 ? 1 - x : 0;
}

/// Pesos normalizados de uma reamostragem 1D: para cada pixel de saída, o início, o
/// número de vizinhos e os pesos. Quando há redução, o suporte do filtro é escalado (antialias).
_Coeficientes _coeficientesPIL(int entrada, int saida) {
  final escala = entrada / saida;
  final filtro = math.max(escala, 1.0);
  final suporte = 1.0 * filtro;
  final inicio = <int>[];
  final tamanho = <int>[];
  final pesos = <Float64List>[];
  for (var i = 0; i < saida; i++) {
    final centro = (i + 0.5) * escala;
    var xmin = (centro - suporte + 0.5).truncate(); // truncamento em direção a zero, como C int()
    if (xmin < 0) xmin = 0;
    var xmax = (centro + suporte + 0.5).truncate();
    if (xmax > entrada) xmax = entrada;
    xmax -= xmin;
    final k = Float64List(xmax);
    var soma = 0.0;
    for (var x = 0; x < xmax; x++) {
      final w = _filtroBilinear((x + xmin - centro + 0.5) / filtro);
      k[x] = w;
      soma += w;
    }
    if (soma != 0) {
      for (var x = 0; x < xmax; x++) {
        k[x] /= soma;
      }
    }
    inicio.add(xmin);
    tamanho.add(xmax);
    pesos.add(k);
  }
  return _Coeficientes(inicio, tamanho, pesos);
}

/// Reamostra uma imagem RGB intercalada (sw x sh) para (dw x dh).
/// Passe horizontal em ponto flutuante, depois vertical, e arredondamento final para 0..255.
Uint8List reamostrarPIL(Uint8List src, int sw, int sh, int dw, int dh) {
  final h = _coeficientesPIL(sw, dw);
  final v = _coeficientesPIL(sh, dh);

  final tmp = Float64List(sh * dw * 3);
  for (var y = 0; y < sh; y++) {
    final base = y * sw * 3;
    for (var x = 0; x < dw; x++) {
      final xmin = h.inicio[x];
      final n = h.tamanho[x];
      final k = h.pesos[x];
      for (var c = 0; c < 3; c++) {
        var s = 0.0;
        for (var j = 0; j < n; j++) {
          s += src[base + (xmin + j) * 3 + c] * k[j];
        }
        tmp[(y * dw + x) * 3 + c] = s;
      }
    }
  }

  final out = Uint8List(dh * dw * 3);
  for (var yy = 0; yy < dh; yy++) {
    final ymin = v.inicio[yy];
    final n = v.tamanho[yy];
    final k = v.pesos[yy];
    for (var x = 0; x < dw; x++) {
      for (var c = 0; c < 3; c++) {
        var s = 0.0;
        for (var j = 0; j < n; j++) {
          s += tmp[((ymin + j) * dw + x) * 3 + c] * k[j];
        }
        final r = (s + 0.5).floor();
        out[(yy * dw + x) * 3 + c] = r < 0 ? 0 : (r > 255 ? 255 : r);
      }
    }
  }
  return out;
}

/// Converte os bytes de uma imagem no tensor CHW float32 [3 x tamanho x tamanho] do modelo.
Float32List preprocessarBytes(
  Uint8List bytes, {
  required List<double> media,
  required List<double> desvio,
  required int tamanho,
}) {
  final decodificada = img.decodeImage(bytes);
  if (decodificada == null) {
    throw const FormatException('Formato de imagem não suportado.');
  }
  final orientada = img.bakeOrientation(decodificada);
  final rgbImagem = orientada.convert(numChannels: 3, format: img.Format.uint8);
  final w = rgbImagem.width;
  final h = rgbImagem.height;

  final rgb = Uint8List(w * h * 3);
  var q = 0;
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final p = rgbImagem.getPixel(x, y);
      rgb[q++] = p.r.toInt();
      rgb[q++] = p.g.toInt();
      rgb[q++] = p.b.toInt();
    }
  }

  final r = reamostrarPIL(rgb, w, h, tamanho, tamanho);
  final n = tamanho * tamanho;
  final t = Float32List(3 * n);
  for (var p = 0; p < n; p++) {
    for (var c = 0; c < 3; c++) {
      t[c * n + p] = ((r[p * 3 + c] / 255.0) - media[c]) / desvio[c];
    }
  }
  return t;
}
