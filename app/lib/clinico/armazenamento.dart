// Armazenamento local e CRIPTOGRAFADO dos dados clínicos. Nada sai do aparelho.
//  - Cifra: AES-256-GCM (autenticada: qualquer adulteração do arquivo é detectada e rejeitada).
//  - Chave: 32 bytes aleatórios gerados no aparelho, guardados no Android Keystore (via
//    flutter_secure_storage); nunca no arquivo. Apagar a chave torna os dados irrecuperáveis.
//  - Arquivo: no diretório privado do app, formato "DSC1" + nonce(12) + texto cifrado + etiqueta(16).
//  - O consentimento fica dentro do mesmo registro cifrado.
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import 'dados_clinicos.dart';

const int versaoConsentimento = 1;

class RegistroClinico {
  const RegistroClinico({this.consentido = false, this.dados});
  final bool consentido;
  final DadosClinicos? dados;

  Map<String, Object?> toJson() => {
        'consentimento': {'aceito': consentido, 'versao': versaoConsentimento},
        'dados': dados?.toJson(),
      };

  factory RegistroClinico.fromJson(Object? bruto) {
    if (bruto is! Map) throw const FormatException('Registro inválido.');
    final j = Map<String, Object?>.from(bruto);
    if (j.keys.any((k) => k != 'consentimento' && k != 'dados')) throw const FormatException('Campo desconhecido.');
    final c = j['consentimento'];
    if (c is! Map || c.keys.any((k) => k != 'aceito' && k != 'versao') || c['aceito'] is! bool || c['versao'] is! int) {
      throw const FormatException('Consentimento inválido.');
    }
    // Consentimento de versão antiga deixa de valer (o texto pode ter mudado).
    final valido = c['aceito'] == true && c['versao'] == versaoConsentimento;
    final d = j['dados'];
    return RegistroClinico(consentido: valido, dados: d == null ? null : DadosClinicos.fromJson(d));
  }
}

class ArmazenamentoCorrompido implements Exception {
  const ArmazenamentoCorrompido(this.motivo);
  final String motivo;
  @override
  String toString() => 'Dados clínicos ilegíveis ou adulterados ($motivo).';
}

abstract class ArmazenamentoClinico {
  Future<RegistroClinico> carregar();
  Future<void> salvar(RegistroClinico registro);
  Future<void> apagarTudo();
}

/// Guarda a chave de 32 bytes. A implementação real usa o Keystore do Android.
abstract class ChaveStore {
  Future<String?> ler();
  Future<void> gravar(String valorBase64);
  Future<void> apagar();
}

class ChaveStoreSegura implements ChaveStore {
  ChaveStoreSegura([FlutterSecureStorage? s]) : _s = s ?? const FlutterSecureStorage();
  final FlutterSecureStorage _s;
  static const _nome = 'dermscan_chave_clinico_v1';
  @override
  Future<String?> ler() => _s.read(key: _nome);
  @override
  Future<void> gravar(String v) => _s.write(key: _nome, value: v);
  @override
  Future<void> apagar() => _s.delete(key: _nome);
}

class ChaveStoreMemoria implements ChaveStore {
  String? _v;
  @override
  Future<String?> ler() async => _v;
  @override
  Future<void> gravar(String v) async => _v = v;
  @override
  Future<void> apagar() async => _v = null;
}

class ArmazenamentoCriptografado implements ArmazenamentoClinico {
  ArmazenamentoCriptografado({ChaveStore? chaves, Future<Directory> Function()? diretorio})
      : _chaves = chaves ?? ChaveStoreSegura(),
        _diretorio = diretorio ?? getApplicationSupportDirectory;

  final ChaveStore _chaves;
  final Future<Directory> Function() _diretorio;
  final AesGcm _aes = AesGcm.with256bits();
  static final List<int> _magia = utf8.encode('DSC1');
  static final List<int> _aad = utf8.encode('DermSCAN-clinico-v1');

  Future<File> _arquivo() async => File('${(await _diretorio()).path}/clinico.bin');

  Future<SecretKey> _chave({required bool criar}) async {
    final salva = await _chaves.ler();
    if (salva != null) {
      final bytes = base64Decode(salva);
      if (bytes.length != 32) throw const ArmazenamentoCorrompido('chave com tamanho inválido');
      return SecretKey(bytes);
    }
    if (!criar) throw const ArmazenamentoCorrompido('chave ausente');
    final r = math.Random.secure();
    final nova = Uint8List.fromList(List<int>.generate(32, (_) => r.nextInt(256)));
    await _chaves.gravar(base64Encode(nova));
    return SecretKey(nova);
  }

  @override
  Future<RegistroClinico> carregar() async {
    final f = await _arquivo();
    if (!await f.exists()) return const RegistroClinico();
    final b = await f.readAsBytes();
    if (b.length < 4 + 12 + 16 + 1 || b.length > 256 * 1024) throw const ArmazenamentoCorrompido('tamanho inválido');
    for (var i = 0; i < 4; i++) {
      if (b[i] != _magia[i]) throw const ArmazenamentoCorrompido('cabeçalho inválido');
    }
    final nonce = b.sublist(4, 16);
    final mac = Mac(b.sublist(b.length - 16));
    final cifrado = b.sublist(16, b.length - 16);
    final chave = await _chave(criar: false);
    final List<int> claro;
    try {
      claro = await _aes.decrypt(SecretBox(cifrado, nonce: nonce, mac: mac), secretKey: chave, aad: _aad);
    } on SecretBoxAuthenticationError {
      throw const ArmazenamentoCorrompido('falha de autenticação');
    }
    try {
      return RegistroClinico.fromJson(jsonDecode(utf8.decode(claro)));
    } on FormatException catch (e) {
      throw ArmazenamentoCorrompido(e.message);
    }
  }

  @override
  Future<void> salvar(RegistroClinico registro) async {
    final chave = await _chave(criar: true);
    final claro = utf8.encode(jsonEncode(registro.toJson()));
    final caixa = await _aes.encrypt(claro, secretKey: chave, aad: _aad); // nonce aleatório novo a cada gravação
    final saida = BytesBuilder()
      ..add(_magia)
      ..add(caixa.nonce)
      ..add(caixa.cipherText)
      ..add(caixa.mac.bytes);
    final f = await _arquivo();
    await f.parent.create(recursive: true);
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsBytes(saida.toBytes(), flush: true);
    await tmp.rename(f.path);
  }

  @override
  Future<void> apagarTudo() async {
    final f = await _arquivo();
    for (final alvo in [f, File('${f.path}.tmp')]) {
      if (await alvo.exists()) {
        try {
          final n = await alvo.length();
          await alvo.writeAsBytes(Uint8List(n), flush: true); // sobrescreve antes de apagar (melhor esforço)
        } on FileSystemException {
          // segue para apagar
        }
        await alvo.delete();
      }
    }
    await _chaves.apagar(); // apagar a chave também torna qualquer cópia residual ilegível
  }
}

/// Apenas para testes e pré-visualização: nada é persistido.
class ArmazenamentoMemoria implements ArmazenamentoClinico {
  ArmazenamentoMemoria([RegistroClinico? inicial]) : _r = inicial ?? const RegistroClinico();
  RegistroClinico _r;
  @override
  Future<RegistroClinico> carregar() async => _r;
  @override
  Future<void> salvar(RegistroClinico registro) async => _r = registro;
  @override
  Future<void> apagarTudo() async => _r = const RegistroClinico();
}
