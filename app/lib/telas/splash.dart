// Splash animada do DermSCAN: colchetes se fecham, a lente aparece, a lesão surge e a linha de
// varredura percorre a lente. Respeita "reduzir animações" do sistema. Dura ~2,2 s.
import 'dart:async';
import 'package:flutter/material.dart';
import '../marca/cores.dart';
import '../marca/simbolo.dart';

class Splash extends StatefulWidget {
  const Splash({super.key, required this.aoTerminar, this.duracao = const Duration(milliseconds: 2200)});
  final VoidCallback aoTerminar;
  final Duration duracao;

  @override
  State<Splash> createState() => _SplashState();
}

class _SplashState extends State<Splash> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.duracao);
  bool _reduzir = false;
  bool _iniciada = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_iniciada) return;
    _iniciada = true;
    _reduzir = MediaQuery.of(context).disableAnimations;
    if (_reduzir) {
      _c.value = 1;
      Timer(const Duration(milliseconds: 600), _fim);
    } else {
      _c.forward().whenComplete(() => Timer(const Duration(milliseconds: 250), _fim));
    }
  }

  void _fim() {
    if (mounted) widget.aoTerminar();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  double _faixa(double t, double a, double b) => ((t - a) / (b - a)).clamp(0.0, 1.0);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Marca.tinta,
      body: Center(
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            final t = _c.value;
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox.square(
                  dimension: 168,
                  child: CustomPaint(
                    painter: SimboloPainter(
                      colchetes: Curves.easeOut.transform(_faixa(t, 0.0, 0.30)),
                      lente: _faixa(t, 0.15, 0.40),
                      lesao: Curves.easeIn.transform(_faixa(t, 0.35, 0.55)),
                      varredura: _faixa(t, 0.50, 0.90),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Opacity(
                  opacity: _faixa(t, 0.70, 0.95),
                  child: Transform.translate(
                    offset: Offset(0, 8 * (1 - _faixa(t, 0.70, 0.95))),
                    child: const Nome(tamanho: 34),
                  ),
                ),
                const SizedBox(height: 8),
                Opacity(
                  opacity: _faixa(t, 0.80, 1.0),
                  child: const Text(
                    'Apoio à pesquisa · não é diagnóstico',
                    style: TextStyle(fontFamily: Marca.fonte, fontSize: 12, color: Marca.aguaClara),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
