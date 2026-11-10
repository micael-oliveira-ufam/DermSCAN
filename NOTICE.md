# Avisos, atribuições e termos

## Código
Licença MIT (`LICENSE`). Cobre apenas o código-fonte.

## Pesos do modelo (`docs/model/vit_b16_int8.onnx`)
Os pesos foram treinados com imagens do **Atlas Interativo de Leishmaniose nas Américas** (OPAS/OMS, 2020),
disponibilizado sob **CC BY-NC-SA 3.0 IGO** (atribuição, uso não comercial, compartilhamento pela mesma licença).

Se os pesos contam como obra derivada dessas imagens é uma questão jurídica em aberto, e **não é um parecer
jurídico**. Por precaução, os pesos são disponibilizados **somente para pesquisa e uso não comercial**, sob os
mesmos termos da CC BY-NC-SA 3.0 IGO (https://creativecommons.org/licenses/by-nc-sa/3.0/igo/), com atribuição à OPAS
como fonte dos dados de treino. Isto não é endosso: a OPAS/OMS não endossa este projeto, seus resultados nem o modelo.
As imagens do atlas **não** são distribuídas neste repositório, e o `.gitignore` as exclui.

## Marca (`brand/`)
O nome DermSCAN e os arquivos de identidade visual não estão cobertos pela licença MIT. Ver `brand/BRAND.md`.

## Componentes de terceiros
| Componente | Uso | Licença |
|---|---|---|
| Sora (The Sora Project Authors) | tipografia do site e do app | SIL OFL 1.1 (`brand/fontes/OFL-Sora.txt`) |
| onnxruntime-web 1.24.2 | inferência no navegador (`docs/vendor/`) | MIT |
| onnxruntime (plugin Flutter 1.4.1) | inferência no Android | MIT |
| ViT-B/16 (torchvision, pesos ImageNet) | modelo-base | BSD-3-Clause (código); pesos ImageNet sujeitos aos termos do ImageNet |
| Flutter e pacotes pub (image, image_picker) | app | BSD-3-Clause / Apache-2.0, conforme cada pacote |

## Uso clínico
O DermSCAN é uma ferramenta de apoio à pesquisa. Não é dispositivo médico, não foi validado clinicamente e não
deve ser usado para diagnóstico ou decisão de tratamento.
