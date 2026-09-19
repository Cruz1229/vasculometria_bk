from __future__ import annotations

import argparse
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
MODEL_URL = "https://drive.google.com/uc?id=116EEFBn7qr_LpCBb8GBuyzpa_KGp4xPX"


def download_disc_model(output: Path) -> Path:
    if output.is_file() and output.stat().st_size > 0:
        return output

    import gdown

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    result = gdown.download(MODEL_URL, str(temporary), quiet=False)
    if result is None or not temporary.is_file() or temporary.stat().st_size == 0:
        raise RuntimeError("No se pudo descargar el modelo de disco óptico de PVBM")
    temporary.replace(output)
    return output


def main() -> None:
    pvbm_dir = Path(os.getenv("PVBM_DIR", "models/PVBM")).expanduser()
    if not pvbm_dir.is_absolute():
        pvbm_dir = PROJECT_DIR / pvbm_dir
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=pvbm_dir / "lunetv2_odc.onnx")
    args = parser.parse_args()
    output = args.output.expanduser()
    if not output.is_absolute():
        output = PROJECT_DIR / output
    print(download_disc_model(output))


if __name__ == "__main__":
    main()
