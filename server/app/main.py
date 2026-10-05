"""App factory. Run with `uv run uvicorn app.main:app --reload` from `server/`."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import install_error_handling
from app.routes import health, install, transcribe
from app.security import MemoryUsageStore, TokenSigner
from app.services import audio
from app.services.asr import WhisperTranscriber

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Show `app.*` logs (metadata only) next to uvicorn's, which only sets up its own."""
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings: Settings = app.state.settings
    if settings.token_secret is None:
        logger.warning("TOKEN_SECRET unset: random signing key, tokens die on restart (dev only)")
    # docs/PRIVACY.md: a process that crashed mid-request can leave audio behind.
    removed = audio.clear_leftovers(settings.audio_tmp_dir)
    if removed:
        logger.warning("removed %d leftover audio temp dirs", removed)
    # Once per process. The first run downloads the model if MODEL_PATH is a name.
    app.state.transcriber = await run_in_threadpool(WhisperTranscriber, settings)
    logger.info(
        "model %s loaded (%s, %s on %s)",
        settings.model_version,
        settings.model_path,
        settings.compute_type,
        settings.device,
    )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Sma3ni API", version="1", lifespan=lifespan)
    app.state.settings = settings = settings or Settings()
    app.state.asr_slots = asyncio.Semaphore(settings.asr_concurrency)
    secret = settings.token_secret
    app.state.token_signer = TokenSigner(
        secret.get_secret_value().encode() if secret else secrets.token_bytes(32)
    )
    app.state.usage = MemoryUsageStore()
    install_error_handling(app)
    app.include_router(health.router, prefix="/v1")
    app.include_router(install.router, prefix="/v1")
    app.include_router(transcribe.router, prefix="/v1")
    return app


app = create_app()
