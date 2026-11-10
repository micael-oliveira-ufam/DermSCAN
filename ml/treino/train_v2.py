#!/usr/bin/env python3
"""Treino de classificadores de lesões cutâneas sobre o pacote atlas_leishmaniose_treino_v1.

Arquiteturas (torchvision 0.20.1, pesos ImageNet-1k pré-treinados):
  CNN:          convnext_tiny, convnext_base, convnext_large
  Transformers: swin_b, swin_v2_b, vit_b_16, vit_l_16

O pacote já vem dividido em train/ val/ test/ (uma pasta por classe). Este script não refaz o split.

Saídas, por arquitetura e semente, em <out>/<arch>/seed<s>/:
  best.pt, classes.json, history.csv, metrics_test.json, confusion_matrix_test.csv,
  confusion_matrix_test.png, predictions_test.csv, metadata.json
E, ao final, <out>/comparacao.csv com uma linha por execução.

Uso:
  python train_v2.py --data-dir ../pacote --arch convnext_large --seeds 42 43 44
  python train_v2.py --data-dir ../pacote --arch convnext_large,swin_b --seeds 42
  python train_v2.py --data-dir ../pacote --arch all --seeds 42 --batch-size 16 --device cuda --amp
"""
from __future__ import annotations

import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # operações sem suporte no MPS rodam na CPU

import argparse
import contextlib
import csv
import hashlib
import json
import math
import platform
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from torch.utils.data import DataLoader
from torchvision import transforms as T
from torchvision.datasets import ImageFolder
from torchvision.models import get_model, get_model_weights

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)  # normalização ImageNet, igual aos pesos
SIZE = 224
ARCHS = ["convnext_tiny", "convnext_base", "convnext_large", "swin_b", "swin_v2_b", "vit_b_16", "vit_l_16"]

TRAIN_T = T.Compose([
    T.Resize((SIZE, SIZE)),
    T.RandomHorizontalFlip(),
    T.RandomVerticalFlip(),
    T.RandomRotation(30),
    T.ColorJitter(0.2, 0.2, 0.2, 0.05),
    T.ToTensor(),
    T.Normalize(MEAN, STD),
])
EVAL_T = T.Compose([T.Resize((SIZE, SIZE)), T.ToTensor(), T.Normalize(MEAN, STD)])


# ---------------------------------------------------------------- reprodutibilidade

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def pick_device(pref: str) -> torch.device:
    if pref != "auto":
        return torch.device(pref)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# ---------------------------------------------------------------- modelo

def build(arch: str, n_classes: int, dropout: float):
    """Carrega a arquitetura com pesos ImageNet e troca só a última camada linear."""
    kw = {}
    # Só ConvNeXt. Nas Swin o torchvision já fixa stochastic_depth_prob ao instanciar a arquitetura,
    # e repetir o argumento causa "multiple values for keyword argument" (correção não testada em execução).
    if arch.startswith("convnext"):
        kw["stochastic_depth_prob"] = 0.2  # regularização por profundidade estocástica
    weights = get_model_weights(arch).DEFAULT
    model = get_model(arch, weights=weights, **kw)

    if arch.startswith("convnext"):
        in_f = model.classifier[-1].in_features
        model.classifier[-1] = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, n_classes))
    elif arch.startswith("swin"):
        in_f = model.head.in_features
        model.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, n_classes))
    elif arch.startswith("vit"):
        in_f = model.heads.head.in_features
        model.heads.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, n_classes))
    else:
        raise ValueError(f"arquitetura sem regra de cabeça: {arch}")
    return model, str(weights)


def head_params(arch: str, model: nn.Module):
    if arch.startswith("convnext"):
        return model.classifier[-1].parameters()
    if arch.startswith("swin"):
        return model.head.parameters()
    return model.heads.head.parameters()


def set_requires_grad(params, flag: bool) -> None:
    for p in params:
        p.requires_grad_(flag)


# ---------------------------------------------------------------- métricas

def metrics(y: np.ndarray, p: np.ndarray, classes: list[str]) -> dict:
    """Macro-F1 calculada só sobre classes com suporte > 0 (uma classe ausente não entra com F1 = 0)."""
    n = len(classes)
    cm = np.zeros((n, n), dtype=int)
    np.add.at(cm, (y, p), 1)
    tp = np.diag(cm).astype(float)
    support = cm.sum(1).astype(float)
    predicted = cm.sum(0).astype(float)
    prec = np.divide(tp, predicted, out=np.zeros(n), where=predicted > 0)
    rec = np.divide(tp, support, out=np.zeros(n), where=support > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0)
    present = support > 0
    return {
        "cm": cm,
        "n": int(cm.sum()),
        "accuracy": float(tp.sum() / max(cm.sum(), 1)),
        "balanced_accuracy": float(rec[present].mean()),
        "macro_f1": float(f1[present].mean()),
        "per_class": {c: {"precision": float(prec[i]), "recall": float(rec[i]),
                          "f1": float(f1[i]), "support": int(support[i])} for i, c in enumerate(classes)},
    }


def bootstrap_ci_macro_f1(y, p, classes, seed: int, n_boot: int = 1000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        vals.append(metrics(y[idx], p[idx], classes)["macro_f1"])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def expected_calibration_error(probs: np.ndarray, y: np.ndarray, bins: int = 15) -> float:
    conf = probs.max(1)
    correct = (probs.argmax(1) == y).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def plot_cm(cm: np.ndarray, classes: list[str], path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(classes)
    norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    fig, axes = plt.subplots(1, 2, figsize=(max(12, 1.3 * n * 2), max(5, 0.6 * n)))
    for ax, mat, t, fmt in [(axes[0], cm, "Contagem", "d"), (axes[1], norm, "Normalizada por linha (recall)", ".2f")]:
        ax.imshow(mat, cmap="Blues")
        ax.set_xticks(range(n), classes, rotation=45, ha="right")
        ax.set_yticks(range(n), classes)
        ax.set_xlabel("Predito")
        ax.set_ylabel("Verdadeiro")
        ax.set_title(t)
        for i in range(n):
            for j in range(n):
                ax.text(j, i, format(mat[i, j], fmt), ha="center", va="center", fontsize=8,
                        color="white" if mat[i, j] > mat.max() / 2 else "black")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- treino

@torch.no_grad()
def predict(model: nn.Module, dl: DataLoader, device: torch.device):
    model.eval()
    logits, ys = [], []
    for x, y in dl:
        logits.append(model(x.to(device)).float().cpu())
        ys.append(y)
    return torch.cat(logits), torch.cat(ys).numpy()


def train_one(arch: str, seed: int, args, data_dir: Path, out_root: Path, device: torch.device) -> dict:
    set_seed(seed)
    out = out_root / arch / f"seed{seed}"
    out.mkdir(parents=True, exist_ok=True)

    tr_ds = ImageFolder(data_dir / "train", transform=TRAIN_T)
    va_ds = ImageFolder(data_dir / "val", transform=EVAL_T)
    te_ds = ImageFolder(data_dir / "test", transform=EVAL_T)
    classes = tr_ds.classes
    if not (va_ds.classes == classes and te_ds.classes == classes):
        raise SystemExit("As classes diferem entre train, val e test.")
    n = len(classes)
    counts = np.bincount(tr_ds.targets, minlength=n).astype(float)
    cw = counts.sum() / (n * np.maximum(counts, 1))
    cw = torch.tensor(cw / cw.mean(), dtype=torch.float32, device=device)

    g = torch.Generator().manual_seed(seed)
    tr_dl = DataLoader(tr_ds, batch_size=args.batch_size, shuffle=True, generator=g, num_workers=args.workers)
    va_dl = DataLoader(va_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.workers)
    te_dl = DataLoader(te_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.workers)

    model, weights_name = build(arch, n, args.dropout)
    model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    head_ids = {id(p) for p in head_params(arch, model)}
    backbone = [p for p in model.parameters() if id(p) not in head_ids]
    if args.freeze_epochs > 0:
        set_requires_grad(backbone, False)  # aquecimento: só a cabeça aprende

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    steps = len(tr_dl)
    total, warm = steps * args.epochs, steps * args.warmup_epochs

    def lr_factor(s: int) -> float:
        if s < warm:
            return (s + 1) / max(1, warm)
        prog = (s - warm) / max(1, total - warm)
        return 0.5 * (1 + math.cos(math.pi * min(1.0, prog)))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_factor)
    crit = nn.CrossEntropyLoss(weight=cw)
    amp_on = args.amp and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_on)
    ctx = (lambda: torch.autocast(device_type="cuda", dtype=torch.float16)) if amp_on else contextlib.nullcontext

    history, best_f1, best_epoch, best_state, bad = [], -1.0, 0, None, 0
    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        if args.freeze_epochs and epoch == args.freeze_epochs + 1:
            set_requires_grad(backbone, True)
        model.train()
        loss_sum, seen, te0 = 0.0, 0, time.time()
        for x, y in tr_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            with ctx():
                loss = crit(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            loss_sum += loss.item() * len(y)
            seen += len(y)

        val_logits, val_y = predict(model, va_dl, device)
        vm = metrics(val_y, val_logits.argmax(1).numpy(), classes)
        val_loss = float(F.cross_entropy(val_logits, torch.tensor(val_y)).item())
        row = {"epoch": epoch, "train_loss": loss_sum / max(seen, 1), "val_loss": val_loss,
               "val_acc": vm["accuracy"], "val_macro_f1": vm["macro_f1"],
               "lr": opt.param_groups[0]["lr"], "seconds": round(time.time() - te0, 1)}
        history.append(row)
        print(f"[{arch} seed{seed}] época {epoch:2d} | perda treino {row['train_loss']:.4f} | "
              f"val perda {val_loss:.4f} | val acc {vm['accuracy']:.4f} | val macro-F1 {vm['macro_f1']:.4f} | "
              f"{row['seconds']} s", flush=True)

        if vm["macro_f1"] > best_f1:
            best_f1, best_epoch, bad = vm["macro_f1"], epoch, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience:
                print(f"[{arch} seed{seed}] parada antecipada na época {epoch}", flush=True)
                break

    model.load_state_dict(best_state)
    wall = time.time() - t0

    te_logits, te_y = predict(model, te_dl, device)
    probs = F.softmax(te_logits, dim=1).numpy()
    te_pred = probs.argmax(1)
    tm = metrics(te_y, te_pred, classes)
    ci = bootstrap_ci_macro_f1(te_y, te_pred, classes, seed=seed)
    ece = expected_calibration_error(probs, te_y)

    torch.save(best_state, out / "best.pt")
    (out / "classes.json").write_text(json.dumps(classes, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "history.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(history[0].keys()))
        w.writeheader()
        w.writerows(history)
    with (out / "confusion_matrix_test.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["verdadeiro \\ predito"] + classes)
        for c, row_cm in zip(classes, tm["cm"]):
            w.writerow([c] + list(row_cm))
    plot_cm(tm["cm"], classes, out / "confusion_matrix_test.png", f"{arch} seed {seed} (teste)")
    with (out / "predictions_test.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "verdadeiro", "predito", "prob_max"])
        for (path, _), yt, yp, pr in zip(te_ds.samples, te_y, te_pred, probs.max(1)):
            w.writerow([Path(path).relative_to(data_dir), classes[yt], classes[yp], f"{pr:.4f}"])

    result = {
        "arch": arch, "seed": seed, "weights": weights_name,
        "n_test": tm["n"], "accuracy": tm["accuracy"], "balanced_accuracy": tm["balanced_accuracy"],
        "macro_f1": tm["macro_f1"], "macro_f1_ci95": ci, "ece": ece,
        "best_epoch": best_epoch, "best_val_macro_f1": best_f1, "epochs_run": len(history),
        "per_class": tm["per_class"],
    }
    (out / "metrics_test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {
        "arch": arch, "weights": weights_name, "seed": seed, "params": n_params,
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "torch": torch.__version__, "torchvision": torchvision.__version__, "numpy": np.__version__,
        "python": platform.python_version(), "platform": platform.platform(), "device": str(device),
        "amp": amp_on, "classes": classes,
        "split_sizes": {"train": len(tr_ds), "val": len(va_ds), "test": len(te_ds)},
        "manifest_sha256": sha256_file(data_dir / "manifest.csv") if (data_dir / "manifest.csv").exists() else None,
        "git_commit": git_commit(), "wall_time_s": round(wall, 1),
    }
    (out / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[{arch} seed{seed}] TESTE: macro-F1 {tm['macro_f1']:.4f} "
          f"(IC95% {ci[0]:.4f}–{ci[1]:.4f}) | acc {tm['accuracy']:.4f} | ECE {ece:.4f}", flush=True)
    return result


def write_comparison(out_root: Path) -> None:
    rows = []
    for p in sorted(out_root.glob("*/seed*/metrics_test.json")):
        if not (p.parent / "metadata.json").exists():
            print(f"[comparacao] ignorada, sem metadata.json: {p.parent}")
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        meta = json.loads((p.parent / "metadata.json").read_text(encoding="utf-8"))
        rows.append({
            "arch": r["arch"], "seed": r["seed"], "params": meta["params"], "weights": r["weights"],
            "test_macro_f1": f"{r['macro_f1']:.4f}",
            "ci95_low": f"{r['macro_f1_ci95'][0]:.4f}", "ci95_high": f"{r['macro_f1_ci95'][1]:.4f}",
            "test_accuracy": f"{r['accuracy']:.4f}", "test_balanced_accuracy": f"{r['balanced_accuracy']:.4f}",
            "ece": f"{r['ece']:.4f}", "best_epoch": r["best_epoch"], "epochs_run": r["epochs_run"],
            "wall_time_s": meta["wall_time_s"], "device": meta["device"],
        })
    if not rows:
        return
    with (out_root / "comparacao.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[comparacao] {out_root / 'comparacao.csv'} ({len(rows)} execuções)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True, help="pasta do pacote com train/ val/ test/")
    ap.add_argument("--out-dir", type=Path, default=Path("runs_v2"))
    ap.add_argument("--arch", default="convnext_large",
                    help="uma arquitetura, lista separada por vírgula, ou 'all'. Opções: " + ", ".join(ARCHS))
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--warmup-epochs", type=float, default=1)
    ap.add_argument("--freeze-epochs", type=int, default=0, help="épocas só com a cabeça treinando (0 = desligado)")
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=0, help="0 no Mac; 4 a 8 no Linux")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])
    ap.add_argument("--amp", action="store_true", help="precisão mista fp16 (só CUDA)")
    args = ap.parse_args()

    archs = ARCHS if args.arch == "all" else [a.strip() for a in args.arch.split(",")]
    bad = [a for a in archs if a not in ARCHS]
    if bad:
        raise SystemExit(f"arquitetura desconhecida: {bad}")

    device = pick_device(args.device)
    print(f"[train_v2] device={device} | torch {torch.__version__} | torchvision {torchvision.__version__}", flush=True)
    for arch in archs:
        for seed in args.seeds:
            train_one(arch, seed, args, args.data_dir, args.out_dir, device)
    write_comparison(args.out_dir)


if __name__ == "__main__":
    main()
