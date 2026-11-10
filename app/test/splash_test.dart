import 'package:dermscan/marca/simbolo.dart';
import 'package:dermscan/telas/splash.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('splash anima, mostra o nome e chama aoTerminar uma vez', (tester) async {
    var chamadas = 0;
    await tester.pumpWidget(MaterialApp(
      home: Splash(aoTerminar: () => chamadas++, duracao: const Duration(milliseconds: 1000)),
    ));
    expect(find.byType(CustomPaint), findsWidgets);
    expect(find.text('Apoio à pesquisa · não é diagnóstico'), findsOneWidget);
    expect(chamadas, 0);
    await tester.pump(const Duration(milliseconds: 1100)); // fim da animação
    await tester.pump(const Duration(milliseconds: 300)); // atraso final
    expect(chamadas, 1);
  });

  testWidgets('com "reduzir animações", a splash abre completa e termina logo', (tester) async {
    var chamadas = 0;
    await tester.pumpWidget(MediaQuery(
      data: const MediaQueryData(disableAnimations: true),
      child: MaterialApp(home: Splash(aoTerminar: () => chamadas++)),
    ));
    await tester.pump(const Duration(milliseconds: 700));
    expect(chamadas, 1);
  });

  testWidgets('Nome expõe rótulo semântico DermSCAN', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Nome())));
    expect(find.bySemanticsLabel('DermSCAN'), findsOneWidget);
  });

  test('painter só repinta quando um progresso muda', () {
    const a = SimboloPainter(varredura: 0.5);
    expect(a.shouldRepaint(const SimboloPainter(varredura: 0.5)), isFalse);
    expect(a.shouldRepaint(const SimboloPainter(varredura: 0.6)), isTrue);
  });
}
