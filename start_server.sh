#!/bin/bash
set -Eeuo pipefail

LOGFILE=/var/log/start_server.sh.log
exec > >(tee -a "$LOGFILE") 2>&1

echo "[start_server] $(date -u +'%FT%TZ') iniciando EyeInsights"

# 1. Ubicarse en la raíz del repositorio
cd "$(dirname "$0")"
REPO_DIR="$(pwd)"

# 2. Configurar la API
export API_HOST=127.0.0.1
export API_PORT=8001

mkdir -p /var/log/model
export MODEL_LOG_FILE=/var/log/model/server.log

# 3. Iniciar FastAPI en segundo plano
echo "[start_server] iniciando FastAPI..."

nohup python -m uvicorn app.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    > /var/log/model/server.stdout 2>&1 &

API_PID=$!
echo "[start_server] FastAPI PID=$API_PID"

# 4. Esperar a que FastAPI esté disponible
echo "[start_server] esperando API..."

READY=0

for i in $(seq 1 120); do
    if curl -fsS "http://${API_HOST}:${API_PORT}/health" \
    >/dev/null 2>&1; then
        READY=1
        echo "[start_server] API disponible después de ${i}s"
        break
    fi

    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "[start_server] ERROR: FastAPI terminó inesperadamente"
        tail -n 100 /var/log/model/server.stdout || true
        exit 1
    fi

    sleep 1
done

if [ "$READY" -ne 1 ]; then
    echo "[start_server] ERROR: la API no respondió en 120 segundos"
    tail -n 100 /var/log/model/server.stdout || true
    kill "$API_PID" 2>/dev/null || true
    exit 1
fi

# 5. Iniciar PyWorker en primer plano
echo "[start_server] iniciando PyWorker..."

cd "$REPO_DIR"
exec python worker.py