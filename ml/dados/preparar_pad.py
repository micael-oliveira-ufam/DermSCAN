"""Uso: python3 preparar_pad.py <pasta_de_saida> (precisa de metadata.csv nessa pasta, baixado do Mendeley zr7vgbcyr2).
Espaço: ~3,6 GB temporários por zip (apagado após processar) e ~52 MB de imagens 256x256."""
"""Prepara o PAD-UFES-20 para mesclagem: mapeia diagnósticos para as classes do atlas,
reduz para 256x256 (esticado, igual ao pipeline do atlas) e grava manifesto com patient_id (para CV agrupada)."""
import csv, hashlib, json, os, sys, zipfile, io  # noqa: E401
from PIL import Image

RAIZ = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/pad"  # uso: python3 preparar_pad.py <pasta_de_saida>
MAPA = {  # diagnóstico PAD -> classe do atlas (MEL excluído: sem classe equivalente)
    "BCC": "carcinoma_basocelular",
    "SCC": "carcinoma_espinocelular",
    "ACK": "outras_dermatoses",   # decisão a confirmar com o usuário
    "SEK": "outras_dermatoses",   # idem
    "NEV": "outras_dermatoses",   # idem
}
PARTES = {
    "imgs_part_1.zip": "1cc2f71f-20a2-412d-b746-a9b9bc20c966",
    "imgs_part_2.zip": "559a60ed-5504-475d-996c-6a8bc253b5e7",
    "imgs_part_3.zip": "34dcdf8e-e5f1-4b35-aa0b-5135051ff852",
}
ZIP_ID = "zr7vgbcyr2"

linhas = [r for r in csv.DictReader(open(f"{RAIZ}/metadata.csv", encoding="utf-8")) if r["diagnostic"] in MAPA]
por_img = {r["img_id"]: r for r in linhas}
print("imagens alvo:", len(por_img), flush=True)
achadas = {}

for nome, fid in PARTES.items():
    print("baixando", nome, flush=True)
    zpath = f"{RAIZ}/{nome}"
    os.system(f'curl -sL --retry 3 -o "{zpath}" "https://data.mendeley.com/public-files/datasets/{ZIP_ID}/files/{fid}/file_downloaded"')
    print("tamanho", os.path.getsize(zpath), flush=True)
    with zipfile.ZipFile(zpath) as z:
        for m in z.namelist():
            base = os.path.basename(m)
            if base in por_img and base not in achadas:
                r = por_img[base]
                cls = MAPA[r["diagnostic"]]
                destino = f"{RAIZ}/imgs/{cls}/{base}"
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(m) as f:
                    im = Image.open(io.BytesIO(f.read())).convert("RGB")
                im.resize((256, 256), Image.BILINEAR).save(destino, "JPEG", quality=95)
                achadas[base] = cls
    os.remove(zpath)
    print("acumulado", len(achadas), flush=True)

faltam = set(por_img) - set(achadas)
print("sem imagem no zip:", len(faltam), flush=True)
with open(f"{RAIZ}/manifesto_pad.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["arquivo", "classe_atlas", "diagnostico_pad", "patient_id", "lesion_id", "img_id", "sha256_jpeg"])
    for img, cls in sorted(achadas.items()):
        r = por_img[img]
        p = f"{RAIZ}/imgs/{cls}/{img}"
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        w.writerow([f"imgs/{cls}/{img}", cls, r["diagnostic"], r["patient_id"], r["lesion_id"], img, h])
json.dump({"mapa": MAPA, "excluidas_sem_imagem": sorted(faltam), "total": len(achadas)},
          open(f"{RAIZ}/mapeamento_pad.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("FIM", flush=True)
