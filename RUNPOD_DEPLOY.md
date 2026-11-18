# RunPod GPU Pod deployment

This repository is a FastAPI **Pod**, not a RunPod Serverless worker. The legacy `worker.py` and `start_server.sh` target Vast.ai; do not run them on a Pod.

## Deploy using an inexpensive GPU

1. In RunPod Console > Pods > Deploy, choose **Community Cloud** and sort available NVIDIA GPUs by hourly price. Try the RTX A2000 6 GB only if you can test inference memory; if out-of-memory, select a 16 GB RTX A4000 or the least expensive GPU with >= 16 GB VRAM.
2. Select a RunPod **PyTorch / CUDA-compatible GPU Pod image with Python 3.11** and an interactive terminal. Expose **HTTP port 8001** and leave disk sufficient for the repo (~70 MB weights plus dependencies and runtime); budget >= 25 GB of free writable space. Do not use SSH-only exposure for an HTTP client.
3. Set Pod environment variables **BACKEND_SECRET_TOKEN** (generate a long random token), **REQUIRE_BACKEND_TOKEN_HEADER=true**, **LUNET_TF_DEVICE=/GPU:0**, **TF_GPU_MEMORY_GROWTH=true**, **LOAD_MODELS_ON_STARTUP=true**, **USE_ARQ_MODEL_LOADING=false**, **RETINAL_API_BASE_DIR=/workspace/retinal-runtime**. Restrict **RETINAL_API_CORS_ALLOW_ORIGINS** to the actual frontend origin instead of `*`.
4. In the Pod terminal run:

```bash
set -e
cd /workspace
git clone --depth 1 --branch deploy/runpod-pods-20261117 https://github.com/Cruz1229/vasculometria_bk.git
cd vasculometria_bk
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
mkdir -p /workspace/retinal-runtime
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Do not install `requirements-torch.txt` for the basic FastAPI pipeline; the advanced ARQ worker uses torch but is disabled by default. Make sure the Pod has enough system RAM and compatible CUDA libraries for `tensorflow[and-cuda]` and `onnxruntime-gpu`.

5. Test **https://<POD_ID>-8001.proxy.runpod.net/health**, then authenticated endpoint using:

```bash
curl -X POST "https://<POD_ID>-8001.proxy.runpod.net/pipeline/sequential" \
  -H "X-Backend-Token: YOUR_SECRET_TOKEN" \
  -F "file=@retina.jpg"
```

The existing `/pipeline/sequential/v1` endpoint authenticates the token in its JSON body. **Do not send patient images or other sensitive information until HTTPS, authentication, retention and compliance are verified.**

## Troubleshooting

- `/health` returns OK but prediction fails: startup is not a full inference test. Inspect TensorFlow GPU visibility, ONNX execution providers, model weights and logs.
- CUDA out-of-memory: use a >=16 GB VRAM GPU, keep one Uvicorn worker and process one image at a time.
- Unexpected 403: ensure Pod environment has `REQUIRE_BACKEND_TOKEN_HEADER=true`; do not try to fix this by setting `ALLOWED_IPS=*`.
- ONNX optic disc weights are downloaded from Hugging Face if missing, so Pod requires internet during first initialization; allow extra writable disk.
- Pod costs accrue while it runs. Stop it when idle and verify RunPod storage billing/termination semantics.
- For durable deployment, build and publish a container image from the repo and deploy that custom image instead of reinstalling dependencies at each Pod start.

**Notes:** Prices and GPU inventory vary by region, availability and Cloud type; confirm displayed total before deploying. An HTTP proxy may impose request duration or size limits. The API route uses potentially long-running image analysis; measure actual response time and consider a background-job architecture if necessary.
