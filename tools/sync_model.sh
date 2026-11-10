#!/usr/bin/env bash
# Copia o modelo (única cópia versionada, em docs/model/) para o app, antes de compilar.
set -euo pipefail
raiz="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$raiz/app/assets/model"
cp "$raiz/docs/model/vit_b16_int8.onnx" "$raiz/app/assets/model/"
cp "$raiz/docs/model/modelo_info.json" "$raiz/app/assets/model/"
( cd "$raiz/app/assets/model" && sha256sum vit_b16_int8.onnx )
echo "modelo copiado para app/assets/model/"
