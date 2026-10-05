"""App factory. Run with `uv run uvicorn app.main:app --reload` from `server/`."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings
from app.errors import install_error_handling
from app.routes import health


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Sma3ni API", version="1")
    app.state.settings = settings or Settings()
    install_error_handling(app)
    app.include_router(health.router, prefix="/v1")
    return app


app = create_app()
