from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas import SequentialPipelineResponse


class StatusTask(Enum):
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class TaskMetadata(BaseModel):
    task_id: str
    model: str = 'BeiT-DR'
    status: StatusTask
    message: Optional[str] = None


class Prediction(BaseModel):
    label: str
    score: float


class ProcessedImage(BaseModel):
    label: str
    img64: str


class AiModelResponse(BaseModel):
    predictions: list[Prediction] = []
    images: list[ProcessedImage] = []


class AiModelRequest(BaseModel):
    filename: str = Field(min_length=1)
    image_base64: str = Field(min_length=1)


class TaskResultResponse(BaseModel):
    metadata: TaskMetadata
    result: Optional[AiModelResponse] = None


def to_ai_model_response(prediction_response: SequentialPipelineResponse | dict) -> AiModelResponse:

    if isinstance(prediction_response, dict):
        prediction_response = SequentialPipelineResponse.model_validate(prediction_response)

    clasification_response = prediction_response.fuzzy_tree.classification

    images64 = [
        ProcessedImage(label=label, img64=base64_str)
        for label, base64_str in prediction_response.images.items()
    ]
    predictions = [
        Prediction(label="pctsano", score=clasification_response.pct_sano / 100.0),
        Prediction(label="pctsospecharh", score=clasification_response.pct_alto_riesgo_rh / 100.0),
        Prediction(label="pctaltoriesgorh", score=clasification_response.pct_alto_riesgo_rh / 100.0),
        Prediction(label="pctsospechard", score=clasification_response.pct_sospecha_rd / 100.0),
        Prediction(label="pctaltoriesgord", score=clasification_response.pct_alto_riesgo_rd / 100.0),
    ]

    return AiModelResponse(predictions=predictions, images=images64)
