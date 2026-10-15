#!/usr/bin/env bash
set -Eeuo pipefail

LOGFILE=/tmp/start_server.sh.log
mkdir -p "$(dirname "$LOGFILE")"
exec > >(tee -a "$LOGFILE") 2>&1

echo "[start_server] $(date -u +'%FT%TZ') iniciando EyeInsights"
export GIT_TERMINAL_PROMPT=0

# --- Configuración ---
REPO_URL="${PYWORKER_REPO:-https://github.com/Cruz1229/vasculometria_bk.git}"
REPO_REF="${PYWORKER_REF:-main}"
REPO_DIR="/app"

API_HOST="${API_HOST:-127.0.0.1}"
MODEL_SERVER_PORT="${MODEL_SERVER_PORT:-18000}"
API_PORT="$MODEL_SERVER_PORT"   # uvicorn y worker.py usan el mismo puerto
MODEL_LOG_FILE="${MODEL_LOG_FILE:-/tmp/model/server.log}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-1800}"

BENCHMARK_IMAGE_PATH="${BENCHMARK_IMAGE_PATH:-/app/benchmark/retina.jpeg}"

mkdir -p "$(dirname "$MODEL_LOG_FILE")" "$REPO_DIR"

# ---------- Clonar el repo dentro de /app ----------
if [ ! -f "$REPO_DIR/worker.py" ]; then
    echo "[start_server] clonando $REPO_URL ($REPO_REF) en $REPO_DIR"
    TMP_CLONE="$(mktemp -d)"
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$TMP_CLONE"
    cp -a "$TMP_CLONE"/. "$REPO_DIR"/
    rm -rf "$TMP_CLONE"
else
    echo "[start_server] worker.py ya existe en $REPO_DIR; se reutiliza"
fi
cd "$REPO_DIR"

# ---------- Verificar estructura ----------
for f in requirements.txt worker.py app/main.py; do
    [ -f "$f" ] || { echo "[start_server] ERROR: falta $REPO_DIR/$f"; exit 1; }
done

mkdir -p "$RETINAL_API_BASE_DIR"
[ -f "$BENCHMARK_IMAGE_PATH" ] || echo "[start_server] AVISO: no existe $BENCHMARK_IMAGE_PATH (el benchmark fallará)"

# ---------- Dependencias ----------
echo "[start_server] instalando requirements.txt"
python -m pip install --no-cache-dir -r requirements.txt

# ---------- Variables para la app y el worker ----------
export API_HOST API_PORT MODEL_SERVER_PORT MODEL_LOG_FILE
export MODEL_SERVER_URL="${MODEL_SERVER_URL:-http://127.0.0.1}"
export RETINAL_API_BASE_DIR LUNET_DIR PVBM_DIR LUNET_WEIGHTS BENCHMARK_IMAGE_PATH

# ---------- FastAPI (su log va al archivo que lee el PyWorker) ----------
# La app descarga pesos y carga modelos en su arranque; /health responde al terminar.
echo "[start_server] iniciando FastAPI en ${API_HOST}:${API_PORT}"
python -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" \
    > "$MODEL_LOG_FILE" 2>&1 &
API_PID=$!

API_READY=0
for i in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
        API_READY=1; echo "[start_server] API lista tras ${i}s"; break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "[start_server] ERROR: FastAPI terminó"; tail -n 100 "$MODEL_LOG_FILE"; exit 1
    fi
    sleep 1
done

if [ "$API_READY" -ne 1 ]; then
    echo "[start_server] ERROR: /health no respondió en ${HEALTH_TIMEOUT}s"
    tail -n 100 "$MODEL_LOG_FILE" || true
    kill "$API_PID" 2>/dev/null || true
    exit 1
fi

# ---------- PyWorker ----------
echo "[start_server] iniciando PyWorker"
exec python worker.py