import logging
import os
import time


LOG_LEVEL_NAME = os.getenv("RETINAL_API_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
LOGGER = logging.getLogger("uvicorn.error").getChild("retinal_api")
if not logging.getLogger().handlers and not logging.getLogger("uvicorn.error").handlers:
    logging.basicConfig(level=LOG_LEVEL)
LOGGER.setLevel(LOG_LEVEL)

def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
