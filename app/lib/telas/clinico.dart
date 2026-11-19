// Telas dos dados clínicos opcionais: consentimento e formulário. Tudo fica criptografado neste aparelho.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../clinico/dados_clinicos.dart';

class TelaConsentimentoClinico extends StatefulWidget {
  const TelaConsentimentoClinico({super.key});

  @override
  State<TelaConsentimentoClinico> createState() => _TelaConsentimentoClinicoState();
}

class _TelaConsentimentoClinicoState extends State<TelaConsentimentoClinico> {
  bool _ok = false;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    Widget item(String t) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Padding(padding: EdgeInsets.only(top: 3), child: Icon(Icons.check_circle_outline, size: 18)),
            const SizedBox(width: 8),
            Expanded(child: Text(t, style: tema.textTheme.bodyMedium)),
          ]),
        );
    return Scaffold(
      appBar: AppBar(title: const Text('Dados clínicos do paciente')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Text('Antes de registrar', style: tema.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          item('Os dados são opcionais e ficam somente neste aparelho, criptografados (AES-256-GCM, chave no Android Keystore). Nada é enviado a servidor.'),
          item('Servem para um indicador por regras do Ministério da Saúde, mostrado ao lado do resultado da imagem. Não alteram o modelo de IA nem geram probabilidade de doença.'),
          item('O resultado não é diagnóstico nem substitui avaliação médica ou laboratorial.'),
          item('Você pode apagar tudo a qualquer momento, e a chave de criptografia é apagada junto.'),
          item('Usar dados de pacientes reais em pesquisa (coleta, compartilhamento ou publicação) exige termo de consentimento e aprovação de comitê de ética. Este aplicativo não envia nem exporta esses dados.'),
          const SizedBox(height: 8),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: _ok,
            onChanged: (v) => setState(() => _ok = v ?? false),
            title: const Text('Confirmo que o paciente foi informado e concorda com o registro local destes dados.'),
          ),
          const SizedBox(height: 8),
          FilledButton(onPressed: _ok ? () => Navigator.of(context).pop(true) : null, child: const Text('Continuar')),
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Agora não')),
        ],
      ),
    );
  }
}

class TelaFormularioClinico extends StatefulWidget {
  const TelaFormularioClinico({super.key, this.inicial = const DadosClinicos()});
  final DadosClinicos inicial;

  @override
  State<TelaFormularioClinico> createState() => _TelaFormularioClinicoState();
}

/// Resultado da tela: salvar (com dados) ou apagar tudo.
class RespostaFormulario {
  const RespostaFormulario.salvar(this.dados) : apagar = false;
  const RespostaFormulario.apagar()
      : dados = null,
        apagar = true;
  final DadosClinicos? dados;
  final bool apagar;
}

class _TelaFormularioClinicoState extends State<TelaFormularioClinico> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _municipio = TextEditingController(text: widget.inicial.municipio);
  late final TextEditingController _semanas = TextEditingController(text: widget.inicial.semanasEvolucao?.toString() ?? '');
  late final TextEditingController _lesoes = TextEditingController(text: widget.inicial.numeroLesoes?.toString() ?? '');
  late final TextEditingController _idade = TextEditingController(text: widget.inicial.idadeAnos?.toString() ?? '');
  late final TextEditingController _obs = TextEditingController(text: widget.inicial.observacoes);

  late Tri? _residente = widget.inicial.residenteAreaTransmissao;
  late Tri? _mata = widget.inicial.exposicaoMataOuRural;
  late Tri? _desloc = widget.inicial.deslocamentoAreaEndemica6m;
  late Tri? _casos = widget.inicial.casosNaFamiliaOuVizinhanca;
  late final Set<LocalLesao> _locais = {...widget.inicial.locais};
  late Tri? _fundo = widget.inicial.fundoGranulosoBordasElevadas;
  late Tri? _dor = widget.inicial.dor;
  late Tri? _linfa = widget.inicial.linfadenopatia;
  late Tri? _secrecao = widget.inicial.secrecaoPurulenta;
  late Sexo? _sexo = widget.inicial.sexo;
  late int? _fitz = widget.inicial.fitzpatrick;
  late Tri? _gestante = widget.inicial.gestante;
  late Tri? _imuno = widget.inicial.imunossupressaoOuHiv;
  late Tri? _antib = widget.inicial.antibioticoPrevioSemMelhora;
  late Exame? _parasito = widget.inicial.parasitologico;
  late Exame? _pcr = widget.inicial.pcr;
  late Exame? _monte = widget.inicial.montenegro;
  late Tri? _trat = widget.inicial.tratamentoAnteriorLeishmaniose;

  @override
  void dispose() {
    for (final c in [_municipio, _semanas, _lesoes, _idade, _obs]) {
      c.dispose();
    }
    super.dispose();
  }

  static const _rotuloTri = {Tri.sim: 'Sim', Tri.nao: 'Não', Tri.naoSei: 'Não sei'};
  static const _rotuloExame = {Exame.naoFeito: 'Não feito', Exame.positivo: 'Positivo', Exame.negativo: 'Negativo'};
  static const _rotuloSexo = {Sexo.feminino: 'Feminino', Sexo.masculino: 'Masculino', Sexo.naoInformado: 'Não informado'};
  static const _rotuloLocal = {
    LocalLesao.cabecaPescoco: 'Cabeça e pescoço',
    LocalLesao.tronco: 'Tronco',
    LocalLesao.membrosSuperiores: 'Membros superiores',
    LocalLesao.membrosInferiores: 'Membros inferiores',
    LocalLesao.mucosaNasalOral: 'Mucosa nasal ou oral',
  };

  Widget _titulo(String t) => Padding(
        padding: const EdgeInsets.only(top: 22, bottom: 4),
        child: Text(t, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
      );

  Widget _escolha<T>(String pergunta, Map<T, String> rotulos, T? valor, void Function(T?) aoMudar) => Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(pergunta),
          const SizedBox(height: 4),
          Wrap(spacing: 8, children: [
            for (final e in rotulos.entries)
              ChoiceChip(
                label: Text(e.value),
                selected: valor == e.key,
                // Tocar de novo limpa a resposta (volta a "sem informação").
                onSelected: (s) => setState(() => aoMudar(s ? e.key : null)),
              ),
          ]),
        ]),
      );

  Widget _tri(String pergunta, Tri? valor, void Function(Tri?) aoMudar) => _escolha<Tri>(pergunta, _rotuloTri, valor, aoMudar);

  Widget _numero(String rotulo, TextEditingController c, int min, int max) => Padding(
        padding: const EdgeInsets.only(top: 10),
        child: TextFormField(
          controller: c,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(3)],
          decoration: InputDecoration(labelText: rotulo, border: const OutlineInputBorder()),
          validator: (v) {
            if (v == null || v.isEmpty) return null;
            final n = int.tryParse(v);
            if (n == null || n < min || n > max) return 'Informe de $min a $max';
            return null;
          },
        ),
      );

  int? _int(TextEditingController c) => c.text.isEmpty ? null : int.tryParse(c.text);

  DadosClinicos _montar() => DadosClinicos(
        municipio: sanitizarTexto(_municipio.text, maxTextoMunicipio),
        residenteAreaTransmissao: _residente,
        exposicaoMataOuRural: _mata,
        deslocamentoAreaEndemica6m: _desloc,
        casosNaFamiliaOuVizinhanca: _casos,
        semanasEvolucao: _int(_semanas),
        numeroLesoes: _int(_lesoes),
        locais: _locais,
        fundoGranulosoBordasElevadas: _fundo,
        dor: _dor,
        linfadenopatia: _linfa,
        secrecaoPurulenta: _secrecao,
        idadeAnos: _int(_idade),
        sexo: _sexo,
        fitzpatrick: _fitz,
        gestante: _gestante,
        imunossupressaoOuHiv: _imuno,
        antibioticoPrevioSemMelhora: _antib,
        parasitologico: _parasito,
        pcr: _pcr,
        montenegro: _monte,
        tratamentoAnteriorLeishmaniose: _trat,
        observacoes: sanitizarTexto(_obs.text, maxTextoObservacoes),
      );

  Future<void> _apagar() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Apagar dados clínicos?'),
        content: const Text('Os dados e a chave de criptografia serão apagados deste aparelho. Isso não pode ser desfeito.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(c).pop(false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.of(c).pop(true), child: const Text('Apagar')),
        ],
      ),
    );
    if (ok == true && mounted) Navigator.of(context).pop(const RespostaFormulario.apagar());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dados clínicos')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
          children: [
            _titulo('Epidemiologia'),
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: TextFormField(
                controller: _municipio,
                inputFormatters: [LengthLimitingTextInputFormatter(maxTextoMunicipio)],
                decoration: const InputDecoration(labelText: 'Município de residência ou procedência', border: OutlineInputBorder()),
              ),
            ),
            _tri('Reside ou é procedente de área com transmissão de leishmaniose?', _residente, (v) => _residente = v),
            _tri('Deslocamento para área de transmissão nos 6 meses antes dos sintomas?', _desloc, (v) => _desloc = v),
            _tri('Atividade em mata ou área rural (6 meses)?', _mata, (v) => _mata = v),
            _tri('Casos na família ou vizinhança?', _casos, (v) => _casos = v),
            _titulo('Lesão'),
            _numero('Tempo de evolução (semanas)', _semanas, 0, 520),
            _numero('Número de lesões', _lesoes, 0, 200),
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Localização'),
                const SizedBox(height: 4),
                Wrap(spacing: 8, children: [
                  for (final e in _rotuloLocal.entries)
                    FilterChip(
                      label: Text(e.value),
                      selected: _locais.contains(e.key),
                      onSelected: (s) => setState(() => s ? _locais.add(e.key) : _locais.remove(e.key)),
                    ),
                ]),
              ]),
            ),
            _tri('Úlcera com fundo granuloso e bordas elevadas em moldura?', _fundo, (v) => _fundo = v),
            _tri('Dor na lesão?', _dor, (v) => _dor = v),
            _tri('Gânglios aumentados (linfadenopatia)?', _linfa, (v) => _linfa = v),
            _tri('Secreção purulenta?', _secrecao, (v) => _secrecao = v),
            _titulo('Paciente'),
            _numero('Idade (anos)', _idade, 0, 120),
            _escolha<Sexo>('Sexo', _rotuloSexo, _sexo, (v) => _sexo = v),
            _escolha<int>('Tom de pele (Fitzpatrick)', {for (var i = 1; i <= 6; i++) i: 'Tipo ${['', 'I', 'II', 'III', 'IV', 'V', 'VI'][i]}'}, _fitz, (v) => _fitz = v),
            _tri('Gestante?', _gestante, (v) => _gestante = v),
            _tri('Imunossupressão ou HIV?', _imuno, (v) => _imuno = v),
            _titulo('Diagnóstico e tratamento prévios'),
            _tri('Usou antibiótico sem melhora?', _antib, (v) => _antib = v),
            _escolha<Exame>('Exame parasitológico direto', _rotuloExame, _parasito, (v) => _parasito = v),
            _escolha<Exame>('PCR', _rotuloExame, _pcr, (v) => _pcr = v),
            _escolha<Exame>('Intradermorreação de Montenegro', _rotuloExame, _monte, (v) => _monte = v),
            _tri('Já tratou leishmaniose antes?', _trat, (v) => _trat = v),
            _titulo('Observações (texto livre)'),
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: TextFormField(
                controller: _obs,
                maxLines: 3,
                inputFormatters: [LengthLimitingTextInputFormatter(maxTextoObservacoes)],
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  helperText: 'Apenas anotação. Este texto não é usado por nenhuma regra nem pela IA.',
                  helperMaxLines: 2,
                ),
              ),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () {
                if (_form.currentState!.validate()) Navigator.of(context).pop(RespostaFormulario.salvar(_montar()));
              },
              child: const Text('Salvar neste aparelho'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(onPressed: _apagar, icon: const Icon(Icons.delete_outline), label: const Text('Apagar dados e chave')),
          ],
        ),
      ),
    );
  }
}
