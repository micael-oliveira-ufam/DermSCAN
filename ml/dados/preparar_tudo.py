"""Prepara os dados do treino em outra máquina: valida o atlas, baixa e processa o PAD-UFES-20 e
gera um manifesto mesclado (atlas + PAD). NÃO inclui imagens do atlas: elas devem existir localmente.

Uso:
  python3 preparar_tudo.py --atlas /caminho/pacote [--trabalho ./dados_treino] [--pular-download]

  --atlas        pasta com manifest.csv e train/, val/, test/ (pacote gerado a partir do PDF do atlas)
  --trabalho     pasta de saída (PAD e manifesto mesclado)
  --pular-download  usa um PAD já processado em <trabalho>/pad (sem baixar de novo)

Saídas em <trabalho>:
  pad/manifesto_pad.csv, pad/imgs/...        (PAD-UFES-20 mapeado e reduzido)
  manifesto_mesclado.csv                     (todas as imagens de treino, com origem e grupo)
  resumo_mesclagem.json                      (contagens, hashes, verificações)
"""
import argparse, csv, hashlib, json, os, subprocess, sys
from collections import Counter
from pathlib import Path

HASH_ATLAS_ESPERADO = "50839b9fb00384727f1eb8fd0e46571b91474c28ff0b032b3e4ce840d0b5aab1"
CONTAGEM_ATLAS_ESPERADA = {"train": 447, "val": 90, "test": 89}  # do treino original
AQUI = Path(__file__).resolve().parent


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""): h.update(bloco)
    return h.hexdigest()


def validar_atlas(pacote: Path, log) -> dict:
    manifesto = pacote / "manifest.csv"
    if not manifesto.exists(): raise SystemExit(f"não achei {manifesto}")
    h = sha256(manifesto)
    if h != HASH_ATLAS_ESPERADO:
        log(f"AVISO: manifest.csv do atlas tem hash diferente do treino original ({h[:12]}…). Verifique o pacote.")
    linhas = [r for r in csv.DictReader(open(manifesto, encoding="utf-8")) if r["split"] in CONTAGEM_ATLAS_ESPERADA]
    cont = Counter(r["split"] for r in linhas)
    faltando = [r["arquivo"] for r in linhas if not (pacote / r["arquivo"]).exists()]
    if faltando:
        raise SystemExit(f"{len(faltando)} imagens do atlas não encontradas, ex.: {faltando[:3]}")
    if dict(cont) != CONTAGEM_ATLAS_ESPERADA:
        log(f"AVISO: contagem por split {dict(cont)} difere da original {CONTAGEM_ATLAS_ESPERADA}")
    log(f"atlas ok: {dict(cont)}, todas as imagens presentes")
    return {"hash_manifest_atlas": h, "contagem": dict(cont), "linhas": linhas}


def preparar_pad(trabalho: Path, pular: bool, log) -> Path:
    destino = trabalho / "pad"
    if pular:
        if not (destino / "manifesto_pad.csv").exists(): raise SystemExit("--pular-download, mas não há PAD processado")
        log("PAD: usando processamento existente (sem baixar)")
        return destino
    destino.mkdir(parents=True, exist_ok=True)
    # o preparar_pad.py precisa do metadata.csv na pasta de saída; baixa-o do Mendeley
    import urllib.request
    meta = destino / "metadata.csv"
    if not meta.exists():
        url = "https://data.mendeley.com/public-files/datasets/zr7vgbcyr2/files/fa850265-57da-48f0-ba3e-998b3e44b1f6/file_downloaded"
        log("baixando metadata.csv do PAD-UFES-20")
        urllib.request.urlretrieve(url, meta)
    log("baixando e processando os 3 zips do PAD-UFES-20 (≈3,6 GB, um por vez)")
    subprocess.run([sys.executable, str(AQUI / "preparar_pad.py"), str(destino)], check=True)
    return destino


def checar_mapeamento_pad(pad: Path) -> dict:
    """Recusa um PAD processado com o mapeamento antigo (ACK/SEK/NEV agrupados em outras_dermatoses)."""
    info = json.load(open(pad / "mapeamento_pad.json", encoding="utf-8"))
    mapa = info["mapa"]
    individuais = {mapa.get(k) for k in ("ACK", "SEK", "NEV")}
    if info.get("versao_mapeamento") != 2 or len(individuais) != 3 or "outras_dermatoses" in individuais:
        raise SystemExit("PAD processado com o mapeamento ANTIGO (ACK/SEK/NEV em outras_dermatoses). "
                         "Apague a pasta pad/ do diretório de trabalho e rode de novo, ou use o PAD-UFES-20-processado.tar.gz novo.")
    cabecalho = open(pad / "manifesto_pad.csv", encoding="utf-8").readline().strip().split(",")
    if "classe" not in cabecalho:
        raise SystemExit("manifesto_pad.csv no formato antigo (coluna 'classe_atlas'); regenere o PAD.")
    return mapa


def mesclar(atlas_info: dict, pad: Path, pacote: Path, trabalho: Path, log) -> dict:
    mapa_pad = checar_mapeamento_pad(pad)
    saida = trabalho / "manifesto_mesclado.csv"
    linhas_pad = list(csv.DictReader(open(pad / "manifesto_pad.csv", encoding="utf-8")))
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["caminho", "classe", "origem", "split", "grupo"])
        for r in atlas_info["linhas"]:
            w.writerow([str(pacote / r["arquivo"]), r["classe"], "atlas", r["split"], f"atlas:{r['pagina_pdf']}"])
        for r in linhas_pad:
            w.writerow([str(pad / r["arquivo"]), r["classe"], "pad", "pad", f"pad:{r['patient_id']}"])
    faltando = [r["caminho"] for r in csv.DictReader(open(saida, encoding="utf-8")) if not Path(r["caminho"]).exists()]
    if faltando: raise SystemExit(f"{len(faltando)} arquivos do manifesto mesclado não existem")
    cont = Counter((r["origem"], r["classe"]) for r in csv.DictReader(open(saida, encoding="utf-8")))
    resumo = {
        "manifesto_mesclado": saida.name,
        "total_linhas": sum(cont.values()),
        "por_origem_e_classe": {f"{o}:{c}": n for (o, c), n in sorted(cont.items())},
        "mapeamento_pad": mapa_pad,
        "hash_manifest_atlas": atlas_info["hash_manifest_atlas"],
        "hash_manifesto_pad": sha256(pad / "manifesto_pad.csv"),
        "observacao_hash": "hashes dos JPEG do PAD podem variar entre versões do libjpeg; a verificação é de existência e contagem",
    }
    json.dump(resumo, open(trabalho / "resumo_mesclagem.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"manifesto mesclado: {resumo['total_linhas']} linhas em {saida}")
    return resumo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--trabalho", default="./dados_treino")
    ap.add_argument("--pular-download", action="store_true")
    a = ap.parse_args()
    trabalho = Path(a.trabalho).resolve(); trabalho.mkdir(parents=True, exist_ok=True)
    pacote = Path(a.atlas).resolve()
    def log(m): print(f"[preparar_tudo] {m}", flush=True)
    atlas = validar_atlas(pacote, log)
    pad = preparar_pad(trabalho, a.pular_download, log)
    mesclar(atlas, pad, pacote, trabalho, log)
    log("pronto. Treino (exemplo):")
    log(f"  python3 treino/cv_treino.py --atlas {pacote} --pad {pad} --config forte --pesos inversa --out runs/forte_pad")


if __name__ == "__main__":
    main()
