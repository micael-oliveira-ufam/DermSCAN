#!/usr/bin/env bash
# Roda todas as arquiteturas e seeds restantes do train_v2.py, em sequência.
# Pula execuções que já têm metadata.json (execução completa).
# Executar a partir da pasta training/:  bash rodar_todas.sh
set -u

DATA_DIR="../data/atlas_leishmaniose_treino_v1"
OUT_DIR="runs_v2"
LOG="$OUT_DIR/log_rodar_todas.txt"
ARCHS=(convnext_tiny convnext_base convnext_large swin_b swin_v2_b vit_b_16 vit_l_16)
SEEDS=(42 43 44)

mkdir -p "$OUT_DIR"
echo "[$(date '+%F %T')] início" | tee -a "$LOG"

for arch in "${ARCHS[@]}"; do
  for seed in "${SEEDS[@]}"; do
    dir="$OUT_DIR/$arch/seed$seed"
    if [ -f "$dir/metadata.json" ]; then
      echo "[$(date '+%F %T')] pulando $arch seed $seed (já concluído)" | tee -a "$LOG"
      continue
    fi
    echo "[$(date '+%F %T')] iniciando $arch seed $seed" | tee -a "$LOG"
    python3 train_v2.py --data-dir "$DATA_DIR" --out-dir "$OUT_DIR" \
      --arch "$arch" --seeds "$seed" --epochs 15 --batch-size 32 2>&1 | tee -a "$LOG"
    status=${PIPESTATUS[0]}
    echo "[$(date '+%F %T')] $arch seed $seed terminou com código $status" | tee -a "$LOG"
  done
done

echo "[$(date '+%F %T')] fim" | tee -a "$LOG"
