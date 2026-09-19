from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
from app.config import _env_flag, LUNET_DIR, PVBM_DIR, WEIGHTS_PATH, IMAGE_SIZE, LUNET_TF_DEVICE
from app.infrastructure.logging import LOGGER


@dataclass
class ModelBundle:
    model: Any = None
    segmenter: Any = None
    geometricalVBMs: Any = None
    creVBMs: Any = None


def _configure_tensorflow_runtime() -> None:
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    if _env_flag("TF_GPU_MEMORY_GROWTH", True):
        for gpu in gpus:
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
            except RuntimeError as exc:
                LOGGER.warning("tensorflow: no se pudo activar memory_growth en %s: %s", gpu.name, exc)

    LOGGER.info("tensorflow: version=%s gpus=%s", tf.__version__, [gpu.name for gpu in gpus])
    if gpus and _env_flag("TF_GPU_RUNTIME_PROBE", True):
        try:
            with tf.device("/GPU:0"):
                probe = tf.math.rsqrt(tf.constant([4.0], dtype=tf.float32)).numpy()[0]
            LOGGER.info("tensorflow: GPU Rsqrt probe=%.3f", float(probe))
        except Exception as exc:
            raise RuntimeError(
                "TensorFlow no puede compilar/ejecutar Rsqrt en la GPU; "
                "verifica NVRTC, libdevice y las bibliotecas CUDA del contenedor"
            ) from exc


def _prepare_imports() -> None:
    import sys
    if str(LUNET_DIR.parent) not in sys.path:
        sys.path.insert(0, str(LUNET_DIR.parent))
    if str(LUNET_DIR) not in sys.path:
        sys.path.insert(0, str(LUNET_DIR))
    if str(PVBM_DIR.parent) not in sys.path:
        sys.path.insert(0, str(PVBM_DIR.parent))


def load_models() -> ModelBundle:
    os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
    import tensorflow as tf
    from tensorflow.keras import layers

    _configure_tensorflow_runtime()
    _prepare_imports()
    os.environ["TF_USE_LEGACY_KERAS"] = "1"

    from PVBM.DiscSegmenter import DiscSegmenter
    from PVBM.GeometryAnalysis import GeometricalVBMs
    from PVBM.CentralRetinalAnalysis import CREVBMs
    from LUNet.src.lunet.model import build_lunet

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"No se encontraron los pesos: {WEIGHTS_PATH}")

    LOGGER.info(
        "startup: loading LUNet image_size=%s tf_device=%s",
        IMAGE_SIZE,
        LUNET_TF_DEVICE,
    )
    with tf.device(LUNET_TF_DEVICE):
        inputs = layers.Input(shape=(IMAGE_SIZE, IMAGE_SIZE, 3), name="input_fundus")
        model, _attn, _btlnk = build_lunet(
            inputs,
            init_n_filters=18,
            kernel_size=7,
            transpose_stride=2,
            stride=1,
            keep_prob=1.0,
            block_size=7,
            with_batch_normalization=True,
            scale=True,
            dropblock=False,
            n_layer_output=2,
        )
        model.load_weights(str(WEIGHTS_PATH))

    return ModelBundle(
        model=model,
        segmenter=DiscSegmenter(),
        geometricalVBMs=GeometricalVBMs(),
        creVBMs=CREVBMs(),
    )
