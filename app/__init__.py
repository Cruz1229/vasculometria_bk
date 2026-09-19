"""Retinal API. Keep the legacy ``uvicorn app:app`` entry point available."""

def __getattr__(name):
    if name == "app":
        from app.main import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
