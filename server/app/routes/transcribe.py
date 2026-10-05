"""`POST /v1/transcribe` (docs/API.md)."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.schemas import Script, Segment, TranscribeResponse, TranslateTarget
from app.security import TokenId, daily_quota
from app.services import text
from app.services.asr import Transcriber
from app.services.audio import prepared_audio

logger = logging.getLogger(__name__)
router = APIRouter()

LANGUAGE = "aeb"  # ISO 639-3: Tunisian Arabic


@router.post("/transcribe")
async def transcribe(
    request: Request,
    token_id: TokenId,
    audio: UploadFile,
    script: Annotated[Script, Form()] = Script.ARABIC,
    # Accepted now so the contract is stable; answered by the LLM step (ROADMAP
    # Phase 3). Until then `summary`, `translation` and `replies` stay null.
    summary: Annotated[bool, Form()] = False,
    translate: Annotated[TranslateTarget | None, Form()] = None,
    replies: Annotated[bool, Form()] = False,
) -> TranscribeResponse:
    settings: Settings = request.app.state.settings
    transcriber: Transcriber = request.app.state.transcriber
    request_id = f"req_{secrets.token_hex(8)}"
    started = time.perf_counter()

    def run() -> tuple[float, list[Segment]]:
        with prepared_audio(audio.file, settings, pcm=transcriber.needs_pcm) as decoded:
            raw = transcriber.transcribe(decoded.path)
        rendered = (
            Segment(start=round(s.start, 2), end=round(s.end, 2), text=text.render(s.text, script))
            for s in raw
        )
        return decoded.duration_s, [segment for segment in rendered if segment.text]

    # Quota first: an over-limit caller is answered at once instead of queueing.
    async with daily_quota(request, token_id), request.app.state.asr_slots:
        duration_s, segments = await run_in_threadpool(run)

    processing_ms = round((time.perf_counter() - started) * 1000)
    # Metadata only, never the text (docs/PRIVACY.md).
    logger.info(
        "transcribed %s duration_s=%.1f processing_ms=%d model=%s",
        request_id,
        duration_s,
        processing_ms,
        settings.model_version,
    )
    return TranscribeResponse(
        request_id=request_id,
        text=" ".join(segment.text for segment in segments),
        script=script,
        language=LANGUAGE,
        duration_s=round(duration_s, 2),
        segments=segments,
        model_version=settings.model_version,
        processing_ms=processing_ms,
    )
