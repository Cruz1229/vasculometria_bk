from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from app.schemas import (
    BiomarkersResponse, ClassificationResponse, PredictionResponse,
    PreprocessingResponse, LUNetResponse, PVBMStageResponse,
    FuzzyTreeResponse, SequentialPipelineResponse,
)
from app.infrastructure.logging import LOGGER, _elapsed_ms
from app.infrastructure.model_loader import ModelBundle, load_models
from app.infrastructure.storage import PipelineContext, create_context, build_artifact_paths, ensure_runtime_dirs
from app.services.preprocessing import preprocess_image
from app.services.segmentation import segment_image
from app.services.biomarkers import extract_features
from app.services.classification import classify_metrics


class RetinalPipelineService:
    def __init__(self) -> None:
        self.models = ModelBundle()
        self._started = False

    def startup(self) -> None:
        if self._started:
            return
        started = time.perf_counter()
        LOGGER.info("startup: begin")
        ensure_runtime_dirs()
        self.models = load_models()
        self._started = True
        LOGGER.info("startup: models_loaded total_ms=%.2f", _elapsed_ms(started))

    def run(self, image_bytes: bytes, filename: str) -> PredictionResponse:
        pipeline = self.run_sequential(image_bytes, filename)
        return PredictionResponse(
            request_id=pipeline.request_id,
            filename=pipeline.filename,
            biomarkers=pipeline.pvbm.biomarkers,
            classification=pipeline.fuzzy_tree.classification,
            artifact_paths=pipeline.pvbm.artifact_paths,
        )

    def run_preprocessing(self, image_bytes: bytes, filename: str) -> PreprocessingResponse:
        context = create_context(image_bytes, filename)
        response, _preprocessed_path = self._run_preprocessing_stage(context)
        return response

    def run_lunet(self, image_bytes: bytes, filename: str) -> LUNetResponse:
        context = create_context(image_bytes, filename)
        _preprocessing, preprocessed_path = self._run_preprocessing_stage(context)
        response, _artery_path, _vein_path, _vessel_path = self._run_lunet_stage(
            context,
            preprocessed_path=preprocessed_path,
        )
        return response

    def run_pvbm(self, image_bytes: bytes, filename: str) -> PVBMStageResponse:
        context = create_context(image_bytes, filename)
        _preprocessing, preprocessed_path = self._run_preprocessing_stage(context)
        _lunet, artery_path, vein_path, vessel_path = self._run_lunet_stage(
            context,
            preprocessed_path=preprocessed_path,
        )
        response, _biomarkers = self._run_pvbm_stage(
            context,
            artery_path=artery_path,
            vein_path=vein_path,
            preprocessed_path=preprocessed_path,
            vessel_path=vessel_path,
        )
        return response

    def run_fuzzy_tree(self, biomarkers: Dict[str, Any]) -> FuzzyTreeResponse:
        response, _classification = self._run_fuzzy_tree_stage(biomarkers)
        return response

    def run_sequential(self, image_bytes: bytes, filename: str) -> SequentialPipelineResponse:
        total_started = time.perf_counter()
        context = create_context(image_bytes, filename)

        LOGGER.info(
            "pipeline[%s]: started filename=%s bytes=%s",
            context.request_id,
            context.filename,
            len(image_bytes),
        )

        try:
            preprocessing, preprocessed_path = self._run_preprocessing_stage(context)
            lunet, artery_path, vein_path, vessel_path = self._run_lunet_stage(
                context,
                preprocessed_path=preprocessed_path,
            )
            pvbm, biomarkers = self._run_pvbm_stage(
                context,
                artery_path=artery_path,
                vein_path=vein_path,
                preprocessed_path=preprocessed_path,
                vessel_path=vessel_path,
            )
            fuzzy_tree, _classification = self._run_fuzzy_tree_stage(biomarkers)

            response = SequentialPipelineResponse(
                request_id=context.request_id,
                filename=context.filename,
                preprocessing=preprocessing,
                lunet=lunet,
                pvbm=pvbm,
                fuzzy_tree=fuzzy_tree,
            )
            LOGGER.info(
                "pipeline[%s]: completed total_ms=%.2f",
                context.request_id,
                _elapsed_ms(total_started),
            )
            return response
        except Exception:
            LOGGER.exception(
                "pipeline[%s]: failed filename=%s elapsed_ms=%.2f",
                context.request_id,
                context.filename,
                _elapsed_ms(total_started),
            )
            raise

    def _run_preprocessing_stage(self, context: PipelineContext) -> Tuple[PreprocessingResponse, Path]:
        started = time.perf_counter()
        LOGGER.info("preprocess[%s]: started filename=%s", context.request_id, context.filename)
        preprocessed_path = preprocess_image(context.image, context.safe_name)
        LOGGER.info(
            "preprocess[%s]: completed elapsed_ms=%.2f output=%s",
            context.request_id,
            _elapsed_ms(started),
            preprocessed_path,
        )
        response = PreprocessingResponse(
            request_id=context.request_id,
            filename=context.filename,
            artifact_paths=build_artifact_paths(
                input_path=context.input_path,
                preprocessed_path=preprocessed_path,
            ),
        )
        return response, preprocessed_path

    def _run_lunet_stage(
        self,
        context: PipelineContext,
        *,
        preprocessed_path: Optional[Path] = None,
    ) -> Tuple[LUNetResponse, Path, Path, Path]:
        started = time.perf_counter()
        LOGGER.info("lunet[%s]: started filename=%s", context.request_id, context.filename)
        if preprocessed_path is None:
            preprocessed_path = preprocess_image(context.image, context.safe_name)
        artery_path, vein_path, vessel_path = segment_image(self.models.model, context.image, context.safe_name)
        LOGGER.info(
            "lunet[%s]: completed elapsed_ms=%.2f",
            context.request_id,
            _elapsed_ms(started),
        )
        response = LUNetResponse(
            request_id=context.request_id,
            filename=context.filename,
            artifact_paths=build_artifact_paths(
                input_path=context.input_path,
                preprocessed_path=preprocessed_path,
                artery_path=artery_path,
                vein_path=vein_path,
                vessel_path=vessel_path,
            ),
        )
        return response, artery_path, vein_path, vessel_path

    def _run_pvbm_stage(
        self,
        context: PipelineContext,
        *,
        artery_path: Path,
        vein_path: Path,
        preprocessed_path: Optional[Path] = None,
        vessel_path: Optional[Path] = None,
    ) -> Tuple[PVBMStageResponse, Dict[str, Any]]:
        started = time.perf_counter()
        LOGGER.info("pvbm[%s]: started filename=%s", context.request_id, context.filename)
        biomarkers = extract_features(self.models, context.input_path, artery_path, vein_path)
        LOGGER.info(
            "pvbm[%s]: completed elapsed_ms=%.2f",
            context.request_id,
            _elapsed_ms(started),
        )
        response = PVBMStageResponse(
            request_id=context.request_id,
            filename=context.filename,
            biomarkers=BiomarkersResponse(**biomarkers),
            artifact_paths=build_artifact_paths(
                input_path=context.input_path,
                preprocessed_path=preprocessed_path,
                artery_path=artery_path,
                vein_path=vein_path,
                vessel_path=vessel_path,
            ),
        )
        return response, biomarkers

    def _run_fuzzy_tree_stage(self, biomarkers: Dict[str, Any]) -> Tuple[FuzzyTreeResponse, Dict[str, Any]]:
        started = time.perf_counter()
        image_name = biomarkers.get("imagen", "desconocida")
        LOGGER.info("fuzzy_tree[%s]: started", image_name)
        classification = classify_metrics(biomarkers)
        LOGGER.info(
            "fuzzy_tree[%s]: completed elapsed_ms=%.2f label=%s rule_id=%s",
            image_name,
            _elapsed_ms(started),
            classification.get("etiqueta"),
            classification.get("regla_id"),
        )
        response = FuzzyTreeResponse(
            biomarkers=BiomarkersResponse(**biomarkers),
            classification=ClassificationResponse(**classification),
        )
        return response, classification
