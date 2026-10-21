import torch
from arq.connections import RedisSettings
from app.config import NUM_THREADS, REDIS_PORT, REDIS_HOST, MAX_JOBS, JOB_TIMEOUT, KEEP_RESULT

# Restringir hilos para optimizar consumo de CPU/RAM
torch.set_num_threads(NUM_THREADS)


async def startup(ctx: dict):
    from app.services.pipeline import RetinalPipelineService

    service = RetinalPipelineService()
    if hasattr(service, 'startup'):
        service.startup()

    ctx['pipeline_service'] = service


async def run_sequential_pipeline_task(ctx: dict, content: bytes, filename: str) -> dict:

    service = ctx['pipeline_service']
    result = service.run_sequential(content, filename, include_diameter_images=True)

    if hasattr(result, 'model_dump'):
        return result.model_dump()
    return result.dict()


class WorkerSettings:
    functions = [run_sequential_pipeline_task]
    on_startup = startup
    redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)
    max_jobs = MAX_JOBS
    job_timeout = JOB_TIMEOUT
    keep_result = KEEP_RESULT
