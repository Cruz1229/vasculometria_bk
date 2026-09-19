from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel


class BiomarkersResponse(BaseModel):
    imagen: str
    craek: Optional[float] = None
    crvek: Optional[float] = None
    craek_um: Optional[float] = None
    crvek_um: Optional[float] = None
    avr_knudtson: Optional[float] = None
    area_px: Optional[float] = None
    area_um2: Optional[float] = None
    TI: Optional[float] = None
    median_tortuosity: Optional[float] = None
    disc_diameter_px: Optional[float] = None
    um_per_px: Optional[float] = None


class ClassificationResponse(BaseModel):
    etiqueta: str
    regla_id: int
    pct_sano: float
    pct_sospecha_rh: float
    pct_alto_riesgo_rh: float
    pct_sospecha_rd: float
    pct_alto_riesgo_rd: float
    best_rule_soft: Optional[int] = None
    best_rule_soft_label: Optional[str] = None


class PredictionResponse(BaseModel):
    request_id: str
    filename: str
    biomarkers: BiomarkersResponse
    classification: ClassificationResponse
    artifact_paths: Dict[str, str]


class PreprocessingResponse(BaseModel):
    request_id: str
    filename: str
    artifact_paths: Dict[str, str]


class LUNetResponse(BaseModel):
    request_id: str
    filename: str
    artifact_paths: Dict[str, str]


class PVBMStageResponse(BaseModel):
    request_id: str
    filename: str
    biomarkers: BiomarkersResponse
    artifact_paths: Dict[str, str]


class FuzzyTreeResponse(BaseModel):
    biomarkers: BiomarkersResponse
    classification: ClassificationResponse


class SequentialPipelineResponse(BaseModel):
    request_id: str
    filename: str
    preprocessing: PreprocessingResponse
    lunet: LUNetResponse
    pvbm: PVBMStageResponse
    fuzzy_tree: FuzzyTreeResponse
