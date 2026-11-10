#!/usr/bin/env bash
# Executa tudo: ambiente, checagem de GPU, preparo e mesclagem dos dados (atlas + PAD-UFES-20),
# três rodadas de validação cruzada e a tabela comparativa.
#
# Uso:
#   ATLAS_DIR=~/dermscan_dados/atlas bash run_tudo.sh
# Variáveis opcionais:
#   ATLAS_DIR   pasta com manifest.csv, train/, val/, test/ (padrão: ~/dermscan_dados/atlas)
#   TRABALHO    pasta de dados preparados (padrão: ./dados_treino)
#   RUNS        pasta de saídas (padrão: ./runs)
#   PYTHON      interpretador base para criar o .venv (padrão: python3)
#   DRY_RUN=1   só mostra os comandos
#   PERMITIR_CPU=1  roda sem GPU (muito lento para ViT-B/16; só para teste)
#
# Retomável: rodadas que já têm resumo.json são puladas. Código de saída != 0 se alguma rodada falhar.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATLAS_DIR="${ATLAS_DIR:-$HOME/dermscan_dados/atlas}"
TRABALHO="${TRABALHO:-$PWD/dados_treino}"
RUNS="${RUNS:-$PWD/runs}"
PYTHON="${PYTHON:-python3}"
VENV="$PWD/.venv"
LOGS="$PWD/logs"
DRY_RUN="${DRY_RUN:-0}"
PERMITIR_CPU="${PERMITIR_CPU:-0}"

log() { echo "[$(date '+%F %T')] $*"; }
executar() { if [ "$DRY_RUN" = "1" ]; then echo "    (dry-run) $*"; else "$@"; fi; }

# ---------------------------------------------------------------- 0. checagens iniciais
log "pasta do código: $HERE"
if [ ! -f "$ATLAS_DIR/manifest.csv" ]; then
  echo "ERRO: não encontrei $ATLAS_DIR/manifest.csv. Defina ATLAS_DIR com a pasta do pacote do atlas." >&2
  exit 1
fi
for d in train val test; do
  [ -d "$ATLAS_DIR/$d" ] || { echo "ERRO: falta a pasta $ATLAS_DIR/$d" >&2; exit 1; }
done
[ -f "$HERE/treino/cv_treino.py" ] || { echo "ERRO: não achei $HERE/treino/cv_treino.py" >&2; exit 1; }

# ---------------------------------------------------------------- 1. ambiente Python
if [ ! -d "$VENV" ]; then
  log "criando ambiente em $VENV"
  executar "$PYTHON" -m venv "$VENV"
fi
PY="$VENV/bin/python"
if [ "$DRY_RUN" != "1" ] && ! "$PY" -c "import torch, torchvision, sklearn, PIL" >/dev/null 2>&1; then
  log "instalando dependências (requirements.txt do pacote)"
  "$PY" -m pip install -q --upgrade pip
  if [ -f "$HERE/requirements.txt" ]; then
    "$PY" -m pip install -q -r "$HERE/requirements.txt" || { echo "ERRO: falha ao instalar dependências" >&2; exit 1; }
  else
    "$PY" -m pip install -q torch torchvision scikit-learn pillow numpy || exit 1
  fi
fi

# ---------------------------------------------------------------- 2. GPU
if [ "$DRY_RUN" != "1" ]; then
  CUDA=$("$PY" -c "import torch; print(torch.cuda.is_available())")
  if [ "$CUDA" != "True" ] && [ "$PERMITIR_CPU" != "1" ]; then
    echo "ERRO: CUDA não disponível. ViT-B/16 em CPU levaria muito tempo. Use PERMITIR_CPU=1 só para teste." >&2
    exit 1
  fi
  log "dispositivo: $([ "$CUDA" = "True" ] && "$PY" -c "import torch; print(torch.cuda.get_device_name(0))" || echo CPU)"
fi

mkdir -p "$TRABALHO" "$RUNS" "$LOGS"

# ---------------------------------------------------------------- 3. dados: PAD + mesclagem
PAD_OK="$TRABALHO/pad/manifesto_pad.csv"
if [ -f "$PAD_OK" ]; then
  log "PAD já processado em $TRABALHO/pad (não baixa de novo)"
  executar "$PY" "$HERE/dados/preparar_tudo.py" --atlas "$ATLAS_DIR" --trabalho "$TRABALHO" --pular-download \
    || { echo "ERRO no preparo dos dados (se o PAD for de uma versão antiga, apague $TRABALHO/pad e rode de novo)" >&2; exit 1; }
else
  log "baixando e processando o PAD-UFES-20 (≈3,6 GB) e mesclando com o atlas"
  executar "$PY" "$HERE/dados/preparar_tudo.py" --atlas "$ATLAS_DIR" --trabalho "$TRABALHO" || { echo "ERRO no preparo dos dados" >&2; exit 1; }
fi

# ---------------------------------------------------------------- 4. treino (validação cruzada)
FALHAS=()
rodar() {
  local nome="$1"; shift
  if [ -f "$RUNS/$nome/resumo.json" ]; then
    log "rodada '$nome' já concluída; pulando"
    return
  fi
  log "rodada '$nome' iniciada"
  if executar "$PY" "$HERE/treino/cv_treino.py" --atlas "$ATLAS_DIR" "$@" --out "$RUNS/$nome" > "$LOGS/$nome.log" 2>&1; then
    log "rodada '$nome' concluída"
  else
    log "ERRO na rodada '$nome' (veja $LOGS/$nome.log)"
    FALHAS+=("$nome")
  fi
}

rodar base   --config base  --pesos nenhum  --label-smoothing 0
rodar forte  --config forte --pesos inversa
# PAD: BCC e SCC (já existem no atlas) + ACK, SEK e NEV como classes individuais (queratose actínica,
# queratose seborreica, nevo melanocítico). O modelo desta rodada tem 13 saídas.
rodar forte_pad --config forte --pesos inversa \
     --pad "$TRABALHO/pad" --pad-max-por-classe 150 \
     --pad-classes carcinoma_basocelular,carcinoma_espinocelular,queratose_actinica,queratose_seborreica,nevo_melanocitico \
     --pad-reservado 0.2

# ---------------------------------------------------------------- 5. comparação
log "gerando tabela comparativa em $RUNS/comparacao.md"
if [ "$DRY_RUN" != "1" ]; then
"$PY" - "$RUNS" <<'PY'
import json, os, sys
raiz = sys.argv[1]
linhas = ["| rodada | classes | acc OOF estrita | bal. OOF estrita | acc teste estrita | IC 95% teste (estrita) | acc teste colapsada | IC 95% teste (colapsada) | folds |",
          "|---|---|---|---|---|---|---|---|---|"]
for nome in ["base", "forte", "forte_pad"]:
    p = os.path.join(raiz, nome, "resumo.json")
    if not os.path.exists(p):
        linhas.append(f"| {nome} | ausente | | | | | | | |"); continue
    r = json.load(open(p, encoding="utf-8"))
    o, t, tc = r["oof_atlas"], r["teste_ensemble"], r["teste_ensemble_colapsado"]
    ic, icc = t["ic95_acuracia"], tc["ic95_acuracia"]
    linhas.append(f"| {nome} | {len(r['classes'])} | {o['acuracia']:.3f} | {o['acuracia_balanceada']:.3f} | "
                  f"{t['acuracia']:.3f} | [{ic[0]:.3f}, {ic[1]:.3f}] | {tc['acuracia']:.3f} | [{icc[0]:.3f}, {icc[1]:.3f}] | {r['folds_usados']} |")
linhas += ["", "Estrita: todas as classes contam. Colapsada: previsões das classes só do PAD (queratose actínica, seborreica, nevo) "
           "contam como outras_dermatoses, para comparar com o baseline de 10 classes (mais permissiva). "
           "O atlas não tem imagens dessas três classes, então elas não são avaliadas aqui."]
pr_path = os.path.join(raiz, "forte_pad", "resumo.json")
if os.path.exists(pr_path):
    rp = json.load(open(pr_path, encoding="utf-8")).get("pad_reservado")
    if rp:
        a, e = rp["restrita_pad"], rp["estrita"]
        linhas += ["", f"## PAD reservado (forte_pad): {rp['n_imagens']} imagens de {rp['n_pacientes']} pacientes, fora de qualquer treino", "",
                   "| métrica | valor | IC 95% (bootstrap de pacientes) |", "|---|---|---|",
                   f"| acurácia restrita (só classes do PAD) | {a['acuracia']:.3f} | [{a['ic95_acuracia'][0]:.3f}, {a['ic95_acuracia'][1]:.3f}] |",
                   f"| acurácia balanceada restrita | {a['acuracia_balanceada']:.3f} | [{a['ic95_balanceada'][0]:.3f}, {a['ic95_balanceada'][1]:.3f}] |",
                   f"| acurácia estrita (todas as classes) | {e['acuracia']:.3f} | [{e['ic95_acuracia'][0]:.3f}, {e['ic95_acuracia'][1]:.3f}] |",
                   f"| baseline: sempre a classe majoritária | {rp['baseline_classe_majoritaria_acc']:.3f} | |", "",
                   "| classe | n | recall | precisão | F1 |", "|---|---|---|---|---|"]
        for cls, m in a["por_classe"].items():
            linhas.append(f"| {cls} | {m['n']} | {m['recall']:.3f} | {m['precisao']:.3f} | {m['f1']:.3f} |")
        linhas += ["", "Restrita: o argmax considera só as classes do PAD (mede a distinção entre elas). Estrita: considera todas as classes do modelo. "
                   "Os pacientes são do mesmo domínio do treino do PAD (fotos de celular); isto não mede a generalização para o atlas. "
                   "Matriz de confusão completa em forte_pad/resumo.json."]
open(os.path.join(raiz, "comparacao.md"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")
print("\n".join(linhas))
PY
fi

if [ ${#FALHAS[@]} -gt 0 ]; then
  log "FALHAS: ${FALHAS[*]}"
  exit 1
fi
log "tudo concluído. Resultados em $RUNS/"
