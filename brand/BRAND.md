# DermSCAN: guia de identidade visual

Gerado por `gerar_brand_md.py` a partir de `paleta.json` e `contraste.json`. Fonte única dos desenhos: `gerar_marca.py`.

## Conceito

O símbolo junta quatro ideias: colchetes de enquadramento (triagem visual), lente circular (campo dermatoscópico),
mancha coral (a lesão) e linha de varredura com rastro (SCAN). O nome combina *Derm* (peso 600, tinta ou areia) e *SCAN* (peso 800, floresta ou água clara).

## Arquivos

| Uso | Arquivo |
|---|---|
| Símbolo sobre fundo escuro | `svg/simbolo-escuro.svg` |
| Símbolo sobre fundo claro | `svg/simbolo-claro.svg` |
| Símbolo monocromático | `svg/simbolo-mono.svg`, `svg/simbolo-mono-branco.svg` |
| Logotipo (texto em curvas, não depende de fonte) | `svg/logotipo-claro.svg`, `svg/logotipo-escuro.svg` |
| Favicon | `svg/favicon.svg`, `png/favicon-32.png` |
| Ícone do app (legado, adaptativo, monocromático) | `png/icone-1024.png`, `png/icone-foreground-1024.png`, `png/icone-monocromatico-1024.png` |
| Splash nativa | `png/splash-simbolo-640.png`, `png/splash-android12-960.png` |
| Web (PWA, Apple, social) | `png/icone-192.png`, `png/icone-512.png`, `png/icone-maskable-512.png`, `png/apple-touch-icon-180.png`, `png/og-image-1200x630.png` |

## Paleta

| Token | Hex | Papel |
|---|---|---|
| `tinta` | `#0A2E2C` | Fundo escuro, texto principal sobre areia |
| `floresta` | `#0F5F5A` | Cor de marca, botões, texto de destaque |
| `agua` | `#17A398` | Anel da lente, acentos decorativos |
| `agua_clara` | `#6FD3C7` | Colchetes e "SCAN" sobre fundo escuro |
| `areia` | `#F6F1EA` | Fundo claro padrão |
| `areia_escura` | `#E7DCCB` | Bordas e divisores sobre areia |
| `coral` | `#E8704A` | Lesão no símbolo (única cor quente) |
| `coral_claro` | `#F4A98F` | Estados de destaque suaves |
| `ambar` | `#8A4B08` | Avisos e limitações (texto sobre areia) |

## Contraste (WCAG 2.x)

Mínimos: 4,5:1 para texto, 3:1 para gráficos e ícones. Razões calculadas por `gerar_marca.py`.

| Par | Razão | Mínimo | Uso |
|---|---|---|---|
| texto tinta sobre areia | 12.98:1 | 4.5:1 | permitido |
| texto floresta sobre areia | 6.66:1 | 4.5:1 | permitido |
| texto branco sobre floresta (botão) | 7.49:1 | 4.5:1 | permitido |
| texto areia sobre tinta | 12.98:1 | 4.5:1 | permitido |
| texto água clara sobre tinta | 8.21:1 | 4.5:1 | permitido |
| texto âmbar sobre areia (aviso) | 6.05:1 | 4.5:1 | permitido |
| gráfico floresta sobre areia (barras, ícones) | 6.66:1 | 3.0:1 | permitido |
| gráfico coral sobre tinta (lesão na lente) | 4.76:1 | 3.0:1 | permitido |
| gráfico água clara sobre floresta | 4.21:1 | 3.0:1 | permitido |
| gráfico água sobre areia | 2.78:1 | 3.0:1 | evitar |
| gráfico coral sobre areia | 2.73:1 | 3.0:1 | evitar |

Pares marcados como "evitar" ficam abaixo do mínimo e **não** devem carregar informação (só decoração).

## Tipografia

Sora (SIL OFL 1.1), pesos 400, 600, 700 e 800. Licença em `fontes/OFL-Sora.txt`. O site serve as fontes em woff2 do próprio domínio (sem CDN).

## Regras de uso

- Área de respiro mínima: metade da largura de um colchete ao redor do símbolo.
- Tamanho mínimo: símbolo com 24 px; logotipo com 120 px de largura.
- Não distorcer, girar, recolorir fora da paleta, nem aplicar sombra ou contorno.
- Fundo claro usa a variante `claro`; fundo escuro usa `escuro`; uma cor só usa `mono`.
- A mancha coral é a única cor quente da marca. Não use coral como cor de alerta clínico.

## Regenerar

```bash
python3 gerar_marca.py --fontes fontes --saida .   # SVGs, paleta.json, contraste.json
node exportar_png.js .                            # PNGs (requer playwright)
python3 gerar_brand_md.py                         # este arquivo
```
