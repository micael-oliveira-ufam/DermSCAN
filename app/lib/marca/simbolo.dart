// Símbolo DermSCAN desenhado em Dart, com a mesma geometria de brand/gerar_marca.py
// (caixa 256x256). Aceita progressos de animação para a splash.
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'cores.dart';

class SimboloPainter extends CustomPainter {
  const SimboloPainter({
    this.colchetes = 1,
    this.lente = 1,
    this.lesao = 1,
    this.varredura = 1,
    this.corColchete = Marca.aguaClara,
    this.corLente = Marca.floresta,
  });

  /// Todos os progressos vão de 0 a 1. [varredura] = 1 deixa a linha na posição final do logotipo.
  final double colchetes, lente, lesao, varredura;
  final Color corColchete, corLente;

  static const _cx = 128.0, _cy = 128.0, _r = 64.0, _anel = 8.0;
  static const _linhaX = 52.0, _linhaW = 152.0, _linhaH = 8.0, _linhaYFinal = 132.0;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.shortestSide / 256;
    canvas.save();
    canvas.translate((size.width - 256 * s) / 2, (size.height - 256 * s) / 2);
    canvas.scale(s);

    // colchetes: afastam-se dos cantos e se aproximam até a posição final
    if (colchetes > 0) {
      final p = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 14
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..color = corColchete.withValues(alpha: colchetes.clamp(0.0, 1.0));
      final desloc = (1 - colchetes) * 18;
      final cantos = <Path>[
        Path()..moveTo(28, 70)..lineTo(28, 42)..quadraticBezierTo(28, 28, 42, 28)..lineTo(70, 28),
        Path()..moveTo(186, 28)..lineTo(214, 28)..quadraticBezierTo(228, 28, 228, 42)..lineTo(228, 70),
        Path()..moveTo(228, 186)..lineTo(228, 214)..quadraticBezierTo(228, 228, 214, 228)..lineTo(186, 228),
        Path()..moveTo(70, 228)..lineTo(42, 228)..quadraticBezierTo(28, 228, 28, 214)..lineTo(28, 186),
      ];
      final sinais = [const Offset(-1, -1), const Offset(1, -1), const Offset(1, 1), const Offset(-1, 1)];
      for (var i = 0; i < 4; i++) {
        canvas.drawPath(cantos[i].shift(sinais[i] * desloc), p);
      }
    }

    // lente
    final raio = _r * Curves.easeOutBack.transform(lente.clamp(0.0, 1.0));
    if (lente > 0 && raio > 0) {
      final centro = const Offset(_cx, _cy);
      final a = lente.clamp(0.0, 1.0).toDouble();
      canvas.drawCircle(centro, raio, Paint()..color = corLente.withValues(alpha: a));
      canvas.drawCircle(
        centro, raio,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = _anel
          ..color = Marca.agua.withValues(alpha: a),
      );

      canvas.save();
      canvas.clipPath(Path()..addOval(Rect.fromCircle(center: centro, radius: _r)));
      // lesão (coral)
      if (lesao > 0) {
        final lesaoPath = Path()
          ..moveTo(96, 126)
          ..cubicTo(94, 106, 118, 98, 134, 104)
          ..cubicTo(152, 110, 162, 126, 156, 142)
          ..cubicTo(150, 158, 128, 166, 112, 158)
          ..cubicTo(100, 152, 97, 140, 96, 126)
          ..close();
        canvas.drawPath(lesaoPath, Paint()..color = Marca.coral.withValues(alpha: lesao.clamp(0.0, 1.0)));
      }
      // rastro da varredura: gradiente acima da linha
      final y = _yLinha();
      if (varredura > 0) {
        final rastro = Rect.fromLTWH(64, y - 56, 128, 60);
        canvas.drawRect(
          rastro,
          Paint()
            ..shader = LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Marca.aguaClara.withValues(alpha: 0), Marca.aguaClara.withValues(alpha: 0.5)],
            ).createShader(rastro),
        );
      }
      canvas.restore();
    }

    // linha de varredura
    if (varredura > 0) {
      final y = _yLinha();
      canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromLTWH(_linhaX, y, _linhaW, _linhaH), const Radius.circular(4)),
        Paint()..color = Marca.areia.withValues(alpha: math.min(1, varredura * 4)),
      );
    }
    canvas.restore();
  }

  /// 0..1 percorre a lente de cima para baixo; no fim, assenta em y=132 (posição do logotipo).
  double _yLinha() {
    const topo = _cy - _r + 4, base = _cy + _r - 12;
    if (varredura >= 1) return _linhaYFinal;
    final t = varredura;
    // ida (0..0.7) até a base, volta (0.7..1) até a posição final
    if (t < 0.7) return topo + (base - topo) * Curves.easeInOut.transform(t / 0.7);
    return base + (_linhaYFinal - base) * Curves.easeOut.transform((t - 0.7) / 0.3);
  }

  @override
  bool shouldRepaint(SimboloPainter o) =>
      o.colchetes != colchetes || o.lente != lente || o.lesao != lesao || o.varredura != varredura ||
      o.corColchete != corColchete || o.corLente != corLente;
}

class Simbolo extends StatelessWidget {
  const Simbolo({super.key, this.tamanho = 48, this.escuro = true});
  final double tamanho;
  final bool escuro;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'DermSCAN',
        image: true,
        child: SizedBox.square(
          dimension: tamanho,
          child: CustomPaint(
            painter: SimboloPainter(
              corColchete: escuro ? Marca.aguaClara : Marca.floresta,
              corLente: escuro ? Marca.floresta : Marca.tinta,
            ),
          ),
        ),
      );
}

/// Nome "DermSCAN": Derm (600) + SCAN (800), como no logotipo.
class Nome extends StatelessWidget {
  const Nome({super.key, this.tamanho = 28, this.escuro = true});
  final double tamanho;
  final bool escuro;

  @override
  Widget build(BuildContext context) => Text.rich(
        TextSpan(children: [
          TextSpan(text: 'Derm', style: TextStyle(fontWeight: FontWeight.w600, color: escuro ? Marca.areia : Marca.tinta)),
          TextSpan(text: 'SCAN', style: TextStyle(fontWeight: FontWeight.w800, color: escuro ? Marca.aguaClara : Marca.floresta)),
        ]),
        style: TextStyle(fontFamily: Marca.fonte, fontSize: tamanho, height: 1.1),
        semanticsLabel: 'DermSCAN',
      );
}
