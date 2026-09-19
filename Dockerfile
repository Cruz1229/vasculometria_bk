FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app.py ./app.py
COPY models ./models
RUN mkdir -p /app/runtime

ENV RETINAL_API_BASE_DIR=/app/runtime \
    LUNET_DIR=/app/models/LUNet \
    PVBM_DIR=/app/models/PVBM \
    LUNET_WEIGHTS=/app/models/LUNet/lunet_modelbest.h5 \
    PORT=10000

EXPOSE 10000

CMD ["bash", "-lc", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
