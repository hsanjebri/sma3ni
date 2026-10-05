"""App factory. Run with `uv run uvicorn app.main:app --reload` from `server/`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.errors import install_error_handling
from app.routes import health
from app.services import audio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    # docs/PRIVACY.md: a process that crashed mid-request can leave audio behind.
    removed = audio.clear_leftovers(settings.audio_tmp_dir)
    if removed:
        logger.warning("removed %d leftover audio temp dirs", removed)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Sma3ni API", version="1", lifespan=lifespan)
    app.state.settings = settings or Settings()
    install_error_handling(app)
    app.include_router(health.router, prefix="/v1")
    return app


app = create_app()
