# Dados clínicos opcionais no aplicativo (design, segurança e limites)

Data: 19/11/2026. Escopo: app Flutter (`app/`). O site (`docs/`) não foi alterado.

## O que foi implementado
- Formulário **opcional** com quatro grupos: epidemiologia, lesão, paciente, diagnóstico e tratamento prévios (`app/lib/telas/clinico.dart`). Respostas tri-estado (sim, não, não sei); "sem resposta" é diferente de "não".
- Tela de **consentimento** antes do primeiro registro (o paciente foi informado e concorda com o registro local).
- **Indicador clínico-epidemiológico de suspeita**, por regras publicadas, mostrado ao lado do resultado da IA, com texto de concordância ou divergência (`app/lib/clinico/indicador.dart`).
- Armazenamento **somente no aparelho, criptografado** (`app/lib/clinico/armazenamento.dart`). Não há envio, exportação nem backup.

## O que o indicador é e não é
Não é probabilidade, não é escore validado e **não altera** o modelo de imagem. Aplica a definição de caso suspeito do *Manual de Vigilância da Leishmaniose Tegumentar* (Ministério da Saúde, 2017; cópia consultada: CVE-SP, `manual17_lta_ms.pdf`):

| Regra do app | Base no Manual |
|:---|:---|
| Cutânea: lesão com ≥ 3 semanas **e** residência/procedência/deslocamento para área de transmissão | Seção 7.1.1, caso suspeito: "lesões de pele ulceradas ou não com três semanas ou mais de evolução", em residente ou exposto a área de transmissão |
| Mucosa: lesão de mucosa de vias aéreas superiores (nasal) **e** exposição | Seção 7.1.1, caso suspeito de leishmaniose mucosa |
| Aspecto típico (fundo granuloso, bordas elevadas, indolor): só **apoio**, sem pontuar | Seção 4.1.2 |
| HIV/imunossupressão: alerta | Seção 4.2 |
| Montenegro positivo isolado não confirma doença ativa; exame direto negativo não exclui | Seção 5 |
| Parasitológico positivo = critério de confirmação laboratorial | Seção 7.1.1 |

Idade, sexo, tom de pele, município e observações são **registrados, mas não entram em nenhuma regra** (há teste que prova isso). Não existe base pareada imagem + dados clínicos, então **nenhum ganho de acurácia da IA é afirmado**: usar esses dados como entrada do modelo exigiria coletar e treinar uma base própria, com aprovação ética.

Números de páginas e trechos foram lidos por extração automática da cópia do Manual; conferir no PDF original antes de citar em publicação.

## Criptografia
- AES-256-GCM (autenticada) com `cryptography`; nonce aleatório novo a cada gravação; AAD fixa `DermSCAN-clinico-v1`.
- Chave de 32 bytes gerada no aparelho (`Random.secure`) e guardada via `flutter_secure_storage` (Android Keystore). Nunca fica no arquivo.
- Arquivo `clinico.bin` no diretório privado do app: `DSC1` + nonce(12) + cifrado + etiqueta(16). Gravação atômica (arquivo temporário + renomear).
- "Apagar dados e chave": sobrescreve o arquivo com zeros, apaga e remove a chave (a cópia residual fica ilegível).
- Android: `allowBackup=false`, `fullBackupContent=false` e `data_extraction_rules.xml` excluindo tudo (backup na nuvem e transferência entre aparelhos).

## Proteção contra injeção de prompt
O app **não tem modelo de linguagem**: o classificador é um ViT que só recebe pixels. Portanto, injeção de prompt clássica não se aplica hoje. As medidas abaixo tornam a superfície inerte por construção e protegem uma futura integração:
1. Campos estruturados (enums e inteiros com limites) com leitura **estrita por lista de permissão**: chave desconhecida, tipo errado ou valor fora do limite gera erro (`DadosClinicos.fromJson`).
2. Só dois campos de texto livre (município, 60 caracteres; observações, 280). São saneados (controles, caracteres invisíveis e bidirecionais removidos, espaços normalizados) e **nunca** lidos por regra, classificador ou interpretador; aparecem apenas como texto puro.
3. Arquivo adulterado é rejeitado pela etiqueta do GCM e depois pela validação de esquema; o app ignora os dados e oferece apagar.
4. Regra de projeto: se um LLM for integrado no futuro, ele não pode receber o texto livre sem isolamento (delimitação, sem ferramentas/ações, saída nunca executada) e nova revisão de segurança.

Fora do escopo: ataques adversariais por **imagem** (perturbações que enganam o classificador) e texto escrito dentro da foto. Não foram avaliados.

## Testes (`app/test/clinico_test.dart`, 28 testes no total do app, todos passando)
Sanitização; leitura estrita; regras do indicador (inclui casos-limite e "não influencia"); injeções de texto não alteram o indicador; JSON injetado continua texto após cifrar e ler; arquivo sem texto legível; nonce diferente a cada gravação; adulteração, truncamento e chave errada detectados; apagar remove arquivo e chave; fluxo de tela consentimento → formulário → indicador.

## Limites conhecidos
- Os testes usam chave em memória; o Android Keystore real **não foi exercitado em aparelho ou emulador** (a inferência nativa também ainda não foi testada em aparelho).
- Sem `FLAG_SECURE`: capturas de tela e miniaturas de apps recentes podem mostrar o formulário.
- Sem bloqueio por biometria/PIN do app, sem exportação cifrada e sem trilha de auditoria.
- Dispositivo com root ou desbloqueado e sem proteção de tela expõe os dados.
- Coletar, compartilhar ou publicar dados de pacientes em pesquisa exige TCLE e aprovação de CEP/CONEP, além de adequação à LGPD (dados sensíveis de saúde). O app não faz nada disso.
- O limiar de 3 semanas e as demais regras são da vigilância (definição de caso suspeito), não um instrumento de triagem validado com sensibilidade e especificidade medidas.
