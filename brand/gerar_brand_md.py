"""Gera BRAND.md a partir de paleta.json e contraste.json (números nunca digitados à mão)."""
import json
pal=json.load(open("paleta.json",encoding="utf-8")); con=json.load(open("contraste.json",encoding="utf-8"))
papel={"tinta":"Fundo escuro, texto principal sobre areia","floresta":"Cor de marca, botões, texto de destaque",
 "agua":"Anel da lente, acentos decorativos","agua_clara":"Colchetes e \"SCAN\" sobre fundo escuro",
 "areia":"Fundo claro padrão","areia_escura":"Bordas e divisores sobre areia","coral":"Lesão no símbolo (única cor quente)",
 "coral_claro":"Estados de destaque suaves","ambar":"Avisos e limitações (texto sobre areia)"}
L=["# DermSCAN: guia de identidade visual","",
"Gerado por `gerar_brand_md.py` a partir de `paleta.json` e `contraste.json`. Fonte única dos desenhos: `gerar_marca.py`.","",
"## Conceito","",
"O símbolo junta quatro ideias: colchetes de enquadramento (triagem visual), lente circular (campo dermatoscópico),",
"mancha coral (a lesão) e linha de varredura com rastro (SCAN). O nome combina *Derm* (peso 600, tinta ou areia) e *SCAN* (peso 800, floresta ou água clara).","",
"## Arquivos","",
"| Uso | Arquivo |","|---|---|",
"| Símbolo sobre fundo escuro | `svg/simbolo-escuro.svg` |","| Símbolo sobre fundo claro | `svg/simbolo-claro.svg` |",
"| Símbolo monocromático | `svg/simbolo-mono.svg`, `svg/simbolo-mono-branco.svg` |",
"| Logotipo (texto em curvas, não depende de fonte) | `svg/logotipo-claro.svg`, `svg/logotipo-escuro.svg` |",
"| Favicon | `svg/favicon.svg`, `png/favicon-32.png` |",
"| Ícone do app (legado, adaptativo, monocromático) | `png/icone-1024.png`, `png/icone-foreground-1024.png`, `png/icone-monocromatico-1024.png` |",
"| Splash nativa | `png/splash-simbolo-640.png`, `png/splash-android12-960.png` |",
"| Web (PWA, Apple, social) | `png/icone-192.png`, `png/icone-512.png`, `png/icone-maskable-512.png`, `png/apple-touch-icon-180.png`, `png/og-image-1200x630.png` |","",
"## Paleta","","| Token | Hex | Papel |","|---|---|---|"]
for k,v in pal.items(): L.append(f"| `{k}` | `{v}` | {papel.get(k,'')} |")
L+=["","## Contraste (WCAG 2.x)","","Mínimos: 4,5:1 para texto, 3:1 para gráficos e ícones. Razões calculadas por `gerar_marca.py`.","",
"| Par | Razão | Mínimo | Uso |","|---|---|---|---|"]
for c in con: L.append(f"| {c['par']} | {c['razao']:.2f}:1 | {c['minimo']}:1 | {c['uso']} |")
L+=["","Pares marcados como \"evitar\" ficam abaixo do mínimo e **não** devem carregar informação (só decoração).","",
"## Tipografia","","Sora (SIL OFL 1.1), pesos 400, 600, 700 e 800. Licença em `fontes/OFL-Sora.txt`. O site serve as fontes em woff2 do próprio domínio (sem CDN).","",
"## Regras de uso","",
"- Área de respiro mínima: metade da largura de um colchete ao redor do símbolo.",
"- Tamanho mínimo: símbolo com 24 px; logotipo com 120 px de largura.",
"- Não distorcer, girar, recolorir fora da paleta, nem aplicar sombra ou contorno.",
"- Fundo claro usa a variante `claro`; fundo escuro usa `escuro`; uma cor só usa `mono`.",
"- A mancha coral é a única cor quente da marca. Não use coral como cor de alerta clínico.","",
"## Regenerar","","```bash","python3 gerar_marca.py --fontes fontes --saida .   # SVGs, paleta.json, contraste.json","node exportar_png.js .                            # PNGs (requer playwright)","python3 gerar_brand_md.py                         # este arquivo","```",""]
open("BRAND.md","w",encoding="utf-8").write("\n".join(L)); print("BRAND.md ok",len(L),"linhas")
