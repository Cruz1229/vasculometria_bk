from __future__ import annotations

from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.config import CORS_ALLOW_ORIGINS, CORS_ALLOW_ORIGIN_REGEX, CORS_ALLOW_CREDENTIALS, REDIS_HOST, REDIS_PORT, \
    LOAD_MODELS_ON_STARTUP
from app.infrastructure.logging import LOGGER
from app.services.pipeline import RetinalPipelineService


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info(
        "startup: cors allow_origins=%s allow_origin_regex=%s allow_credentials=%s",
        CORS_ALLOW_ORIGINS, CORS_ALLOW_ORIGIN_REGEX, CORS_ALLOW_CREDENTIALS,
    )

    if LOAD_MODELS_ON_STARTUP:
        app.state.pipeline_service.startup()

    app.state.arq_redis = await create_pool(RedisSettings(host=REDIS_HOST, port=REDIS_PORT))

    yield

    await app.state.arq_redis.close()


def create_app(service: RetinalPipelineService | None = None) -> FastAPI:
    application = FastAPI(
        title="Retinal Pipeline API",
        version="1.1.0",
        description="API para preprocesamiento, segmentación, extracción de biomarcadores y clasificación retinal.",
        lifespan=lifespan,
    )
    application.state.pipeline_service = service if service is not None else RetinalPipelineService()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()
