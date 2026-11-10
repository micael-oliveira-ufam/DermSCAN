"""Validação cruzada estratificada agrupada (5 folds) + aumento forte + pesos de classe +
label smoothing + ensemble dos folds, com mesclagem opcional do PAD-UFES-20 (somente no treino).

Princípios:
- Avaliação sempre no atlas (folds de validação e teste de 89 imagens). O PAD nunca entra em validação.
- Grupos: página do atlas (para o atlas) e patient_id (para o PAD). Assim, uma mesma página/paciente
  não fica em treino e validação ao mesmo tempo.
- Sem parada antecipada sobre a validação: o número de épocas é fixo, para não otimizar no próprio fold.
- Teste de 89 imagens é avaliado por cada fold e pelo ensemble (média das probabilidades).

Exemplo (GPU):
  python3 cv_treino.py --atlas ../../dados/pacote --config forte --pad ../../dados/pad --pad-max-por-classe 150 --out runs/forte_pad
"""
from __future__ import annotations
import argparse, csv, json, os, platform, random, time, hashlib
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torchvision import transforms as T
from torchvision.models import get_model, get_model_weights

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
CLASSES = ["carcinoma_basocelular", "carcinoma_espinocelular", "esporotricose", "hanseniase",
           "leish_cutanea_outras_formas", "leish_cutanea_ulcera", "leish_mucosa", "outras_dermatoses",
           "tuberculose_e_micobacterioses", "ulceras_vasculares"]
IDX = {c: i for i, c in enumerate(CLASSES)}


def semear(s: int):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)


def escolher_dispositivo():
    if torch.cuda.is_available(): return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available(): return torch.device("mps")
    return torch.device("cpu")


# ------------------------------------------------------------------ dados
class Amostras(Dataset):
    """Lista de (caminho, rótulo, grupo, origem). Imagens são abertas sob demanda."""
    def __init__(self, itens, transform):
        self.itens, self.transform = itens, transform
    def __len__(self): return len(self.itens)
    def __getitem__(self, i):
        caminho, y, _, _ = self.itens[i]
        im = Image.open(caminho).convert("RGB")
        return self.transform(im), y


def ler_atlas(raiz: Path):
    """Lê o manifesto do pacote do atlas (train/val/test) e devolve itens com grupo = página."""
    itens = []
    with open(raiz / "manifest.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            itens.append((raiz / r["arquivo"], IDX[r["classe"]], f"atlas:{r['pagina_pdf']}", r["split"]))
    return itens


def ler_pad(raiz: Path, mapeadas: set[str] | None, max_por_classe: int | None, rng: random.Random):
    """Lê o manifesto do PAD (já mapeado e reduzido para 256x256). Limita por classe, amostrando por paciente."""
    por_classe: dict[str, list] = {}
    with open(raiz / "manifesto_pad.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if mapeadas and r["classe_atlas"] not in mapeadas: continue
            por_classe.setdefault(r["classe_atlas"], []).append(r)
    itens = []
    for cls, rows in por_classe.items():
        rng.shuffle(rows)
        if max_por_classe: rows = rows[:max_por_classe]
        for r in rows:
            itens.append((raiz / r["arquivo"], IDX[cls], f"pad:{r['patient_id']}", "pad"))
    return itens


# ------------------------------------------------------------------ transformações
def transformacoes(config: str):
    if config == "base":  # o mesmo pipeline do treino atual
        treino = T.Compose([T.Resize((224, 224)), T.RandomHorizontalFlip(), T.RandomVerticalFlip(),
                            T.RandomRotation(30), T.ColorJitter(0.2, 0.2, 0.2, 0.05),
                            T.ToTensor(), T.Normalize(MEAN, STD)])
    elif config == "forte":
        treino = T.Compose([T.RandomResizedCrop(224, scale=(0.6, 1.0), ratio=(0.8, 1.25)),
                            T.RandomHorizontalFlip(), T.RandomVerticalFlip(), T.RandomRotation(30),
                            T.TrivialAugmentWide(),
                            T.ColorJitter(0.2, 0.2, 0.15, 0.02),
                            T.RandomApply([T.GaussianBlur(5, (0.1, 1.5))], p=0.2),
                            T.ToTensor(), T.RandomErasing(p=0.25, scale=(0.02, 0.1)),
                            T.Normalize(MEAN, STD)])
    else:
        raise ValueError(config)
    avaliacao = T.Compose([T.Resize((224, 224)), T.ToTensor(), T.Normalize(MEAN, STD)])
    return treino, avaliacao


# ------------------------------------------------------------------ modelo
def construir(arch: str, dropout: float, pesos_imagenet: bool = True):
    pesos = get_model_weights(arch).DEFAULT if pesos_imagenet else None
    m = get_model(arch, weights=pesos)
    if arch.startswith("vit"):
        in_f = m.heads.head.in_features
        m.heads.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, len(CLASSES)))
    elif arch.startswith("convnext"):
        in_f = m.classifier[-1].in_features
        m.classifier[-1] = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, len(CLASSES)))
    else:
        raise ValueError("arquitetura não prevista: " + arch)
    return m


# ------------------------------------------------------------------ métricas (sem dependências extras)
def metricas(probs: np.ndarray, y: np.ndarray, n_bins: int = 15) -> dict:
    pred = probs.argmax(1)
    acc = float((pred == y).mean())
    recalls, f1s = [], []
    for c in range(len(CLASSES)):
        vp = np.sum((pred == c) & (y == c)); fp = np.sum((pred == c) & (y != c)); fn = np.sum((pred != c) & (y == c))
        if np.sum(y == c) == 0: continue
        rec = vp / max(vp + fn, 1); prec = vp / max(vp + fp, 1)
        recalls.append(rec); f1s.append(0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
    conf = probs.max(1)
    edges = np.linspace(0, 1, n_bins + 1); ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any(): ece += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return {"acuracia": acc, "acuracia_balanceada": float(np.mean(recalls)), "f1_macro": float(np.mean(f1s)),
            "ece": float(ece), "recall_por_classe": {CLASSES[c]: float(r) for c, r in zip(
                [c for c in range(len(CLASSES)) if np.sum(y == c) > 0], recalls)}}


def ic_bootstrap(probs, y, n=2000, seed=42):
    rng = np.random.default_rng(seed); n_amostras = len(y); vals = []
    for _ in range(n):
        idx = rng.integers(0, n_amostras, n_amostras)
        vals.append(float((probs[idx].argmax(1) == y[idx]).mean()))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


# ------------------------------------------------------------------ treino de um fold
@torch.no_grad()
def prever(modelo, loader, dev):
    modelo.eval(); out = []
    for x, _ in loader:
        out.append(torch.softmax(modelo(x.to(dev)), 1).cpu().numpy())
    return np.concatenate(out)


def treinar_fold(args, treino_itens, val_itens, teste_itens, dev, log):
    tr_t, av_t = transformacoes(args.config)
    ds_tr = Amostras(treino_itens, tr_t)
    # pesos de classe: inverso da frequência (suavizado pela raiz quadrada, se --pesos raiz)
    contagem = np.bincount([y for _, y, _, _ in treino_itens], minlength=len(CLASSES)).astype(float)
    peso_classe = np.where(contagem > 0, 1.0 / np.maximum(contagem, 1), 0.0)
    if args.pesos == "raiz": peso_classe = np.sqrt(peso_classe)
    if args.pesos != "nenhum":
        peso_classe = peso_classe / peso_classe[contagem > 0].mean()
        pesos_amostra = [float(peso_classe[y]) for _, y, _, _ in treino_itens]
        sampler = WeightedRandomSampler(pesos_amostra, num_samples=len(treino_itens), replacement=True)
        loader_tr = DataLoader(ds_tr, batch_size=args.batch_size, sampler=sampler, num_workers=args.workers)
    else:
        loader_tr = DataLoader(ds_tr, batch_size=args.batch_size, shuffle=True, num_workers=args.workers)
    loader_val = DataLoader(Amostras(val_itens, av_t), batch_size=64, num_workers=args.workers)
    loader_te = DataLoader(Amostras(teste_itens, av_t), batch_size=64, num_workers=args.workers)

    modelo = construir(args.arch, args.dropout, args.pesos_imagenet).to(dev)
    opt = torch.optim.AdamW(modelo.parameters(), lr=args.lr, weight_decay=args.wd)
    passos = args.epochs * len(loader_tr)
    aquec = max(1, int(args.warmup_epochs * len(loader_tr)))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / aquec if s < aquec else
                                              0.5 * (1 + np.cos(np.pi * (s - aquec) / max(1, passos - aquec))))
    perda = nn.CrossEntropyLoss(weight=torch.tensor(peso_classe, dtype=torch.float32, device=dev)
                                if args.pesos != "nenhum" else None, label_smoothing=args.label_smoothing)
    for ep in range(1, args.epochs + 1):
        modelo.train(); t0 = time.time(); soma = 0.0; n = 0
        for x, y in loader_tr:
            x, y = x.to(dev), y.to(dev)
            if args.mixup > 0 and np.random.rand() < 0.5:
                lam = np.random.beta(args.mixup, args.mixup); perm = torch.randperm(x.size(0), device=dev)
                saida = modelo(lam * x + (1 - lam) * x[perm])
                loss = lam * perda(saida, y) + (1 - lam) * perda(saida, y[perm])
            else:
                loss = perda(modelo(x), y)
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
            soma += float(loss) * x.size(0); n += x.size(0)
        log(f"  época {ep}/{args.epochs} perda={soma / max(n, 1):.4f} {time.time() - t0:.0f}s")
    # sem seleção de época: avaliação ao final, para não otimizar na própria validação
    p_val = prever(modelo, loader_val, dev)
    p_te = prever(modelo, loader_te, dev)
    return p_val, p_te


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, help="pasta com manifest.csv do atlas")
    ap.add_argument("--pad", default=None, help="pasta com manifesto_pad.csv e imgs/ (opcional)")
    ap.add_argument("--pad-classes", default="carcinoma_basocelular,carcinoma_espinocelular,outras_dermatoses")
    ap.add_argument("--pad-max-por-classe", type=int, default=150)
    ap.add_argument("--config", choices=["base", "forte"], default="forte")
    ap.add_argument("--pesos", choices=["nenhum", "inversa", "raiz"], default="inversa")
    ap.add_argument("--label-smoothing", type=float, default=0.1)
    ap.add_argument("--mixup", type=float, default=0.0, help="alfa do Beta; 0 desliga")
    ap.add_argument("--arch", default="vit_b_16")
    ap.add_argument("--sem-pesos-imagenet", dest="pesos_imagenet", action="store_false",
                    help="só para teste de fumaça: sem pesos pré-treinados")
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--warmup-epochs", type=float, default=1)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limitar-folds", type=int, default=0, help="só para teste rápido (0 = todos)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.txt", "a", encoding="utf-8")
    def log(msg):
        s = f"[{time.strftime('%F %T')}] {msg}"; print(s, flush=True); logf.write(s + "\n"); logf.flush()

    semear(args.seed)
    dev = escolher_dispositivo()
    log(f"dispositivo={dev} args={vars(args)}")

    atlas = ler_atlas(Path(args.atlas))
    pool = [it for it in atlas if it[3] in ("train", "val")]
    teste = [it for it in atlas if it[3] == "test"]
    log(f"atlas: pool={len(pool)} (train+val), teste={len(teste)}")

    pad_itens = []
    if args.pad:
        rng = random.Random(args.seed)
        mapeadas = set(args.pad_classes.split(",")) if args.pad_classes else None
        pad_itens = ler_pad(Path(args.pad), mapeadas, args.pad_max_por_classe, rng)
        log(f"PAD mesclado (só treino): {len(pad_itens)} imagens; classes={sorted({CLASSES[i[1]] for i in pad_itens})}")

    # divisão estratificada agrupada por página (atlas); a estratificação usa a classe
    from sklearn.model_selection import StratifiedGroupKFold
    X = np.arange(len(pool)); y = np.array([it[1] for it in pool]); g = np.array([it[2] for it in pool])
    skf = StratifiedGroupKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    oof = np.zeros((len(pool), len(CLASSES)))
    probs_teste_folds = []
    resultados_folds = []
    for k, (tr_idx, va_idx) in enumerate(skf.split(X, y, g)):
        if args.limitar_folds and k >= args.limitar_folds: break
        log(f"fold {k + 1}/{args.folds}: treino={len(tr_idx)} validação={len(va_idx)}")
        semear(args.seed + k)
        treino_k = [pool[i] for i in tr_idx] + pad_itens
        val_k = [pool[i] for i in va_idx]
        p_val, p_te = treinar_fold(args, treino_k, val_k, teste, dev, log)
        oof[va_idx] = p_val
        probs_teste_folds.append(p_te)
        m = metricas(p_val, np.array([it[1] for it in val_k]))
        resultados_folds.append(m)
        log(f"  fold {k + 1}: acc={m['acuracia']:.4f} bal={m['acuracia_balanceada']:.4f} f1={m['f1_macro']:.4f}")

    usados = len(probs_teste_folds)
    idx_oof = np.where(oof.sum(1) > 0)[0]
    y_teste = np.array([it[1] for it in teste])
    ensemble_teste = np.mean(probs_teste_folds, axis=0)
    resumo = {
        "config": vars(args),
        "folds_usados": usados,
        "oof_atlas": metricas(oof[idx_oof], y[idx_oof]) | {"ic95_acuracia": ic_bootstrap(oof[idx_oof], y[idx_oof])},
        "teste_ensemble": metricas(ensemble_teste, y_teste) | {"ic95_acuracia": ic_bootstrap(ensemble_teste, y_teste)},
        "teste_por_fold": [metricas(p, y_teste)["acuracia"] for p in probs_teste_folds],
        "resultados_folds_validacao": resultados_folds,
        "ambiente": {"python": platform.python_version(), "torch": torch.__version__, "dispositivo": str(dev)},
        "hash_manifesto_atlas": hashlib.sha256(open(Path(args.atlas) / "manifest.csv", "rb").read()).hexdigest(),
    }
    if args.pad:
        resumo["hash_manifesto_pad"] = hashlib.sha256(open(Path(args.pad) / "manifesto_pad.csv", "rb").read()).hexdigest()
        resumo["pad_imagens_no_treino"] = len(pad_itens)
    json.dump(resumo, open(out / "resumo.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.savez(out / "predicoes.npz", oof=oof, teste_ensemble=ensemble_teste, y_teste=y_teste,
             **{f"teste_fold{k}": p for k, p in enumerate(probs_teste_folds)})
    log(f"FIM resumo em {out / 'resumo.json'}")


if __name__ == "__main__":
    main()
