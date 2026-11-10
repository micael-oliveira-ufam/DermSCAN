# Código de ML (sem dados)

Nenhuma imagem, dataset ou manifesto derivado do atlas (CC BY-NC-SA 3.0 IGO) está neste repositório.

- `dados/build_atlas.py`: extrai imagens e metadados do PDF do atlas (requer o PDF e poppler-utils: `pdfimages`, `pdftotext`).
- `dados/build_dataset.py`: monta o split treino/validação/teste (seed 42, agrupado por página).
- `treino/train_v2.py`, `treino/rodar_todas.sh`: treino e avaliação (ConvNeXt, Swin, ViT; métricas, IC bootstrap, calibração).
- `exportacao/exportar.py`: exporta para ONNX, quantiza em int8 e confere paridade com o PyTorch.

Observações de reprodutibilidade:
- Os scripts foram escritos para um diretório de trabalho com `atlas.pdf`, `imglist.txt`, `raw/` e `full.txt` (ver docstring de `build_atlas.py`); os caminhos podem precisar de ajuste.
- Só o ViT-B/16 (seed 42) foi treinado, avaliado e exportado até agora.
- A correção do `train_v2.py` para as arquiteturas Swin (argumento duplicado `stochastic_depth_prob`) **não foi executada**.

## Rodar a validação cruzada (GPU)

Requisitos: PyTorch com CUDA, torchvision, scikit-learn, pillow. Os dados não estão no repositório.

1. Pacote do atlas (`pacote/` com `manifest.csv`, `train/`, `val/`, `test/`), gerado a partir do PDF do atlas (`dados/build_atlas.py`, `dados/build_dataset.py`). As imagens do atlas não estão no repositório.
2. Um comando faz a validação do atlas, o download e o processamento do PAD-UFES-20 e o manifesto mesclado:
   ```bash
   python3 dados/preparar_tudo.py --atlas /caminho/pacote --trabalho ./dados_treino
   ```
   Use `--pular-download` para reaproveitar um PAD já processado em `./dados_treino/pad`.
3. Exemplo (configuração forte, com PAD para BCC, SCC e outras dermatoses):
   ```bash
   python3 treino/cv_treino.py --atlas /caminho/pacote --pad /caminho/pad --config forte --pesos inversa \
     --label-smoothing 0.1 --pad-max-por-classe 150 --out runs/forte_pad
   ```
   Baseline (sem PAD, sem pesos): `--config base --pesos nenhum --label-smoothing 0 --out runs/base`.
