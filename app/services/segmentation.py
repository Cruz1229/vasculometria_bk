from __future__ import annotations
from pathlib import Path
from typing import Tuple
import numpy as np
from PIL import Image
from app.config import IMAGE_SIZE, LUNET_TF_DEVICE, THRESHOLD, ARTERY_DIR, VEIN_DIR, VESSEL_DIR
from app.infrastructure.storage import save_image


def segment_image(model, image: Image.Image, output_name: str) -> Tuple[Path, Path, Path]:
    import tensorflow as tf

    if model is None:
        raise RuntimeError("El modelo de segmentación no está cargado")

    img_resized = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    x = np.expand_dims(np.array(img_resized, dtype=np.float32) / 255.0, axis=0)

    with tf.device(LUNET_TF_DEVICE):
        prob = tf.sigmoid(model(x, training=False)).numpy()[0]
    n_ch = prob.shape[-1]

    artery = (prob[..., 0] > THRESHOLD).astype(np.uint8) * 255
    vein = (prob[..., 1] > THRESHOLD).astype(np.uint8) * 255 if n_ch >= 2 else np.zeros_like(artery)
    if n_ch >= 3:
        vessel = (prob[..., 2] > THRESHOLD).astype(np.uint8) * 255
    else:
        vessel = ((artery > 0) | (vein > 0)).astype(np.uint8) * 255

    artery_path = ARTERY_DIR / output_name
    vein_path = VEIN_DIR / output_name
    vessel_path = VESSEL_DIR / output_name

    save_image(Image.fromarray(artery), artery_path)
    save_image(Image.fromarray(vein), vein_path)
    save_image(Image.fromarray(vessel), vessel_path)

    return artery_path, vein_path, vessel_path
