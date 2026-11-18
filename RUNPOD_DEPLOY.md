# RunPod GPU Pod deployment

Use a RunPod GPU Pod for FastAPI. The legacy Vast.ai worker and startup scripts are for a separate deployment.

## Pod configuration

1. Select an available NVIDIA GPU. The RTX 3070 with 8 GB was verified with one Uvicorn worker and 1024 × 1024 LUNet input using the graph settings below.
2. Select the official image `runpod/pytorch:2.1.0-cu1281-torch280-ubuntu2404`. Expose HTTP port **8001**. The image's Nginx process already owns that port and forwards to localhost:8000. Run Uvicorn on **127.0.0.1:8000** inside this image.
3. Use the RunPod web terminal for setup. Leave the Jupyter and SSH options off when they are unnecessary. The running Pod can use a 50 GB container disk without an extra volume. Stopping a Pod erases the container disk; attach persistent storage or automate setup at container start if the deployment must survive a restart.

## Install and launch

In the Pod terminal:

```bash
cd /workspace
git clone --depth 1 --branch deploy/runpod-pods-20261117 https://github.com/Cruz1229/vasculometria_bk.git
cd vasculometria_bk
python3.11 -m venv /workspace/retinal-venv
source /workspace/retinal-venv/bin/activate

# Keep only the headless OpenCV wheel in this environment.
sed '/^opencv-python$/d' requirements.txt > /workspace/retinal-requirements.txt
python -m pip install --no-cache-dir -r /workspace/retinal-requirements.txt
python -m pip check

cuda_libs=$(find "$VIRTUAL_ENV/lib/python3.11/site-packages/nvidia" -type d -name lib | paste -sd: -)
export LD_LIBRARY_PATH="$cuda_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LUNET_TF_DEVICE=/GPU:0 TF_GPU_MEMORY_GROWTH=true TF_FORCE_GPU_ALLOW_GROWTH=true
export LUNET_GRAPH_INFERENCE=true TF_GPU_ALLOCATOR=cuda_malloc_async
export TF_CUDNN_USE_AUTOTUNE=1 TF_CUDNN_WORKSPACE_LIMIT_IN_MB=512
export LOAD_MODELS_ON_STARTUP=true USE_ARQ_MODEL_LOADING=false REQUIRE_BACKEND_TOKEN_HEADER=true
export RETINAL_API_BASE_DIR=/workspace/retinal-runtime
export RETINAL_API_CORS_ALLOW_ORIGINS="https://${RUNPOD_POD_ID:?Missing Pod ID}-8001.proxy.runpod.net"
export MPLBACKEND=Agg HF_HUB_DISABLE_XET=1

# Use an injected RunPod Secret if configured, or create a private Pod-local token.
if [ -z "${BACKEND_SECRET_TOKEN:-}" ]; then
  if [ ! -s /workspace/.retinal-api-token ]; then
    (umask 077; python -c 'import secrets; print(secrets.token_urlsafe(48))' > /workspace/.retinal-api-token)
  fi
  export BACKEND_SECRET_TOKEN="$(cat /workspace/.retinal-api-token)"
fi

nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 \
  > /workspace/retinal-api.log 2>&1 < /dev/null &
```

The LUNet weights are tracked in the repository. On first startup, PVBM downloads the optic disc ONNX model from Hugging Face if missing. The CUDA libraries from the virtual environment take precedence for both TensorFlow and ONNX Runtime.

## Verify

Replace `retina.jpg` with a public test image without sensitive information.

```bash
base_url="https://${RUNPOD_POD_ID:?Missing Pod ID}-8001.proxy.runpod.net"
curl --fail-with-body "$base_url/health"
printf 'X-Backend-Token: %s\n' "$BACKEND_SECRET_TOKEN" |
  curl --fail-with-body --header @- -F 'file=@retina.jpg;type=image/jpeg' \
    "$base_url/pipeline/sequential?include_diameter_images=false" > result.json
```

Swagger is at `/docs`. Requests to the multipart pipeline must supply `X-Backend-Token`. The legacy JSON endpoint at `/pipeline/sequential/v1` uses its existing token field.

## Troubleshooting

- An HTML response or HTTP 405 from the exposed port can come from the template's welcome page while Uvicorn is unavailable. Check for JSON at `/health` and inspect `/workspace/retinal-api.log`.
- If TensorFlow cannot allocate GPU memory at 1024 × 1024, use graph execution and the allocator settings above. Use a larger GPU if the pipeline still exhausts memory.
- Check the active provider on a real ONNX inference session using `session.get_providers()`. The list of providers installed in the package alone cannot confirm CUDA inference.
