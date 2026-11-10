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
