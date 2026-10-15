#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# EyeInsights - Vast.ai Serverless startup
# ============================================================

LOGFILE=/tmp/start_server.sh.log
mkdir -p "$(dirname "$LOGFILE")"
exec > >(tee -a "$LOGFILE") 2>&1

echo "[start_server] $(date -u +'%FT%TZ') iniciando EyeInsights"

# 1. Configurar rutas
REPO_URL="${PYWORKER_REPO:-https://github.com/Cruz1229/vasculometria_bk.git}"
REPO_REF="${PYWORKER_REF:-main}"
REPO_DIR="${PYWORKER_DIR:-/app/eyeinsights}"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8001}"

MODEL_LOG_FILE="${MODEL_LOG_FILE:-/tmp/model/server.log}"
mkdir -p "$(dirname "$MODEL_LOG_FILE")"

echo "[start_server] repositorio: $REPO_URL"
echo "[start_server] directorio: $REPO_DIR"

# 2. Preparar el directorio padre
mkdir -p "$(dirname "$REPO_DIR")"

# 3. Clonar el repositorio si todavía no está disponible
if [ ! -f "$REPO_DIR/worker.py" ]; then
    if [ -e "$REPO_DIR" ]; then
        echo "[start_server] el directorio existe, pero no contiene worker.py"
        echo "[start_server] eliminando directorio incompleto: $REPO_DIR"
        rm -rf "$REPO_DIR"
    fi

    echo "[start_server] clonando repositorio..."
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$REPO_DIR"
else
    echo "[start_server] worker.py encontrado; se reutiliza el repositorio"
fi

cd "$REPO_DIR"

# 4. Verificar estructura del proyecto
for file in requirements.txt worker.py; do
    if [ ! -f "$file" ]; then
        echo "[start_server] ERROR: falta $file en $REPO_DIR"
        exit 1
    fi
done

if [ ! -f app/main.py ]; then
    echo "[start_server] ERROR: no existe app/main.py"
    exit 1
fi

# 5. Verificar herramientas necesarias
for cmd in python git curl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[start_server] ERROR: no se encontró el comando $cmd"
        exit 1
    fi
done

# 6. Instalar dependencias
echo "[start_server] instalando requirements.txt"
python -m pip install --no-cache-dir -r requirements.txt

# PyWorker SDK
echo "[start_server] verificando SDK de Vast.ai"
python -m pip install --no-cache-dir vastai

# 7. Configurar FastAPI
export API_HOST API_PORT
export MODEL_LOG_FILE

echo "[start_server] iniciando FastAPI en ${API_HOST}:${API_PORT}"

python -m uvicorn app.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    > /tmp/model/server.stdout 2>&1 &

API_PID=$!
echo "[start_server] FastAPI PID=$API_PID"

# 8. Esperar a que /health responda
echo "[start_server] esperando http://${API_HOST}:${API_PORT}/health"

API_READY=0

for i in $(seq 1 180); do
    if curl -fsS \
        "http://${API_HOST}:${API_PORT}/health" \
        >/dev/null 2>&1; then
        API_READY=1
        echo "[start_server] API disponible después de ${i}s"
        break
    fi

    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "[start_server] ERROR: FastAPI terminó inesperadamente"
        tail -n 100 /tmp/model/server.stdout || true
        exit 1
    fi

    sleep 1
done

if [ "$API_READY" -ne 1 ]; then
    echo "[start_server] ERROR: la API no respondió en 180 segundos"
    tail -n 100 /tmp/model/server.stdout || true
    kill "$API_PID" 2>/dev/null || true
    exit 1
fi

# 9. Iniciar PyWorker en primer plano
echo "[start_server] iniciando PyWorker"
exec python worker.py