import base64
import os
from pathlib import Path

from vastai import Worker, WorkerConfig, HandlerConfig, BenchmarkConfig, LogActionConfig

MODEL_SERVER_URL = os.getenv('MODEL_SERVER_URL', '127.0.0.1')
MODEL_SERVER_PORT = int(os.getenv('MODEL_SERVER_PORT', '18000'))
MODEL_LOG_FILE = os.getenv('MODEL_LOG_FILE', '/app/runtime/api.log')

BENCHMARK_IMAGE_PATH = os.getenv('BENCHMARK_IMAGE_PATH', '')
PIPELINE_ROUTE = '/pipeline/sequential/v1'


def benchmark_generator() -> dict:
    if not BENCHMARK_IMAGE_PATH:
        raise RuntimeError(
            "Configura BENCHMARK_IMAGE_PATH con una imagen "
            "de prueba válida para EyeInsights.")

    image_path = Path(BENCHMARK_IMAGE_PATH)

    if not image_path.is_file():
        raise FileNotFoundError(f"No se encontró la imagen de prueba: {image_path}")

    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")

    return {
        "filename": image_path.name,
        "image_base64": image_base64,
    }


worker_config = WorkerConfig(
    model_server_url=MODEL_SERVER_URL,
    model_server_port=MODEL_SERVER_PORT,
    model_log_file=MODEL_LOG_FILE,

    handlers=[
        HandlerConfig(
            route=PIPELINE_ROUTE,
            allow_parallel_requests=False,
            max_queue_time=180.0,
            workload_calculator=lambda payload: 1.0,
            benchmark_config=BenchmarkConfig(
                generator=benchmark_generator,
                runs=1,
                concurrency=1
            )
        )
    ],

    log_action_config=LogActionConfig(
        on_load=[
            "INFO:     Application startup complete.",
        ],
        on_error=[
            "Traceback (most recent call last):",
        ]
    )
)

if __name__ == "__main__":
    Worker(worker_config).run()