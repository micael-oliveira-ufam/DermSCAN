"""Monta o pacote de treino a partir do manifesto do atlas (atlas_out/manifest.csv).

Regras (todas explícitas):
  1. Só entram imagens com tipo_imagem_heuristica == 'clínica'.
  2. Classe = mapeamento do subgrupo (ver DD_MAP e LEISH_MAP). Subgrupo 'Sem forma identificada'
     e seções visceral, pré-textual, capítulos 1-2 e caso clínico ficam fora (excluídas, com motivo).
  3. Classes com menos de MIN_CLASSE imagens são agrupadas em 'outras_dermatoses',
     exceto as classes de interesse do projeto (LEISH_E_ESPORO), que são mantidas mesmo pequenas.
  4. Split 70/15/15 estratificado por classe, agrupado por página (imagens da mesma página
     ficam no mesmo conjunto). Semente fixa.
  5. Conversão para JPEG qualidade 95 (JPX do PDF original já é com perda; ver README).
  6. Histopatologia não entra no treino; fica em excluidas/histopatologia/ para uso separado.

Saída: pacote/ (pronto para zipar) e pacote/manifest.csv.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold

BASE = Path(__file__).resolve().parent
ATLAS = BASE / "atlas_out"
PACOTE = BASE / "pacote"
SEED = 42
MIN_CLASSE = 20
JPEG_Q = 95
LEISH_E_ESPORO = {"leish_cutanea_ulcera", "leish_cutanea_outras_formas", "leish_mucosa", "esporotricose"}

# subgrupo de diagnóstico diferencial (nome já em português, conforme manifest) -> classe
DD_MAP = {
    "Esporotricose": "esporotricose",
    "Hanseníase": "hanseniase", "Hanseníase lepromatosa": "hanseniase",
    "Paracoccidioidomicose": "paracoccidioidomicose",
    "Carcinoma basocelular": "carcinoma_basocelular",
    "Carcinoma espinocelular": "carcinoma_espinocelular",
    "Carcinoma espinocelular - doença de Bowen": "carcinoma_espinocelular",
    "Úlceras venosas": "ulceras_vasculares", "Úlceras arteriais": "ulceras_vasculares",
    "Úlceras vasculares mistas": "ulceras_vasculares", "Infecções em úlceras vasculares": "ulceras_vasculares",
    "Úlceras bacterianas": "ulceras_bacterianas",
    "Cromoblastomicose": "cromoblastomicose",
    "Lobomicose": "lobomicose",
    "Histoplasmose": "histoplasmose", "Histoplasmose disseminada associada à AIDS": "histoplasmose",
    "Escrofuloderma": "tuberculose_e_micobacterioses", "Tuberculose cutânea": "tuberculose_e_micobacterioses",
    "Tuberculose cutânea - lúpus vulgar": "tuberculose_e_micobacterioses", "Lúpus vulgar": "tuberculose_e_micobacterioses",
    "Tuberculose dos orifícios": "tuberculose_e_micobacterioses", "Tuberculide papulonecrótica": "tuberculose_e_micobacterioses",
    "Micobactérias atípicas": "tuberculose_e_micobacterioses", "Tuberculose verrucosa": "tuberculose_e_micobacterioses",
    "Linfoma cutâneo": "linfomas", "Linfocitoma cutâneo": "linfomas", "Tumor linfoide": "linfomas",
    "Linfoma de linha média": "linfomas", "Linfoma angiocêntrico": "linfomas",
    "Pioderma gangrenoso": "outras_dermatoses", "Psoríase": "outras_dermatoses", "Sarcoidose cutânea": "outras_dermatoses",
    "Úlceras traumáticas": "outras_dermatoses", "Picadas de inseto": "outras_dermatoses",
    "Granuloma facial": "outras_dermatoses", "Ceratoacantoma": "outras_dermatoses", "Escleroma nasal": "outras_dermatoses",
    "Rinoescleroma": "outras_dermatoses", "Rinosporidiose": "outras_dermatoses", "Rinoentomoftoromicose": "outras_dermatoses",
    "Anemia falciforme": "outras_dermatoses", "Discoid lupus": "outras_dermatoses",
}
# seções de leishmaniose: subgrupo de forma de lesão -> classe
LEISH_GRUPOS = {
    "Leishmaniose cutânea localizada", "Leishmaniose cutânea disseminada", "Leishmaniose cutânea difusa",
    "Leishmaniose cutânea atípica", "Leishmaniose cutânea crônica recidivante",
}
LEISH_MUCOSA_GRUPO = "Leishmaniose mucosa - manifestações clínicas"
EXCLUIR_GRUPOS = {"Leishmaniose visceral", "Leishmaniose dérmica pós-calazar e para-calazar", "Caso clínico",
                  "Capítulo 1 - Visão geral", "Capítulo 2 - Imunopatogênese", "Pré-textual (capa, índice, prefácio)",
                  "Leishmaniose cutânea - introdução", "Leishmaniose mucosa - definição"}


def classe_de(grupo: str, subgrupo: str, tipo: str) -> tuple[str | None, str]:
    if tipo != "clínica":
        return None, "histopatologia/microscopia (fora do treino)"
    if subgrupo in DD_MAP:
        return DD_MAP[subgrupo], "diagnóstico diferencial"
    if subgrupo == "Sem forma identificada" or subgrupo == "Sem cabeçalho":
        return None, "forma de lesão não identificada"
    if grupo in EXCLUIR_GRUPOS:
        return None, f"grupo fora do escopo de classificação de pele ({grupo})"
    if grupo in LEISH_GRUPOS:
        return ("leish_cutanea_ulcera" if subgrupo == "úlcera" else "leish_cutanea_outras_formas"), "leishmaniose cutânea"
    if grupo == LEISH_MUCOSA_GRUPO:
        return "leish_mucosa", "leishmaniose mucosa"
    return None, f"sem regra ({grupo} | {subgrupo})"


def main() -> None:
    rows = list(csv.DictReader((ATLAS / "manifest.csv").open(encoding="utf-8")))
    atribuidas, excluidas = [], []
    for r in rows:
        cls, motivo = classe_de(r["grupo"], r["subgrupo"], r["tipo_imagem_heuristica"])
        (atribuidas if cls else excluidas).append((r, cls, motivo))

    # agrupa classes pequenas
    cont = Counter(c for _, c, _ in atribuidas)
    final = []
    for r, cls, motivo in atribuidas:
        if cont[cls] < MIN_CLASSE and cls not in LEISH_E_ESPORO:
            cls = "outras_dermatoses"
        final.append((r, cls, motivo))
    cont = Counter(c for _, c, _ in final)

    # split por página, estratificado por classe
    y = np.array([c for _, c, _ in final])
    grupos = np.array([int(r["pagina_pdf"]) for r, _, _ in final])
    idx_all = np.arange(len(final))
    sgkf = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=SEED)
    tr_val_idx, test_idx = next(sgkf.split(idx_all, y, grupos))
    sgkf2 = StratifiedGroupKFold(n_splits=6, shuffle=True, random_state=SEED)
    tr_i, val_i = next(sgkf2.split(tr_val_idx, y[tr_val_idx], grupos[tr_val_idx]))
    split = {}
    for i in tr_val_idx[tr_i]: split[i] = "train"
    for i in tr_val_idx[val_i]: split[i] = "val"
    for i in test_idx: split[i] = "test"

    if PACOTE.exists():
        shutil.rmtree(PACOTE)
    PACOTE.mkdir(parents=True)

    manifest = []
    for i, (r, cls, motivo) in enumerate(final):
        src = ATLAS / r["arquivo"]
        nome = Path(r["arquivo"]).stem + ".jpg"
        im = Image.open(src).convert("RGB")
        destino = PACOTE / split[i] / cls / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        im.save(destino, "JPEG", quality=JPEG_Q, subsampling=0)
        manifest.append({
            "arquivo": str(destino.relative_to(PACOTE)), "classe": cls, "split": split[i],
            "pagina_pdf": r["pagina_pdf"], "pagina_impressa": r["pagina_impressa"],
            "grupo_original": r["grupo"], "subgrupo_original": r["subgrupo"],
            "figuras_na_pagina": r["figuras_na_pagina"], "tipo": r["tipo_imagem_heuristica"],
            "largura": im.width, "altura": im.height, "origem_png": r["arquivo"],
        })

    for r, cls, motivo in excluidas:
        src = ATLAS / r["arquivo"]
        sub = "histopatologia" if r["tipo_imagem_heuristica"] != "clínica" else "nao_classificadas"
        destino = PACOTE / "excluidas" / sub / (Path(r["arquivo"]).stem + ".jpg")
        destino.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGB").save(destino, "JPEG", quality=JPEG_Q, subsampling=0)
        manifest.append({
            "arquivo": str(destino.relative_to(PACOTE)), "classe": "", "split": "excluida",
            "pagina_pdf": r["pagina_pdf"], "pagina_impressa": r["pagina_impressa"],
            "grupo_original": r["grupo"], "subgrupo_original": r["subgrupo"],
            "figuras_na_pagina": r["figuras_na_pagina"], "tipo": r["tipo_imagem_heuristica"],
            "largura": r["largura"], "altura": r["altura"], "origem_png": r["arquivo"],
        })

    with (PACOTE / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)

    contagem = defaultdict(lambda: Counter())
    for m in manifest:
        if m["split"] != "excluida":
            contagem[m["classe"]][m["split"]] += 1
    resumo = {
        "semente": SEED, "min_classe": MIN_CLASSE, "jpeg_qualidade": JPEG_Q,
        "imagens_no_treino_total": len(final),
        "excluidas": Counter(m for _, _, m in excluidas),
        "classes": {c: {"train": contagem[c]["train"], "val": contagem[c]["val"], "test": contagem[c]["test"],
                        "total": cont[c]} for c in sorted(contagem)},
    }
    (PACOTE / "classes.json").write_text(json.dumps(
        {**resumo, "excluidas": dict(resumo["excluidas"])}, ensure_ascii=False, indent=2), encoding="utf-8")

    # checksums
    linhas = []
    for p in sorted(PACOTE.rglob("*.jpg")):
        linhas.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(PACOTE)}")
    (PACOTE / "SHA256SUMS.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in resumo.items() if k != "classes"}, ensure_ascii=False, indent=2, default=dict))
    for c, v in resumo["classes"].items():
        print(f"{c:32s} train={v['train']:4d} val={v['val']:4d} test={v['test']:4d} total={v['total']:4d}")


if __name__ == "__main__":
    main()
