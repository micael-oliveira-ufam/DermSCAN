#!/usr/bin/env python3
"""Gera a identidade visual do DermSCAN: SVGs, paleta e verificação de contraste.

Tudo sai de uma única fonte de verdade (as constantes abaixo), para que o site, o app e os
ícones usem exatamente a mesma geometria e as mesmas cores.

Uso:  python3 gerar_marca.py --fontes fontes/ --saida .
Requer: fonttools (pip install fonttools).
"""
import argparse
import json
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# --------------------------------------------------------------------------- paleta
PALETA = {
    "tinta":       "#0A2E2C",  # fundo escuro, texto sobre claro
    "floresta":    "#0F5F5A",  # primária (botões com texto branco)
    "agua":        "#17A398",  # destaque gráfico (não usar como texto sobre claro)
    "agua_clara":  "#6FD3C7",  # detalhes sobre fundo escuro
    "areia":       "#F6F1EA",  # fundo claro
    "areia_escura": "#E7DCCB",  # bordas e superfícies sobre areia
    "coral":       "#E8704A",  # lesão (acento da marca)
    "coral_claro": "#F4A98F",
    "ambar":       "#8A4B08",  # avisos de texto sobre claro
}

# --------------------------------------------------------------------------- geometria
# Caixa 256x256. Todos os valores aqui são repetidos no app (lib/marca/simbolo.dart).
COLCHETES = [
    "M28 70V42Q28 28 42 28H70",
    "M186 28H214Q228 28 228 42V70",
    "M228 186V214Q228 228 214 228H186",
    "M70 228H42Q28 228 28 214V186",
]
COLCHETE_LARGURA = 14
LENTE = {"cx": 128, "cy": 128, "r": 64, "anel": 8}
LESAO = ("M96 126C94 106 118 98 134 104C152 110 162 126 156 142"
         "C150 158 128 166 112 158C100 152 97 140 96 126Z")
LINHA = {"x": 52, "y": 132, "w": 152, "h": 8}          # linha de varredura (estática)
RASTRO = {"x": 64, "y": 76, "w": 128, "h": 60}          # rastro acima da linha

VARIANTES = {
    # sobre fundo escuro
    "escuro": dict(colchete=PALETA["agua_clara"], lente=PALETA["floresta"], anel=PALETA["agua"],
                   lesao=PALETA["coral"], linha=PALETA["areia"], rastro=PALETA["agua_clara"]),
    # sobre fundo claro
    "claro": dict(colchete=PALETA["floresta"], lente=PALETA["tinta"], anel=PALETA["agua"],
                  lesao=PALETA["coral"], linha=PALETA["areia"], rastro=PALETA["agua_clara"]),
}


def simbolo_svg(v, uid="a", extra_defs=""):
    """Retorna os elementos SVG do símbolo (sem <svg>), na caixa 256x256."""
    L = LENTE
    colchetes = "".join(
        f'<path d="{d}" fill="none" stroke="{v["colchete"]}" stroke-width="{COLCHETE_LARGURA}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>' for d in COLCHETES)
    return (
        f'<defs>{extra_defs}'
        f'<clipPath id="lente-{uid}"><circle cx="{L["cx"]}" cy="{L["cy"]}" r="{L["r"]}"/></clipPath>'
        f'<linearGradient id="rastro-{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{v["rastro"]}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{v["rastro"]}" stop-opacity="0.5"/></linearGradient></defs>'
        f'{colchetes}'
        f'<circle cx="{L["cx"]}" cy="{L["cy"]}" r="{L["r"]}" fill="{v["lente"]}" '
        f'stroke="{v["anel"]}" stroke-width="{L["anel"]}"/>'
        f'<g clip-path="url(#lente-{uid})">'
        f'<path d="{LESAO}" fill="{v["lesao"]}"/>'
        f'<rect x="{RASTRO["x"]}" y="{RASTRO["y"]}" width="{RASTRO["w"]}" height="{RASTRO["h"]}" '
        f'fill="url(#rastro-{uid})"/></g>'
        f'<rect x="{LINHA["x"]}" y="{LINHA["y"]}" width="{LINHA["w"]}" height="{LINHA["h"]}" '
        f'rx="{LINHA["h"] // 2}" fill="{v["linha"]}"/>'
    )


def simbolo_mono_svg(cor="#000"):
    """Versão de uma cor só (ícone monocromático do Android, impressão)."""
    L = LENTE
    colchetes = "".join(
        f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="{COLCHETE_LARGURA}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>' for d in COLCHETES)
    return (
        f'{colchetes}'
        f'<circle cx="{L["cx"]}" cy="{L["cy"]}" r="{L["r"] - L["anel"] / 2}" fill="none" '
        f'stroke="{cor}" stroke-width="{L["anel"]}"/>'
        f'<path d="{LESAO}" fill="{cor}"/>'
        f'<rect x="{LINHA["x"]}" y="{LINHA["y"]}" width="{LINHA["w"]}" height="{LINHA["h"]}" '
        f'rx="{LINHA["h"] // 2}" fill="{cor}" stroke="none"/>'
    )


# --------------------------------------------------------------------------- logotipo
def texto_em_curvas(partes, tamanho):
    """partes: [(texto, ttf)]. Converte para um único <path> (y para baixo) e devolve (d, largura, altura_caps)."""
    x = 0.0
    comandos = []
    ymin, ymax = 1e9, -1e9
    for texto, fonte in partes:
        f = TTFont(fonte)
        gs = f.getGlyphSet()
        cmap = f.getBestCmap()
        upem = f["head"].unitsPerEm
        s = tamanho / upem
        for ch in texto:
            nome = cmap[ord(ch)]
            glifo = gs[nome]
            pen = SVGPathPen(gs)
            # y invertido: SVG cresce para baixo
            tp = TransformPen(pen, (s, 0, 0, -s, x, 0))
            glifo.draw(tp)
            comandos.append(pen.getCommands())
            bp = BoundsPen(gs)
            glifo.draw(bp)
            if bp.bounds:
                ymin = min(ymin, bp.bounds[1] * s)
                ymax = max(ymax, bp.bounds[3] * s)
            x += glifo.width * s
        x += 0  # sem espaçamento extra entre partes
    return " ".join(comandos), x, (ymin, ymax)


def logotipo_svg(fontes, variante, cor_texto, cor_scan, uid):
    v = VARIANTES[variante]
    d, largura, (ymin, ymax) = texto_em_curvas(
        [("Derm", fontes["600"]), ("SCAN", fontes["800"])], 100)
    altura_texto = ymax - ymin
    alvo = 120.0                                  # altura de caixa do símbolo (256 -> 120)
    escala_simbolo = alvo / 256
    escala_texto = 64 / altura_texto              # altura das maiúsculas ~ 64
    texto_x = alvo + 22
    texto_y = alvo / 2 + (altura_texto * escala_texto) / 2 + ymin * escala_texto  # centra verticalmente
    # cor da parte SCAN: separa os dois trechos
    d_derm, w_derm, _ = texto_em_curvas([("Derm", fontes["600"])], 100)
    d_scan_full, _, _ = texto_em_curvas([("Derm", fontes["600"]), ("SCAN", fontes["800"])], 100)
    d_scan, _, _ = texto_em_curvas([("SCAN", fontes["800"])], 100)
    larg_total = texto_x + largura * escala_texto + 6
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {larg_total:.1f} {alvo}" '
        f'role="img" aria-label="DermSCAN">'
        f'<g transform="scale({escala_simbolo})">{simbolo_svg(v, uid)}</g>'
        f'<g transform="translate({texto_x} {texto_y:.2f}) scale({escala_texto:.5f})">'
        f'<path d="{d_derm}" fill="{cor_texto}"/>'
        f'<path d="{d_scan}" transform="translate({w_derm:.2f} 0)" fill="{cor_scan}"/>'
        f'</g></svg>'
    )
    return svg, larg_total, alvo


# --------------------------------------------------------------------------- contraste
def lum(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


# (descrição, cor do primeiro plano, cor do fundo, mínimo WCAG 2.x, uso)
#   texto normal >= 4.5, elementos gráficos >= 3.0.
#   uso "evitar": combinação que NÃO atinge o mínimo e por isso está proibida no sistema visual.
PARES = [
    ("texto tinta sobre areia", "tinta", "areia", 4.5, "permitido"),
    ("texto floresta sobre areia", "floresta", "areia", 4.5, "permitido"),
    ("texto branco sobre floresta (botão)", "#FFFFFF", "floresta", 4.5, "permitido"),
    ("texto areia sobre tinta", "areia", "tinta", 4.5, "permitido"),
    ("texto água clara sobre tinta", "agua_clara", "tinta", 4.5, "permitido"),
    ("texto âmbar sobre areia (aviso)", "ambar", "areia", 4.5, "permitido"),
    ("gráfico floresta sobre areia (barras, ícones)", "floresta", "areia", 3.0, "permitido"),
    ("gráfico coral sobre tinta (lesão na lente)", "coral", "tinta", 3.0, "permitido"),
    ("gráfico água clara sobre floresta", "agua_clara", "floresta", 3.0, "permitido"),
    ("gráfico água sobre areia", "agua", "areia", 3.0, "evitar"),
    ("gráfico coral sobre areia", "coral", "areia", 3.0, "evitar"),
]


def verificar_contraste():
    linhas = []
    for nome, fg, bg, minimo, uso in PARES:
        cf = PALETA.get(fg, fg)
        cb = PALETA.get(bg, bg)
        r = contraste(cf, cb)
        atinge = r >= minimo
        # "permitido" precisa atingir o mínimo; "evitar" documenta uma combinação que não atinge
        linhas.append({"par": nome, "fg": cf, "bg": cb, "razao": round(r, 2), "minimo": minimo,
                       "uso": uso, "atinge_minimo": atinge,
                       "ok": atinge if uso == "permitido" else (not atinge)})
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fontes", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    fontes = {w: str(next(Path(a.fontes).glob(f"Sora_{w}*.ttf"))) for w in ("400", "600", "700", "800")}
    out = Path(a.saida)
    svg_dir = out / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    def caixa(inner, bg=None):
        fundo = f'<rect width="256" height="256" fill="{bg}"/>' if bg else ""
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">{fundo}{inner}</svg>'

    (svg_dir / "simbolo-escuro.svg").write_text(caixa(simbolo_svg(VARIANTES["escuro"], "e")), encoding="utf-8")
    (svg_dir / "simbolo-claro.svg").write_text(caixa(simbolo_svg(VARIANTES["claro"], "c")), encoding="utf-8")
    (svg_dir / "simbolo-mono.svg").write_text(caixa(simbolo_mono_svg("#000000")), encoding="utf-8")
    (svg_dir / "simbolo-mono-branco.svg").write_text(caixa(simbolo_mono_svg("#FFFFFF")), encoding="utf-8")

    # favicon: símbolo sobre quadrado arredondado escuro, sem texto
    fav = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
           f'<rect width="256" height="256" rx="56" fill="{PALETA["tinta"]}"/>'
           f'<g transform="translate(28 28) scale(0.78125)">{simbolo_svg(VARIANTES["escuro"], "f")}</g></svg>')
    (svg_dir / "favicon.svg").write_text(fav, encoding="utf-8")

    sl, w, h = logotipo_svg(fontes, "claro", PALETA["tinta"], PALETA["floresta"], "l")
    se, _, _ = logotipo_svg(fontes, "escuro", PALETA["areia"], PALETA["agua_clara"], "d")
    (svg_dir / "logotipo-claro.svg").write_text(sl, encoding="utf-8")
    (svg_dir / "logotipo-escuro.svg").write_text(se, encoding="utf-8")

    (out / "paleta.json").write_text(json.dumps(PALETA, indent=2, ensure_ascii=False), encoding="utf-8")
    cont = verificar_contraste()
    (out / "contraste.json").write_text(json.dumps(cont, indent=2, ensure_ascii=False), encoding="utf-8")
    falhas = [c for c in cont if not c["ok"]]
    for c in cont:
        marca = "OK   " if c["ok"] else "FALHA"
        print(f'{marca} {c["razao"]:5.2f} (mín {c["minimo"]}) [{c["uso"]}] {c["par"]}')
    print(f"logotipo: {w:.1f} x {h:.0f}")
    if falhas:
        raise SystemExit(f"{len(falhas)} par(es) de cor abaixo do mínimo")


if __name__ == "__main__":
    main()
