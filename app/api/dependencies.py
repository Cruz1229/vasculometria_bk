from fastapi import Request
from app.services.pipeline import RetinalPipelineService


def get_service(request: Request) -> RetinalPipelineService:
    return request.app.state.pipeline_service
