from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from pathlib import Path

import httpx
import pytest
from conftest import FakeTranscriber, assert_nothing_left
from fastapi import FastAPI
from sma3ni_ml.text import arabizi

from app.config import Settings
from app.main import create_app
from app.services.asr import RawSegment, WhisperTranscriber

pytestmark = pytest.mark.anyio


def voice_note(clips: dict[str, Path]) -> dict[str, tuple[str, bytes, str]]:
    # WhatsApp shares its notes as .opus with this content type.
    return {"audio": ("PTT-20261005.opus", clips["voice_note.opus"].read_bytes(), "audio/ogg")}


async def test_returns_the_normalized_transcript(
    client: httpx.AsyncClient,
    clips: dict[str, Path],
    settings: Settings,
    transcriber: FakeTranscriber,
) -> None:
    response = await client.post("/v1/transcribe", files=voice_note(clips))

    assert response.status_code == 200
    body = response.json()
    assert re.fullmatch(r"req_[0-9a-f]{16}", body.pop("request_id"))
    assert isinstance(body.pop("processing_ms"), int)
    assert body.pop("duration_s") == pytest.approx(2.0, abs=0.1)
    # No tashkeel, no tatweel, lowercase French; the blank segment is dropped.
    assert body == {
        "text": "عسلامة، توا نوصل لل réunion",
        "script": "arabic",
        "language": "aeb",
        "segments": [
            {"start": 0.0, "end": 1.2, "text": "عسلامة، توا نوصل"},
            {"start": 1.2, "end": 2.0, "text": "لل réunion"},
        ],
        "summary": None,
        "translation": None,
        "replies": None,
        "model_version": "test-model",
    }
    [wav] = transcriber.calls
    assert wav.name == "audio.wav"
    assert wav.parent.parent == settings.audio_tmp_dir
    assert_nothing_left(settings)


async def test_arabizi_goes_through_the_shared_implementation(
    client: httpx.AsyncClient, clips: dict[str, Path]
) -> None:
    response = await client.post(
        "/v1/transcribe", files=voice_note(clips), data={"script": "arabizi"}
    )

    body = response.json()
    assert body["script"] == "arabizi"
    assert body["text"] == arabizi("عَسلامة، توا نوصل للـ RÉUNION")
    assert body["text"].startswith("3aslema")


async def test_model_failure_answers_500_and_leaves_no_audio(
    client: httpx.AsyncClient,
    clips: dict[str, Path],
    settings: Settings,
    transcriber: FakeTranscriber,
) -> None:
    transcriber.error = RuntimeError("CUDA out of memory")

    response = await client.post("/v1/transcribe", files=voice_note(clips))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert_nothing_left(settings)


async def test_bad_audio_is_rejected_before_the_model(
    client: httpx.AsyncClient, settings: Settings, transcriber: FakeTranscriber
) -> None:
    files = {"audio": ("note.opus", b"this is not audio\n" * 200, "audio/ogg")}

    response = await client.post("/v1/transcribe", files=files)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_audio"
    assert transcriber.calls == []
    assert_nothing_left(settings)


@pytest.mark.parametrize(
    ("data", "with_audio", "field"),
    [({"script": "cyrillic"}, True, "script"), ({}, False, "audio")],
    ids=["unknown-script", "missing-audio"],
)
async def test_invalid_fields_use_the_error_envelope(
    client: httpx.AsyncClient,
    clips: dict[str, Path],
    data: dict[str, str],
    with_audio: bool,
    field: str,
) -> None:
    files = voice_note(clips) if with_audio else None

    response = await client.post("/v1/transcribe", files=files, data=data)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert field in error["message"]
    assert "cyrillic" not in response.text  # submitted values are never echoed


async def test_logs_carry_metadata_but_never_the_text(
    client: httpx.AsyncClient, clips: dict[str, Path], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = await client.post("/v1/transcribe", files=voice_note(clips))

    assert response.json()["request_id"] in caplog.text
    for word in ("عسلامة", "توا", "réunion", "RÉUNION"):
        assert word not in caplog.text


async def test_transcriptions_beyond_asr_concurrency_queue(
    app: FastAPI, client: httpx.AsyncClient, clips: dict[str, Path], settings: Settings
) -> None:
    assert settings.asr_concurrency == 1
    lock = threading.Lock()
    running = peak = 0

    class SlowTranscriber(FakeTranscriber):
        def transcribe(self, wav: Path) -> list[RawSegment]:
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.2)
            with lock:
                running -= 1
            return super().transcribe(wav)

    app.state.transcriber = SlowTranscriber()

    responses = await asyncio.gather(
        *(client.post("/v1/transcribe", files=voice_note(clips)) for _ in range(3))
    )

    assert [r.status_code for r in responses] == [200, 200, 200]
    assert peak == 1


@pytest.mark.slow
async def test_real_whisper_end_to_end(settings: Settings, clips: dict[str, Path]) -> None:
    """Loads Whisper `tiny` on CPU (downloads it once). Run with `pytest -m slow`."""
    settings.model_path = "tiny"
    app = create_app(settings)
    app.state.transcriber = WhisperTranscriber(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/transcribe", files=voice_note(clips))

    assert response.status_code == 200
    assert isinstance(response.json()["text"], str)  # a tone has no words to get right
    assert_nothing_left(settings)
