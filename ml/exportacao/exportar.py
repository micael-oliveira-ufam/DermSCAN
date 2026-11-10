"""Exporta o ViT-B/16 treinado (seed 42) para ONNX fp32 e int8, e verifica paridade.

Entradas:
  --ckpt   best.pt do treino (state_dict do vit_b_16 com cabeça Dropout+Linear(768,10))
  --data   pasta pacote/ com val/ e test/ (ImageFolder, ordem alfabética = classes.json)
  --out    pasta de saída
Saídas: vit_b16_fp32.onnx, vit_b16_int8.onnx, relatorio.json

Pré-processamento idêntico ao treino: Resize(224,224) (estica, sem recorte),
ToTensor, Normalize(ImageNet). Calibração de temperatura ajustada SOMENTE na validação.
"""
import argparse, json, time, os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torchvision
from torchvision import transforms as T
from torchvision.datasets import ImageFolder
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score, accuracy_score, balanced_accuracy_score
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
SIZE = 224
TF = T.Compose([T.Resize((SIZE, SIZE)), T.ToTensor(), T.Normalize(MEAN, STD)])


def load_model(ckpt_path: str, n_classes: int = 10, dropout: float = 0.3) -> nn.Module:
    m = torchvision.models.vit_b_16(weights=None)
    in_f = m.heads.head.in_features
    m.heads.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, n_classes))
    sd = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    m.load_state_dict(sd, strict=True)  # falha se houver qualquer divergência
    m.eval()
    return m


def logits_torch(model, ds, bs=16):
    dl = DataLoader(ds, batch_size=bs, shuffle=False, num_workers=0)
    outs, ys = [], []
    with torch.no_grad():
        for x, y in dl:
            outs.append(model(x).numpy()); ys.append(y.numpy())
    return np.concatenate(outs), np.concatenate(ys)


def logits_onnx(path, ds, bs=16):
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    dl = DataLoader(ds, batch_size=bs, shuffle=False, num_workers=0)
    outs, ys = [], []
    for x, y in dl:
        outs.append(sess.run(None, {name: x.numpy()})[0]); ys.append(y.numpy())
    return np.concatenate(outs), np.concatenate(ys)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True); e = np.exp(z); return e / e.sum(axis=1, keepdims=True)


def ece(probs, y, n_bins=15):
    conf = probs.max(1); pred = probs.argmax(1); acc = (pred == y).astype(float)
    edges = np.linspace(0, 1, n_bins + 1); e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any(): e += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(e)


def metricas(logits, y, probs=None):
    pred = logits.argmax(1)
    p = probs if probs is not None else softmax(logits)
    return {
        "acuracia": float(accuracy_score(y, pred)),
        "acuracia_balanceada": float(balanced_accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro", labels=np.unique(y))),
        "ece": ece(p, y),
    }


def ajustar_temperatura(logits_val, y_val):
    """Acha T>0 que minimiza NLL na validação (sem olhar o teste)."""
    zt = torch.tensor(logits_val, dtype=torch.float32); yt = torch.tensor(y_val, dtype=torch.long)
    logT = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([logT], lr=0.1, max_iter=200)
    def closure():
        opt.zero_grad()
        loss = nn.functional.cross_entropy(zt / torch.exp(logT), yt)
        loss.backward(); return loss
    opt.step(closure)
    return float(torch.exp(logT).item())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True); ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    data = Path(a.data)

    val_ds = ImageFolder(data / "val", transform=TF)
    test_ds = ImageFolder(data / "test", transform=TF)
    classes = val_ds.classes
    assert classes == test_ds.classes, "ordem de classes diverge entre val e test"
    print("classes:", classes)

    # 1) modelo PyTorch reconstruído
    model = load_model(a.ckpt, n_classes=len(classes))
    lv_t, yv = logits_torch(model, val_ds)
    lt_t, yt = logits_torch(model, test_ds)
    rep = {"classes": classes, "n_val": len(yv), "n_test": len(yt)}
    rep["fp32_pytorch_teste"] = metricas(lt_t, yt)
    print("PyTorch fp32 teste:", rep["fp32_pytorch_teste"])

    # 2) ONNX fp32
    onnx32 = out / "vit_b16_fp32.onnx"
    dummy = torch.zeros(1, 3, SIZE, SIZE)
    torch.onnx.export(model, dummy, str(onnx32), input_names=["imagem"], output_names=["logits"],
                      dynamic_axes={"imagem": {0: "lote"}, "logits": {0: "lote"}}, opset_version=17,
                      dynamo=False)
    lt_32, _ = logits_onnx(str(onnx32), test_ds)
    rep["onnx_fp32_vs_pytorch_max_abs_logit_diff"] = float(np.max(np.abs(lt_32 - lt_t)))
    rep["onnx_fp32_vs_pytorch_mesma_classe"] = float(np.mean(lt_32.argmax(1) == lt_t.argmax(1)))
    rep["fp32_onnx_teste"] = metricas(lt_32, yt)
    rep["tamanho_onnx_fp32_mb"] = round(os.path.getsize(onnx32) / 1e6, 1)
    print("ONNX fp32 vs PyTorch: max|dlogit| =", rep["onnx_fp32_vs_pytorch_max_abs_logit_diff"])

    # 3) ONNX int8 (quantização dinâmica de pesos, ativações em tempo de execução)
    onnx8 = out / "vit_b16_int8.onnx"
    quantize_dynamic(str(onnx32), str(onnx8), weight_type=QuantType.QInt8)
    lt_8, _ = logits_onnx(str(onnx8), test_ds)
    rep["int8_teste"] = metricas(lt_8, yt)
    rep["int8_vs_fp32_mesma_classe"] = float(np.mean(lt_8.argmax(1) == lt_32.argmax(1)))
    rep["tamanho_onnx_int8_mb"] = round(os.path.getsize(onnx8) / 1e6, 1)
    print("int8 teste:", rep["int8_teste"], "| tamanho MB:", rep["tamanho_onnx_int8_mb"])

    # 4) calibração de temperatura (ajuste na validação, avaliação no teste)
    lv_8, _ = logits_onnx(str(onnx8), val_ds)
    T_val = ajustar_temperatura(lv_8, yv)
    rep["temperatura_ajustada_na_validacao_int8"] = T_val
    rep["int8_calibrado_teste"] = metricas(lt_8 / T_val, yt, probs=softmax(lt_8 / T_val))
    print(f"temperatura T={T_val:.3f} | int8 calibrado teste:", rep["int8_calibrado_teste"])

    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("salvo em", out)


if __name__ == "__main__":
    main()
