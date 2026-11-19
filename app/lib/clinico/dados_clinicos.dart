// Dados clínicos opcionais do paciente, para apoiar a triagem. Tudo é estruturado (enums e inteiros
// limitados); os dois únicos campos de texto (município e observações) são saneados e NUNCA entram
// em regra, classificador ou qualquer interpretador: são texto inerte, exibido como texto puro.
import 'dart:convert';

/// Resposta de três estados: o "não sei" é diferente de "não".
enum Tri { sim, nao, naoSei }

enum Sexo { feminino, masculino, naoInformado }

enum Exame { naoFeito, positivo, negativo }

enum LocalLesao { cabecaPescoco, tronco, membrosSuperiores, membrosInferiores, mucosaNasalOral }

const int maxTextoMunicipio = 60;
const int maxTextoObservacoes = 280;
const int versaoDados = 1;

/// Saneia texto livre: remove caracteres de controle, de formatação invisível (largura zero,
/// marcas bidirecionais, BOM, separadores de linha/parágrafo), normaliza espaços e limita o tamanho.
/// Não "interpreta" nada: apenas deixa o texto inofensivo para exibição e armazenamento.
String sanitizarTexto(String entrada, int maximo) {
  final saida = StringBuffer();
  var ultimoEspaco = true;
  for (final r in entrada.runes) {
    final controle = r < 0x20 || (r >= 0x7F && r <= 0x9F);
    final invisivel = (r >= 0x200B && r <= 0x200F) ||
        (r >= 0x202A && r <= 0x202E) ||
        (r >= 0x2060 && r <= 0x2064) ||
        (r >= 0x2066 && r <= 0x2069) ||
        r == 0x2028 ||
        r == 0x2029 ||
        r == 0xFEFF ||
        r == 0x00AD ||
        (r >= 0xE000 && r <= 0xF8FF) || // uso privado
        (r >= 0xFFF0 && r <= 0xFFFF) ||
        (r >= 0xD800 && r <= 0xDFFF);
    if (controle || invisivel) {
      // \t, \n, \r viram espaço; o restante é descartado.
      if (r == 0x09 || r == 0x0A || r == 0x0D) {
        if (!ultimoEspaco) saida.write(' ');
        ultimoEspaco = true;
      }
      continue;
    }
    if (r == 0x20 || r == 0xA0) {
      if (!ultimoEspaco) saida.write(' ');
      ultimoEspaco = true;
    } else {
      saida.writeCharCode(r);
      ultimoEspaco = false;
    }
  }
  var t = saida.toString().trim();
  final runas = t.runes.toList();
  if (runas.length > maximo) t = String.fromCharCodes(runas.take(maximo)).trim();
  return t;
}

class DadosClinicos {
  const DadosClinicos({
    this.municipio = '',
    this.residenteAreaTransmissao,
    this.exposicaoMataOuRural,
    this.deslocamentoAreaEndemica6m,
    this.casosNaFamiliaOuVizinhanca,
    this.semanasEvolucao,
    this.numeroLesoes,
    this.locais = const {},
    this.fundoGranulosoBordasElevadas,
    this.dor,
    this.linfadenopatia,
    this.secrecaoPurulenta,
    this.idadeAnos,
    this.sexo,
    this.fitzpatrick,
    this.gestante,
    this.imunossupressaoOuHiv,
    this.antibioticoPrevioSemMelhora,
    this.parasitologico,
    this.pcr,
    this.montenegro,
    this.tratamentoAnteriorLeishmaniose,
    this.observacoes = '',
  });

  // Epidemiologia
  final String municipio;
  final Tri? residenteAreaTransmissao;
  final Tri? exposicaoMataOuRural;
  final Tri? deslocamentoAreaEndemica6m;
  final Tri? casosNaFamiliaOuVizinhanca;
  // Lesão
  final int? semanasEvolucao;
  final int? numeroLesoes;
  final Set<LocalLesao> locais;
  final Tri? fundoGranulosoBordasElevadas;
  final Tri? dor;
  final Tri? linfadenopatia;
  final Tri? secrecaoPurulenta;
  // Paciente
  final int? idadeAnos;
  final Sexo? sexo;
  final int? fitzpatrick;
  final Tri? gestante;
  final Tri? imunossupressaoOuHiv;
  // Diagnóstico e tratamento prévios
  final Tri? antibioticoPrevioSemMelhora;
  final Exame? parasitologico;
  final Exame? pcr;
  final Exame? montenegro;
  final Tri? tratamentoAnteriorLeishmaniose;
  // Texto inerte
  final String observacoes;

  bool get vazio => toJson().entries.every((e) {
        if (e.key == 'versao') return true;
        final v = e.value;
        return v == null || (v is String && v.isEmpty) || (v is List && v.isEmpty);
      });

  bool get lesaoMucosa => locais.contains(LocalLesao.mucosaNasalOral);

  static const _tri = {'sim': Tri.sim, 'nao': Tri.nao, 'naoSei': Tri.naoSei};
  static const _sexo = {'feminino': Sexo.feminino, 'masculino': Sexo.masculino, 'naoInformado': Sexo.naoInformado};
  static const _exame = {'naoFeito': Exame.naoFeito, 'positivo': Exame.positivo, 'negativo': Exame.negativo};
  static final _local = {for (final l in LocalLesao.values) l.name: l};

  Map<String, Object?> toJson() => {
        'versao': versaoDados,
        'municipio': municipio,
        'residenteAreaTransmissao': residenteAreaTransmissao?.name,
        'exposicaoMataOuRural': exposicaoMataOuRural?.name,
        'deslocamentoAreaEndemica6m': deslocamentoAreaEndemica6m?.name,
        'casosNaFamiliaOuVizinhanca': casosNaFamiliaOuVizinhanca?.name,
        'semanasEvolucao': semanasEvolucao,
        'numeroLesoes': numeroLesoes,
        'locais': (locais.map((l) => l.name).toList()..sort()),
        'fundoGranulosoBordasElevadas': fundoGranulosoBordasElevadas?.name,
        'dor': dor?.name,
        'linfadenopatia': linfadenopatia?.name,
        'secrecaoPurulenta': secrecaoPurulenta?.name,
        'idadeAnos': idadeAnos,
        'sexo': sexo?.name,
        'fitzpatrick': fitzpatrick,
        'gestante': gestante?.name,
        'imunossupressaoOuHiv': imunossupressaoOuHiv?.name,
        'antibioticoPrevioSemMelhora': antibioticoPrevioSemMelhora?.name,
        'parasitologico': parasitologico?.name,
        'pcr': pcr?.name,
        'montenegro': montenegro?.name,
        'tratamentoAnteriorLeishmaniose': tratamentoAnteriorLeishmaniose?.name,
        'observacoes': observacoes,
      };

  /// Leitura ESTRITA (lista de permissão): chaves desconhecidas, tipos errados, valores fora dos
  /// limites ou enums inexistentes geram [FormatException]. Um arquivo adulterado nunca é "adaptado".
  factory DadosClinicos.fromJson(Object? bruto) {
    if (bruto is! Map) throw const FormatException('Registro clínico inválido.');
    final j = Map<String, Object?>.from(bruto);
    const permitidas = {
      'versao', 'municipio', 'residenteAreaTransmissao', 'exposicaoMataOuRural', 'deslocamentoAreaEndemica6m',
      'casosNaFamiliaOuVizinhanca', 'semanasEvolucao', 'numeroLesoes', 'locais', 'fundoGranulosoBordasElevadas',
      'dor', 'linfadenopatia', 'secrecaoPurulenta', 'idadeAnos', 'sexo', 'fitzpatrick', 'gestante',
      'imunossupressaoOuHiv', 'antibioticoPrevioSemMelhora', 'parasitologico', 'pcr', 'montenegro',
      'tratamentoAnteriorLeishmaniose', 'observacoes',
    };
    for (final k in j.keys) {
      if (!permitidas.contains(k)) throw FormatException('Campo desconhecido: ${k.length > 30 ? k.substring(0, 30) : k}');
    }
    if (j['versao'] != versaoDados) throw const FormatException('Versão de dados não suportada.');
    T? enumDe<T>(String k, Map<String, T> mapa) {
      final v = j[k];
      if (v == null) return null;
      if (v is! String || !mapa.containsKey(v)) throw FormatException('Valor inválido em $k.');
      return mapa[v];
    }

    int? inteiro(String k, int min, int max) {
      final v = j[k];
      if (v == null) return null;
      if (v is! int || v < min || v > max) throw FormatException('Número fora do limite em $k.');
      return v;
    }

    String texto(String k, int max) {
      final v = j[k];
      if (v == null) return '';
      if (v is! String) throw FormatException('Texto inválido em $k.');
      return sanitizarTexto(v, max);
    }

    final locaisBrutos = j['locais'];
    final locais = <LocalLesao>{};
    if (locaisBrutos != null) {
      if (locaisBrutos is! List || locaisBrutos.length > LocalLesao.values.length) {
        throw const FormatException('Lista de locais inválida.');
      }
      for (final l in locaisBrutos) {
        if (l is! String || !_local.containsKey(l)) throw const FormatException('Local de lesão inválido.');
        locais.add(_local[l]!);
      }
    }
    return DadosClinicos(
      municipio: texto('municipio', maxTextoMunicipio),
      residenteAreaTransmissao: enumDe('residenteAreaTransmissao', _tri),
      exposicaoMataOuRural: enumDe('exposicaoMataOuRural', _tri),
      deslocamentoAreaEndemica6m: enumDe('deslocamentoAreaEndemica6m', _tri),
      casosNaFamiliaOuVizinhanca: enumDe('casosNaFamiliaOuVizinhanca', _tri),
      semanasEvolucao: inteiro('semanasEvolucao', 0, 520),
      numeroLesoes: inteiro('numeroLesoes', 0, 200),
      locais: locais,
      fundoGranulosoBordasElevadas: enumDe('fundoGranulosoBordasElevadas', _tri),
      dor: enumDe('dor', _tri),
      linfadenopatia: enumDe('linfadenopatia', _tri),
      secrecaoPurulenta: enumDe('secrecaoPurulenta', _tri),
      idadeAnos: inteiro('idadeAnos', 0, 120),
      sexo: enumDe('sexo', _sexo),
      fitzpatrick: inteiro('fitzpatrick', 1, 6),
      gestante: enumDe('gestante', _tri),
      imunossupressaoOuHiv: enumDe('imunossupressaoOuHiv', _tri),
      antibioticoPrevioSemMelhora: enumDe('antibioticoPrevioSemMelhora', _tri),
      parasitologico: enumDe('parasitologico', _exame),
      pcr: enumDe('pcr', _exame),
      montenegro: enumDe('montenegro', _exame),
      tratamentoAnteriorLeishmaniose: enumDe('tratamentoAnteriorLeishmaniose', _tri),
      observacoes: texto('observacoes', maxTextoObservacoes),
    );
  }

  String toJsonString() => jsonEncode(toJson());
  factory DadosClinicos.fromJsonString(String s) => DadosClinicos.fromJson(jsonDecode(s));
}
