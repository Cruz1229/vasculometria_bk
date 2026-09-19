from __future__ import annotations
import os
from pathlib import Path


def _env_flag(env_name: str, default: bool) -> bool:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOCAL_MODELS_DIR = PROJECT_DIR / "models"
LEGACY_MODELS_DIR = PROJECT_DIR / "app" / "models"


def _is_container_path(path: Path) -> bool:
    posix = path.as_posix()
    return posix == "/app" or posix.startswith("/app/")


def _resolve_path(env_name: str, *candidates: Path) -> Path:
    raw = os.getenv(env_name)
    if raw:
        configured = Path(raw).expanduser()
        if not configured.is_absolute():
            configured = PROJECT_DIR / configured
        return configured.resolve(strict=False)

    fallback = None
    for candidate in candidates:
        if os.name == "nt" and _is_container_path(candidate):
            continue
        fallback = candidate
        if candidate.exists():
            return candidate.resolve(strict=False)
    if fallback is None:
        fallback = candidates[-1]
    return fallback.resolve(strict=False)


def _parse_list_env(env_name: str, default: str) -> list[str]:
    raw = os.getenv(env_name, default)
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return values or [default]


BASE_DIR = _resolve_path("RETINAL_API_BASE_DIR", Path("/app/runtime"), PROJECT_DIR / "runtime")
LUNET_DIR = _resolve_path("LUNET_DIR", Path("/app/models/LUNet"), LOCAL_MODELS_DIR / "LUNet", LEGACY_MODELS_DIR / "LUNet")
PVBM_DIR = _resolve_path("PVBM_DIR", Path("/app/models/PVBM"), LOCAL_MODELS_DIR / "PVBM", LEGACY_MODELS_DIR / "PVBM")
WEIGHTS_PATH = _resolve_path("LUNET_WEIGHTS", LUNET_DIR / "lunet_modelbest.h5")
IMAGE_SIZE = int(os.getenv("IMAGE_SIZE", "1024"))
THRESHOLD = float(os.getenv("THRESHOLD", "0.5"))
LUNET_TF_DEVICE = os.getenv("LUNET_TF_DEVICE", "/CPU:0").strip() or "/CPU:0"
MAX_ROI_SIZE = int(os.getenv("MAX_ROI_SIZE", "350"))
OD_DIAMETER_UM = float(os.getenv("OD_DIAMETER_UM", "1800.0"))
PLOT_CRE = os.getenv("PLOT_CRE", "false").lower() == "true"
CORS_ALLOW_ORIGINS = _parse_list_env("RETINAL_API_CORS_ALLOW_ORIGINS", "*")
CORS_ALLOW_ORIGIN_REGEX = os.getenv("RETINAL_API_CORS_ALLOW_ORIGIN_REGEX")
CORS_ALLOW_CREDENTIALS = os.getenv("RETINAL_API_CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

INPUT_DIR = BASE_DIR / "input"
PREPROCESSED_DIR = BASE_DIR / "preprocessed"
ARTERY_DIR = BASE_DIR / "artery"
VEIN_DIR = BASE_DIR / "veins"
VESSEL_DIR = BASE_DIR / "vessels"
VIS_DIR = BASE_DIR / "visualizations"
RESULTS_DIR = BASE_DIR / "results"

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
