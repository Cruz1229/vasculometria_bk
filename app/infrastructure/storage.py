from __future__ import annotations

import base64
import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from PIL import Image
from app.config import INPUT_DIR, PREPROCESSED_DIR, ARTERY_DIR, VEIN_DIR, VESSEL_DIR, VIS_DIR, RESULTS_DIR


@dataclass(frozen=True)
class PipelineContext:
    request_id: str
    filename: str
    safe_name: str
    input_path: Path
    image: Image.Image


def ensure_runtime_dirs() -> None:
    for folder in [INPUT_DIR, PREPROCESSED_DIR, ARTERY_DIR, VEIN_DIR, VESSEL_DIR, VIS_DIR, RESULTS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def diameter_image_path(request_id: str, vessel_type: str) -> Path:
    if vessel_type not in {"artery", "vein"}:
        raise ValueError("Tipo de vaso no válido")
    root = VIS_DIR.resolve()
    path = (root / uuid.UUID(request_id).hex / f"diameters_{vessel_type}.png").resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ruta de imagen no válida")
    return path


def create_context(image_bytes: bytes, filename: str) -> PipelineContext:
    ensure_runtime_dirs()
    request_id = uuid.uuid4().hex
    stem = Path(filename).stem
    safe_name = f"{stem}_{request_id}.png"
    input_path = INPUT_DIR / safe_name

    with open(input_path, "wb") as f:
        f.write(image_bytes)

    with Image.open(io.BytesIO(image_bytes)) as uploaded_image:
        image = uploaded_image.convert("RGB")

    return PipelineContext(
        request_id=request_id,
        filename=filename,
        safe_name=safe_name,
        input_path=input_path,
        image=image,
    )


def build_artifact_paths(
    *,
    input_path: Optional[Path] = None,
    preprocessed_path: Optional[Path] = None,
    artery_path: Optional[Path] = None,
    vein_path: Optional[Path] = None,
    vessel_path: Optional[Path] = None,
) -> Dict[str, str]:
    artifact_paths: Dict[str, str] = {}
    if input_path is not None:
        artifact_paths["input"] = str(input_path)
    if preprocessed_path is not None:
        artifact_paths["preprocessed"] = str(preprocessed_path)
    if artery_path is not None:
        artifact_paths["artery_mask"] = str(artery_path)
    if vein_path is not None:
        artifact_paths["vein_mask"] = str(vein_path)
    if vessel_path is not None:
        artifact_paths["vessel_mask"] = str(vessel_path)
    return artifact_paths


def convert_paths_dict_to_base64(paths: Dict[str, str]) -> Dict[str, str]:
    images: Dict[str, str] = {}
    for key, file_path_str in paths.items():

        file_path = Path(file_path_str)

        if not file_path.exists():
            raise FileNotFoundError(f'No se encontró la imagen en la ruta: {file_path_str}')

        with open(file_path, 'rb') as image_file:
            encoded_bytes = base64.b64encode(image_file.read())
            b64_string = encoded_bytes.decode('utf-8')

            images[f'{key}_b64'] = b64_string

    return images
