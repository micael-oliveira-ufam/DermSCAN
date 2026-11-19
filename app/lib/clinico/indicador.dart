// Indicador clínico-epidemiológico de SUSPEITA, por regras publicadas. Não é probabilidade, não é
// escore validado e não altera o modelo de imagem. Função pura: só lê campos estruturados de
// [DadosClinicos]; texto livre (município, observações) nunca é lido aqui.
//
// Fonte das regras: Brasil. Ministério da Saúde. Manual de Vigilância da Leishmaniose Tegumentar.
// Brasília, 2017 (cópia consultada: Centro de Vigilância Epidemiológica de São Paulo). Definição de
// caso suspeito na seção 7.1.1: cutânea = "lesões de pele ulceradas ou não com três semanas ou mais de
// evolução", em residente ou exposto a área de transmissão; mucosa = lesão de mucosa de vias aéreas
// superiores, principalmente nasal, em residente ou exposto a área de transmissão.
import '../classificador.dart';
import 'dados_clinicos.dart';

const String fonteManual = 'Manual de Vigilância da Leishmaniose Tegumentar (Ministério da Saúde, 2017)';

enum Estado { atendido, naoAtendido, semInformacao }

enum Nivel { suspeitoCutanea, suspeitoMucosa, naoAtende, insuficiente }

class Criterio {
  const Criterio(this.texto, this.estado, this.fonte);
  final String texto;
  final Estado estado;
  final String fonte;
}

class Indicador {
  const Indicador({required this.nivel, required this.criterios, required this.apoio, required this.alertas});
  final Nivel nivel;
  final List<Criterio> criterios;
  final List<String> apoio;
  final List<String> alertas;

  String get titulo => switch (nivel) {
        Nivel.suspeitoCutanea => 'Atende à definição de caso suspeito de leishmaniose cutânea',
        Nivel.suspeitoMucosa => 'Atende à definição de caso suspeito de leishmaniose mucosa',
        Nivel.naoAtende => 'Não atende à definição de caso suspeito com os dados informados',
        Nivel.insuficiente => 'Dados insuficientes para aplicar a definição de caso suspeito',
      };

  bool get suspeito => nivel == Nivel.suspeitoCutanea || nivel == Nivel.suspeitoMucosa;
}

const Set<String> classesLeishmaniose = {'leish_cutanea_ulcera', 'leish_cutanea_outras_formas', 'leish_mucosa'};

Indicador avaliarIndicador(DadosClinicos d) {
  const secao = 'Manual do MS, seção 7.1.1';

  final Estado tempo = d.semanasEvolucao == null
      ? Estado.semInformacao
      : (d.semanasEvolucao! >= 3 ? Estado.atendido : Estado.naoAtendido);

  final Estado exposicao;
  if (d.residenteAreaTransmissao == Tri.sim || d.deslocamentoAreaEndemica6m == Tri.sim) {
    exposicao = Estado.atendido;
  } else if (d.residenteAreaTransmissao == Tri.nao && d.deslocamentoAreaEndemica6m == Tri.nao) {
    exposicao = Estado.naoAtendido;
  } else {
    exposicao = Estado.semInformacao;
  }

  final Estado mucosa = d.locais.isEmpty
      ? Estado.semInformacao
      : (d.lesaoMucosa ? Estado.atendido : Estado.naoAtendido);

  final criterios = [
    Criterio('Lesão com 3 semanas ou mais de evolução (forma cutânea)', tempo, secao),
    Criterio('Residência, procedência ou deslocamento para área de transmissão', exposicao, secao),
    Criterio('Lesão em mucosa de vias aéreas superiores, principalmente nasal (forma mucosa)', mucosa, secao),
  ];

  final Nivel nivel;
  if (d.lesaoMucosa && exposicao == Estado.atendido) {
    nivel = Nivel.suspeitoMucosa;
  } else if (tempo == Estado.atendido && exposicao == Estado.atendido) {
    nivel = Nivel.suspeitoCutanea;
  } else if (exposicao == Estado.naoAtendido || (tempo == Estado.naoAtendido && !d.lesaoMucosa)) {
    nivel = Nivel.naoAtende;
  } else {
    nivel = Nivel.insuficiente;
  }

  final apoio = <String>[];
  if (d.fundoGranulosoBordasElevadas == Tri.sim) {
    apoio.add('Úlcera com fundo granuloso e bordas elevadas em moldura: aspecto típico descrito no Manual do MS (seção 4.1.2).');
  }
  if (d.dor == Tri.nao) apoio.add('Lesão indolor: típica da úlcera leishmaniótica sem infecção secundária (Manual do MS, seção 4.1.2).');
  if (d.casosNaFamiliaOuVizinhanca == Tri.sim) apoio.add('Casos na família ou vizinhança informados: dado epidemiológico de apoio.');

  final alertas = <String>[];
  if (d.imunossupressaoOuHiv == Tri.sim) {
    alertas.add('Imunossupressão ou HIV informado: o Manual do MS recomenda investigar qualquer lesão de pele ou mucosa com mais de 2 semanas e oferecer sorologia para HIV (seção 4.2).');
  }
  if (d.lesaoMucosa) {
    alertas.add('Lesão em mucosa informada: examinar as vias aéreas superiores e encaminhar a avaliação médica.');
  }
  if (d.gestante == Tri.sim) alertas.add('Gestação informada: encaminhar a avaliação médica antes de qualquer conduta.');
  if (d.tratamentoAnteriorLeishmaniose == Tri.sim) alertas.add('Tratamento anterior para leishmaniose informado: considerar recidiva; avaliação médica.');
  if (d.parasitologico == Exame.positivo) {
    alertas.add('Exame parasitológico positivo informado: o achado do parasito é critério de confirmação laboratorial (Manual do MS, seção 7.1.1).');
  }
  if (d.pcr == Exame.positivo) alertas.add('PCR positivo informado: apoia a confirmação; interpretar com o laboratório de referência.');
  if (d.montenegro == Exame.positivo) {
    alertas.add('Intradermorreação de Montenegro positiva, isoladamente, não confirma doença ativa (Manual do MS, seção 5).');
  }
  if (d.parasitologico == Exame.negativo && nivel != Nivel.naoAtende) {
    alertas.add('Um exame direto negativo não exclui a doença: a sensibilidade cai com o tempo de lesão e com infecção secundária (Manual do MS, seção 5).');
  }
  if (d.secrecaoPurulenta == Tri.sim) {
    alertas.add('Sinais de infecção secundária podem reduzir a sensibilidade do exame direto (Manual do MS, seção 5).');
  }
  if (nivel == Nivel.naoAtende) {
    alertas.add('Não atender à definição não exclui a doença (por exemplo, lesão recente). Em dúvida, procurar avaliação médica.');
  }
  return Indicador(nivel: nivel, criterios: criterios, apoio: apoio, alertas: alertas);
}

/// Texto que relaciona o resultado da imagem (IA) com o indicador. Só descreve concordância ou
/// divergência; não combina números nem muda probabilidades.
String compararComIa(Indicador ind, Resultado r) {
  if (r.inconclusivo) {
    return 'A IA ficou inconclusiva. Decidir com base clínica e em exame parasitológico ou PCR.';
  }
  final iaLeish = classesLeishmaniose.contains(r.principal.classe);
  if (ind.nivel == Nivel.insuficiente) {
    return 'Dados clínico-epidemiológicos insuficientes para comparar com o resultado da imagem.';
  }
  if (iaLeish && ind.suspeito) {
    return 'Imagem (IA) e dados clínico-epidemiológicos apontam na mesma direção. A confirmação exige exame parasitológico ou PCR.';
  }
  if (!iaLeish && ind.suspeito) {
    return 'Divergência: os dados atendem à definição de caso suspeito, mas a IA indicou outra classe. A IA não exclui a doença; priorizar exame parasitológico ou PCR e avaliação médica.';
  }
  if (iaLeish && !ind.suspeito) {
    return 'Divergência: a IA indicou leishmaniose, mas os dados não atendem à definição de caso suspeito. Rever as informações e procurar avaliação médica.';
  }
  return 'IA e dados clínico-epidemiológicos não apontam para leishmaniose. Isso não exclui a doença nem outras doenças graves; em dúvida, procurar avaliação médica.';
}
