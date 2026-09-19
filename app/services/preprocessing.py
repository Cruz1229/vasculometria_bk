from pathlib import Path
from PIL import Image
from app.config import IMAGE_SIZE, PREPROCESSED_DIR
from app.infrastructure.storage import save_image


def preprocess_image(image: Image.Image, output_name: str) -> Path:
    img_resized = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    out_path = PREPROCESSED_DIR / output_name
    save_image(img_resized, out_path)
    return out_path
