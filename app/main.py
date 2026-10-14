from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import CORS_ALLOW_ORIGINS, CORS_ALLOW_ORIGIN_REGEX, CORS_ALLOW_CREDENTIALS, REDIS_HOST, REDIS_PORT, \
    LOAD_MODELS_ON_STARTUP, USE_ARQ_MODEL_LOADING, ALLOWED_IPS, TOKEN_HEADER_NAME, BACKEND_SECRET_TOKEN
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

    if USE_ARQ_MODEL_LOADING:
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


@app.middleware('http')
async def security_middleware(request: Request, call_next):

    if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
        return await call_next(request)

    # Validación de IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Si va detrás de Nginx, Traefik o un balanceador de carga
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None

    if client_ip not in ALLOWED_IPS:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": f"Acceso prohibido. IP no autorizada: {client_ip}"})

    # Validación de Token
    client_token = request.headers.get(TOKEN_HEADER_NAME)

    if not client_token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": f"Falta la cabecera de autenticación: {TOKEN_HEADER_NAME}"})

    # Comparación segura en tiempo constante contra ataques de temporización
    is_token_valid = secrets.compare_digest(client_token, BACKEND_SECRET_TOKEN)

    if not is_token_valid:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Token del backend no válido"})

    # Si pasa ambas validaciones, la petición continúa hacia el endpoint correspondiente
    response = await call_next(request)
    return response
