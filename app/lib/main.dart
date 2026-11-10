import 'package:flutter/material.dart';

import 'classificador.dart';
import 'marca/cores.dart';
import 'telas/principal.dart';
import 'telas/splash.dart';

void main() {
  runApp(const DermScanApp());
}

ThemeData _tema(Brightness brilho) {
  final escuro = brilho == Brightness.dark;
  final esquema = ColorScheme.fromSeed(
    seedColor: Marca.floresta,
    brightness: brilho,
  ).copyWith(
    primary: escuro ? Marca.aguaClara : Marca.floresta,
    onPrimary: escuro ? Marca.tinta : Colors.white,
    surface: escuro ? const Color(0xFF103A37) : Colors.white,
    onSurface: escuro ? Marca.areia : Marca.tinta,
    tertiaryContainer: escuro ? const Color(0xFF3A2E18) : const Color(0xFFFBEBD3),
    onTertiaryContainer: escuro ? const Color(0xFFF2C98A) : Marca.ambar,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: esquema,
    fontFamily: Marca.fonte,
    scaffoldBackgroundColor: escuro ? Marca.tinta : Marca.areia,
    appBarTheme: AppBarTheme(
      backgroundColor: escuro ? Marca.tinta : Marca.areia,
      foregroundColor: escuro ? Marca.areia : Marca.tinta,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    cardTheme: CardThemeData(
      color: esquema.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: escuro ? const Color(0xFF1B4F4B) : Marca.areiaEscura),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
  );
}

class DermScanApp extends StatefulWidget {
  const DermScanApp({super.key});

  @override
  State<DermScanApp> createState() => _DermScanAppState();
}

class _DermScanAppState extends State<DermScanApp> {
  // O modelo começa a carregar já na splash, para a tela principal abrir pronta.
  late final Future<Classificador> _modelo = Classificador.carregar();
  bool _splashConcluida = false;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DermSCAN',
      debugShowCheckedModeBanner: false,
      theme: _tema(Brightness.light),
      darkTheme: _tema(Brightness.dark),
      home: AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: _splashConcluida
            ? TelaPrincipal(key: const ValueKey('principal'), modelo: _modelo)
            : Splash(key: const ValueKey('splash'), aoTerminar: () => setState(() => _splashConcluida = true)),
      ),
    );
  }
}
