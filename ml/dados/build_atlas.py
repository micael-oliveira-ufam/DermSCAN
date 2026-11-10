"""Classifica as imagens extraídas do Atlas Interativo de Leishmaniose nas Américas (OPAS, 2020).

Entradas (scratchpad):
  atlas.pdf           cópia do PDF enviado pelo usuário
  imglist.txt         saída de `pdfimages -list atlas.pdf`
  raw/img-NNN.png     saída de `pdfimages -png atlas.pdf raw/img`
  full.txt            saída de `pdftotext -layout atlas.pdf full.txt` (páginas separadas por \f)

Saídas (atlas_out/):
  imagens/<grupo>/<subgrupo>/<pagina_pdf>_<objid>.png
  manifest.csv        uma linha por imagem exportada
  resumo.json         contagens por grupo e subgrupo, com parâmetros usados

Regras, todas explícitas e reproduzíveis:
  1. Página impressa = página PDF - 32 (verificado: PDF 295 = impressa 263, seção Sporotrichosis).
  2. Grupo = intervalo de páginas impressas do índice (TOC) do próprio atlas.
  3. Subgrupo:
       - Diagnóstico diferencial: cabeçalho corrente da página (ex.: "Sporotrichosis").
       - Capítulos de leishmaniose: forma de lesão inferida por palavras-chave nas legendas da página
         (heurística, não é classificação clínica validada).
  4. Filtro de imagem: min(largura, altura) >= 200 px e área >= 60.000 px. Ícones e
     faixas decorativas ficam de fora.
  5. Deduplicação pelo object ID do PDF (a mesma imagem aparece em várias páginas).
  6. Legendas: todas as menções "Figura X.YYY" da página são registradas, mas a associação
     imagem -> figura é por página, pois o PDF não preserva essa ligação.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "atlas_out"
IMG_OUT = OUT / "imagens"
OFFSET = 32  # página PDF - página impressa
MIN_SIDE = 200
MIN_AREA = 60_000

# (inicio_impressa, fim_impressa, grupo, subgrupo_padrao_ou_None)
# None = subgrupo vem do cabeçalho corrente (dif. diagnóstico) ou das palavras-chave (leishmaniose)
SECOES = [
    (1, 81, "Capítulo 1 - Visão geral", None),
    (-999, 0, "Pré-textual (capa, índice, prefácio)", None),
    (82, 99, "Capítulo 2 - Imunopatogênese", None),
    (100, 101, "Leishmaniose cutânea - introdução", None),
    (102, 175, "Leishmaniose cutânea localizada", None),
    (176, 181, "Leishmaniose cutânea localizada", "Diagnóstico laboratorial e tratamento"),
    (182, 189, "Leishmaniose cutânea disseminada", None),
    (190, 197, "Leishmaniose cutânea difusa", None),
    (198, 199, "Leishmaniose cutânea atípica", None),
    (200, 220, "Leishmaniose cutânea crônica recidivante", None),
    (221, 228, "Diagnóstico diferencial - geral", None),
    (229, 288, "Diagnóstico diferencial - infecções", None),
    (289, 324, "Diagnóstico diferencial - inflamatórias e reativas", None),
    (325, 355, "Diagnóstico diferencial - neoplasias malignas", None),
    (356, 359, "Leishmaniose mucosa - definição", None),
    (360, 436, "Leishmaniose mucosa - manifestações clínicas", None),
    (437, 442, "Leishmaniose mucosa - diagnóstico, tratamento e seguimento", None),
    (443, 492, "Leishmaniose mucosa - diagnóstico diferencial", None),
    (493, 520, "Leishmaniose visceral", None),
    (521, 525, "Leishmaniose dérmica pós-calazar e para-calazar", None),
    (526, 532, "Caso clínico", None),
    (533, 9999, "Apêndice", None),
]

# páginas de diagnóstico diferencial (subgrupo = cabeçalho corrente, traduzido quando conhecido)
DD_INTERVALOS = [(221, 355), (443, 492)]
TRADUCAO = {
    "Sporotrichosis": "Esporotricose", "Leprosy": "Hanseníase", "Lepromatous leprosy": "Hanseníase lepromatosa",
    "Paracoccidioidomycosis": "Paracoccidioidomicose", "Paracoccidiodomycosis": "Paracoccidioidomicose",
    "Histoplasmosis": "Histoplasmose", "AIDS-associated disseminated histoplasmosis": "Histoplasmose disseminada associada à AIDS",
    "Chromomycosis": "Cromoblastomicose", "Lobomycosis": "Lobomicose", "Bacterial ulcers": "Úlceras bacterianas",
    "Atypical mycobacteria": "Micobactérias atípicas", "Cutaneous tuberculosis": "Tuberculose cutânea",
    "Cutaneous tuberculosis - lupus vulgaris": "Tuberculose cutânea - lúpus vulgar", "Lupus vulgaris": "Lúpus vulgar",
    "Cutaneous tuberculosis of the orifices": "Tuberculose dos orifícios", "Tuberculosis of the orifices": "Tuberculose dos orifícios",
    "Scrofuloderma": "Escrofuloderma", "Scrofuloderma - tuberculosis": "Escrofuloderma",
    "Papulonecrotic tuberculid": "Tuberculide papulonecrótica", "Verrucous tuberculosis": "Tuberculose verrucosa",
    "Basal cell carcinoma": "Carcinoma basocelular", "Squamous cell carcinoma": "Carcinoma espinocelular",
    "Squamous cell carcinoma - Bowen’s disease": "Carcinoma espinocelular - doença de Bowen",
    "Cutaneous lymphoma": "Linfoma cutâneo", "Keratoacanthoma": "Ceratoacantoma", "Lymphocytoma cutis": "Linfocitoma cutâneo",
    "Venous ulcers": "Úlceras venosas", "Arterial ulcers": "Úlceras arteriais", "Mixed vascular ulcers": "Úlceras vasculares mistas",
    "Infections in vascular ulcers": "Infecções em úlceras vasculares", "Infecciones en úlceras vasculares": "Infecções em úlceras vasculares",
    "Cutaneous sarcoidosis": "Sarcoidose cutânea", "Discoid lupus": "Lúpus discoide", "Psoriasis": "Psoríase",
    "Pyoderma gangrenosum": "Pioderma gangrenoso", "Traumatic ulcers": "Úlceras traumáticas", "Insect bites": "Picadas de inseto",
    "Granuloma faciale": "Granuloma facial", "Anemia de células falciformes": "Anemia falciforme",
    "Rhinoscleroma": "Rinoescleroma", "Nasal scleroma": "Escleroma nasal", "Rhinosporidiosis": "Rinosporidiose",
    "Rhinoentomophthoromycosis": "Rinoentomoftoromicose", "Granulomatosis with polyangiitis": "Granulomatose com poliangeíte",
    "Angiocentric lymphoma": "Linfoma angiocêntrico", "Midline lymphoma": "Linfoma de linha média", "Lymphoma": "Linfoma",
    "Lymphoid tumor": "Tumor linfoide", "Adenoma": "Adenoma", "Nasal biopsy of the previous patient": "Biópsia nasal (paciente anterior)",
}
# ordem de prioridade para a forma principal da lesão
PRIORIDADE = ["úlcera", "nódulo", "placa", "pápula", "verrucosa", "lupoide", "crosta/escama", "cicatriz", "linfangítica", "mucosa/nasal", "orelha/face"]

# palavras-chave em inglês (legendas do atlas) -> forma de lesão
KEYWORDS = [
    ("úlcera", r"\bulcer"),
    ("nódulo", r"\bnodul"),
    ("pápula", r"\bpapul"),
    ("placa", r"\bplaque"),
    ("verrucosa", r"verrucous|warty|verruc"),
    ("lupoide", r"lupoid"),
    ("crosta/escama", r"\bcrust|\bscab|\bscale"),
    ("cicatriz", r"\bscar"),
    ("linfangítica", r"lymphangit"),
    ("mucosa/nasal", r"\bnasal|\bnose|\blip\b|palate|mucos|larynx|pharynx"),
    ("orelha/face", r"\bear\b|auricle|\bface\b|facial|nose"),
]

FIG_RE = re.compile(r"Figures?\s+(\d\.\d{1,3}[A-Z]?)")
SPECIES_RE = re.compile(r"Leishmania\s*\(\s*[A-Za-z]+\.?\s*\)\s*[a-z]+|Leishmania\s+[a-z]+")


def secao_por_pagina_impressa(p: int):
    for ini, fim, grupo, sub in SECOES:
        if ini <= p <= fim:
            return grupo, sub
    return "Sem seção", None


def cabecalho_corrente(texto: str) -> str | None:
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    # linha 0 é a barra "Index ... Appendix"; a seguinte é o cabeçalho quando for texto curto
    for l in linhas[1:3]:
        if l.startswith("Figure") or l.startswith("Figures"):
            return None
        titulo = l.split(". ")[0].strip().rstrip(".")
        if titulo and len(titulo) <= 60 and not re.search(r"\d", titulo) and not titulo.startswith("Figure"):
            return titulo
    return None


def texto_das_legendas(texto: str) -> str:
    """Só o texto de legenda: a linha 'Figure...' e até 4 linhas seguintes, parando na próxima legenda."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    trechos, i = [], 0
    while i < len(linhas):
        if re.match(r"Figures?\s+\d\.\d", linhas[i]):
            bloco = [linhas[i]]
            j = i + 1
            while j < len(linhas) and j - i <= 4 and not re.match(r"Figures?\s+\d\.\d", linhas[j]):
                bloco.append(linhas[j]); j += 1
            trechos.append(" ".join(bloco))
            i = j
        else:
            i += 1
    return " ".join(trechos)


def formas_lesao(legendas: str) -> list[str]:
    achados = []
    low = legendas.lower()
    for nome, padrao in KEYWORDS:
        if re.search(padrao, low):
            achados.append(nome)
    return achados


def main() -> None:
    paginas = (BASE / "full.txt").read_text(encoding="utf-8", errors="replace").split("\f")

    registros = []
    linhas = (BASE / "imglist.txt").read_text(encoding="utf-8", errors="replace").splitlines()[2:]
    for ln in linhas:
        cols = ln.split()
        if len(cols) < 15:
            continue
        pdf_pag, num, _tipo, w, h = int(cols[0]), int(cols[1]), cols[2], int(cols[3]), int(cols[4])
        objid = cols[10]
        if min(w, h) < MIN_SIDE or w * h < MIN_AREA:
            continue
        registros.append({"pdf_pag": pdf_pag, "num": num, "w": w, "h": h, "objid": objid})

    # deduplicação pelo object ID
    vistos = set()
    unicos = []
    for r in registros:
        if r["objid"] in vistos:
            continue
        vistos.add(r["objid"])
        unicos.append(r)

    if IMG_OUT.exists():
        shutil.rmtree(IMG_OUT)
    IMG_OUT.mkdir(parents=True)

    manifest = []
    contagem = Counter()
    ausentes = []
    for r in unicos:
        pdf_pag = r["pdf_pag"]
        impressa = pdf_pag - OFFSET
        texto = paginas[pdf_pag - 1] if pdf_pag - 1 < len(paginas) else ""
        grupo, sub_fixo = secao_por_pagina_impressa(impressa)

        formas = []
        if any(a <= impressa <= b for a, b in DD_INTERVALOS):
            titulo = cabecalho_corrente(texto) or "Sem cabeçalho"
            sub = TRADUCAO.get(titulo, titulo)
        elif sub_fixo:
            sub = sub_fixo
        else:
            formas = formas_lesao(texto_das_legendas(texto))
            principal = next((f for f in PRIORIDADE if f in formas), None)
            sub = principal if principal else "Sem forma identificada"

        legenda = texto_das_legendas(texto).lower()
        tipo = "histopatologia/microscopia" if re.search(r"hematoxylin|eosin|stain|histolog|biops|microscop|granuloma|x\)|\d+x\b|culture|smear", legenda) else "clínica"
        figs = sorted(set(FIG_RE.findall(texto)))
        especies = sorted(set(SPECIES_RE.findall(texto)))

        origem = RAW_DIR / f"img-{r['num']:03d}.png"
        if not origem.exists():
            origem = RAW_DIR / f"img-{r['num']:04d}.png"
        if not origem.exists():
            ausentes.append(r)
            continue

        pasta = IMG_OUT / re.sub(r"[^\w\- ]", "", grupo) / re.sub(r"[^\w\- ]", "", sub.replace("/", "-"))
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"p{pdf_pag:03d}_{r['objid']}.png"
        shutil.copy2(origem, destino)
        sha = hashlib.sha256(destino.read_bytes()).hexdigest()

        contagem[(grupo, sub)] += 1
        manifest.append({
            "arquivo": str(destino.relative_to(OUT)),
            "pagina_pdf": pdf_pag,
            "pagina_impressa": impressa,
            "grupo": grupo,
            "subgrupo": sub,
            "formas_mencionadas_na_pagina": "; ".join(formas),
            "tipo_imagem_heuristica": tipo,
            "figuras_na_pagina": "; ".join(figs),
            "especies_mencionadas": "; ".join(especies),
            "largura": r["w"],
            "altura": r["h"],
            "objid_pdf": r["objid"],
            "sha256": sha,
        })

    OUT.mkdir(exist_ok=True)
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    resumo = {
        "parametros": {
            "offset_pagina": OFFSET, "min_lado_px": MIN_SIDE, "min_area_px": MIN_AREA,
            "dedup": "objid_pdf",
        },
        "imagens_com_registro_no_pdf": len(registros),
        "imagens_unicas_apos_filtro": len(unicos),
        "imagens_exportadas": len(manifest),
        "imagens_sem_arquivo_extraido": len(ausentes),
        "por_grupo_subgrupo": {f"{g} | {s}": n for (g, s), n in sorted(contagem.items())},
    }
    (OUT / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumo.items() if k != "por_grupo_subgrupo"}, ensure_ascii=False, indent=2))


RAW_DIR = BASE / "raw"

if __name__ == "__main__":
    main()
