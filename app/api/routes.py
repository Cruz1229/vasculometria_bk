from __future__ import annotations
from pathlib import Path
from arq.jobs import Job, JobStatus
from fastapi import Request
from app.arq.task_enqueued_response import StatusTask, TaskResultResponse, TaskMetadata, to_ai_model_response, \
    AiModelResponse
from typing import Annotated, Dict, Tuple, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.infrastructure.storage import diameter_image_path
from app.config import SUPPORTED_IMAGE_SUFFIXES
from app.api.dependencies import get_service
from app.services.pipeline import RetinalPipelineService
from app.schemas import (
    BiomarkersResponse, ClassificationResponse, PredictionResponse,
    PreprocessingResponse, LUNetResponse, PVBMStageResponse,
    FuzzyTreeResponse, SequentialPipelineResponse,
)

router = APIRouter()
Service = Annotated[RetinalPipelineService, Depends(get_service)]


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/ping", include_in_schema=False)
def runpod_health() -> Dict[str, str]:
    return health()


async def _read_uploaded_image(file: UploadFile) -> Tuple[bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Debes enviar un archivo con nombre")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Formato no soportado")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    return content, file.filename


def _service_error_to_http(exc: Exception, stage_name: str) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Error en {stage_name}: {exc}")


@router.post("/stages/preprocess", response_model=PreprocessingResponse)
async def preprocess_stage(service: Service, file: UploadFile = File(...)) -> PreprocessingResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        return service.run_preprocessing(content, filename)
    except Exception as exc:
        raise _service_error_to_http(exc, "preprocesamiento") from exc


@router.post("/stages/lunet", response_model=LUNetResponse)
async def lunet_stage(service: Service, file: UploadFile = File(...)) -> LUNetResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        return service.run_lunet(content, filename)
    except Exception as exc:
        raise _service_error_to_http(exc, "LUNET") from exc


@router.post("/stages/pvbm", response_model=PVBMStageResponse)
async def pvbm_stage(service: Service, file: UploadFile = File(...), include_diameter_images: bool | None = None) -> PVBMStageResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        return service.run_pvbm(content, filename, include_diameter_images=include_diameter_images)
    except Exception as exc:
        raise _service_error_to_http(exc, "PVBM") from exc


@router.get(
    "/artifacts/{request_id}/diameters/{vessel_type}",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}, 404: {"description": "Imagen no disponible"}},
)
def download_diameter_image(request_id: UUID, vessel_type: Literal["artery", "vein"]) -> FileResponse:
    try:
        path = diameter_image_path(str(request_id), vessel_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Imagen no disponible") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no disponible: solicita su generación y verifica que existan mediciones válidas")
    return FileResponse(path, media_type="image/png", filename=path.name, content_disposition_type="inline")


@router.post("/stages/fuzzy-proximity-tree", response_model=FuzzyTreeResponse)
def fuzzy_proximity_tree_stage(payload: BiomarkersResponse, service: Service) -> FuzzyTreeResponse:
    try:
        return service.run_fuzzy_tree(payload.model_dump())
    except Exception as exc:
        raise _service_error_to_http(exc, "Árbol de proximidad difusa") from exc


@router.post("/pipeline/sequential", response_model=SequentialPipelineResponse)
async def run_pipeline_sequential(
        service: Service, file: UploadFile = File(...), include_diameter_images: bool | None = None,
) -> SequentialPipelineResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        return service.run_sequential(content, filename, include_diameter_images=include_diameter_images)
    except Exception as exc:
        raise _service_error_to_http(exc, "pipeline secuencial") from exc


@router.post("/pipeline/sequential/v1", response_model=AiModelResponse)
async def run_pipeline_sequential(service: Service, file: UploadFile = File(...)) -> AiModelResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        response = service.run_sequential(content, filename, include_diameter_images=True)
        return to_ai_model_response(response)
    except Exception as exc:
        raise _service_error_to_http(exc, "pipeline secuencial") from exc


# Endpoint para encolar las peticiones
@router.post('/pipeline/sequential/v2', response_model=TaskResultResponse, response_model_exclude_none=True)
async def run_pipeline_sequential(request: Request, file: UploadFile = File(...)) -> TaskResultResponse:
    content, filename = await _read_uploaded_image(file)

    try:
        arq_redis = request.app.state.arq_redis

        job = await arq_redis.enqueue_job('run_sequential_pipeline_task', content, filename)

        return TaskResultResponse(
            metadata=TaskMetadata(
                task_id=job.job_id,
                status=StatusTask.QUEUED,
                message="El análisis de retina ha sido encolado correctamente."))

    except Exception as exc:
        raise _service_error_to_http(exc, 'pipeline secuencial asíncrono') from exc


@router.get('/pipeline/task/{task_id}', response_model=TaskResultResponse, response_model_exclude_none=True)
async def get_pipeline_task_status(request: Request, task_id: str) -> TaskResultResponse:
    arq_redis = request.app.state.arq_redis
    job = Job(task_id, arq_redis)

    # Estado actual de la tarea
    status = await job.status()

    # Si la tarea expiró o el ID es inválido
    if status == JobStatus.not_found:
        raise HTTPException(status_code=404, detail=f"Tarea con ID '{task_id}' no encontrada.")

    # Si la tarea aún está en cola o procesándose
    if status in (JobStatus.deferred, JobStatus.queued, JobStatus.in_progress):
        metadata = TaskMetadata(
            task_id=task_id,
            status=StatusTask.PROCESSING)
        return TaskResultResponse(metadata=metadata)

    # 3. Si la tarea ya finalizó
    job_result = await job.result_info()

    if job_result and job_result.success:
        metadata = TaskMetadata(
            task_id=task_id,
            status=StatusTask.COMPLETED)
        result = to_ai_model_response(job_result.result)
        return TaskResultResponse(metadata=metadata, result=result)

    # Ocurrió una excepción no controlada en el Worker
    error_msg = str(job_result.result) if (job_result and job_result.result) else "Error interno en el procesamiento."
    raise HTTPException(status_code=500, detail=f"La tarea falló: {error_msg}")


@router.post("/predict", response_model=PredictionResponse)
async def predict(service: Service, file: UploadFile = File(...)) -> PredictionResponse:
    content, filename = await _read_uploaded_image(file)
    try:
        return service.run(content, filename)
    except Exception as exc:
        raise _service_error_to_http(exc, "pipeline completo") from exc


@router.post("/classify-from-biomarkers", response_model=ClassificationResponse)
def classify_from_biomarkers(payload: BiomarkersResponse, service: Service) -> ClassificationResponse:
    fuzzy_tree = service.run_fuzzy_tree(payload.model_dump())
    return fuzzy_tree.classification
