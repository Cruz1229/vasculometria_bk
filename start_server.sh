#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# EyeInsights - Vast.ai Serverless startup
# Descarga el repositorio, instala dependencias,
# inicia FastAPI y finalmente ejecuta PyWorker.
# ============================================================

LOGFILE=/var/log/start_server.sh.log
exec > >(tee -a "$LOGFILE") 2>&1

echo "[start_server] $(date -u +'%FT%TZ') iniciando EyeInsights"

# 1. Preparar directorios
cd /workspace

REPO_DIR="${PYWORKER_DIR:-/workspace/eyeinsights}"
REPO_URL="${PYWORKER_REPO:?ERROR: configura PYWORKER_REPO}"
REPO_REF="${PYWORKER_REF:-main}"

mkdir -p /var/log/model

# 2. Obtener el código fuente
if [ ! -f "$REPO_DIR/worker.py" ]; then
    echo "[start_server] clonando $REPO_URL"

    git clone \
        --depth 1 \
        --branch "$REPO_REF" \
        "$REPO_URL" \
        "$REPO_DIR"
else
    echo "[start_server] repositorio ya disponible en $REPO_DIR"
fi

cd "$REPO_DIR"

echo "[start_server] archivos del proyecto:"
ls -la

# 3. Verificar archivos necesarios
for file in requirements.txt worker.py start_server.sh; do
    if [ ! -f "$file" ]; then
        echo "[start_server] ERROR: falta $file"
        exit 1
    fi
done

if [ ! -d app ]; then
    echo "[start_server] ERROR: no existe el directorio app/"
    exit 1
fi

# 4. Instalar dependencias del proyecto
echo "[start_server] instalando requirements.txt"

python -m pip install --no-cache-dir -r requirements.txt

# PyWorker SDK
python -m pip install --no-cache-dir vastai

# 5. Configurar e iniciar FastAPI
export API_HOST=127.0.0.1
export API_PORT=8001

echo "[start_server] iniciando FastAPI en ${API_HOST}:${API_PORT}"

nohup python -m uvicorn app.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    > /var/log/model/server.stdout 2>&1 &

API_PID=$!
echo "[start_server] FastAPI PID=$API_PID"

# 6. Esperar a que la API esté disponible
echo "[start_server] esperando endpoint /health"

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
        echo "[start_server] ERROR: FastAPI terminó"
        tail -n 100 /var/log/model/server.stdout || true
        exit 1
    fi

    sleep 1
done

if [ "$API_READY" -ne 1 ]; then
    echo "[start_server] ERROR: FastAPI no respondió a /health"
    tail -n 100 /var/log/model/server.stdout || true
    kill "$API_PID" 2>/dev/null || true
    exit 1
fi

# 7. Iniciar PyWorker en primer plano
echo "[start_server] iniciando worker.py"

exec python worker.py