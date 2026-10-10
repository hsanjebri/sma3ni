from __future__ import annotations

import io
import os
from collections.abc import Callable
from pathlib import Path

import httpx
import numpy as np
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode
from app.services.asr import GROQ_URL, GroqTranscriber, RawSegment, samples
from app.services.audio import SAMPLE_RATE, prepared_audio

GROQ_REPLY = {
    "task": "transcribe",
    "language": "Arabic",
    "duration": 2.0,
    "text": " عسلامة توا نوصل",
    "segments": [
        {"id": 0, "start": 0.0, "end": 1.1, "text": " عسلامة", "no_speech_prob": 0.01},
        {"id": 1, "start": 1.1, "end": 2.0, "text": " توا نوصل", "no_speech_prob": 0.02},
    ],
}


def test_samples_are_what_whisper_expects(settings: Settings, clips: dict[str, Path]) -> None:
    with prepared_audio(io.BytesIO(clips["voice_note.opus"].read_bytes()), settings) as audio:
        decoded = samples(audio.path)

    assert decoded.dtype == np.float32
    assert decoded.ndim == 1
    assert len(decoded) / SAMPLE_RATE == pytest.approx(2.0, abs=0.1)
    assert 0.1 < np.abs(decoded).max() <= 1.0  # a real signal, scaled to [-1, 1]


def with_groq(settings: Settings, key: str) -> Settings:
    return settings.model_copy(update={"asr_backend": "groq", "groq_api_key": SecretStr(key)})


@pytest.fixture
def groq_settings(settings: Settings) -> Settings:
    return with_groq(settings, "gsk_test")


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    path = tmp_path / "audio.wav"
    path.write_bytes(b"RIFF....WAVEfmt fake-audio-bytes")
    return path


def groq(settings: Settings, handler: Callable[[httpx.Request], httpx.Response]) -> GroqTranscriber:
    return GroqTranscriber(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_groq_request_and_segments(groq_settings: Settings, wav: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=GROQ_REPLY)

    segments = groq(groq_settings, handler).transcribe(wav)

    assert segments == [RawSegment(0.0, 1.1, " عسلامة"), RawSegment(1.1, 2.0, " توا نوصل")]
    [request] = seen
    assert str(request.url) == GROQ_URL
    assert request.headers["authorization"] == "Bearer gsk_test"
    body = request.read()
    for part in (
        b'name="model"\r\n\r\nwhisper-large-v3-turbo',
        b'name="language"\r\n\r\nar',
        b'name="response_format"\r\n\r\nverbose_json',
        b'filename="audio.wav"',
        b"fake-audio-bytes",
    ):
        assert part in body, part


def test_groq_gets_the_format_from_the_file_name(groq_settings: Settings, tmp_path: Path) -> None:
    note = tmp_path / "audio.ogg"
    note.write_bytes(b"OggS fake-opus")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=GROQ_REPLY)

    groq(groq_settings, handler).transcribe(note)

    body = seen[0].read()
    assert b'filename="audio.ogg"' in body
    assert b"Content-Type: audio/ogg" in body


@pytest.mark.parametrize(
    ("status", "headers", "retry_after"),
    [(429, {"retry-after": "7"}, "7"), (503, {}, None), (500, {}, None)],
    ids=["rate-limited", "unavailable", "server-error"],
)
def test_groq_capacity_problems_are_busy(
    groq_settings: Settings,
    wav: Path,
    status: int,
    headers: dict[str, str],
    retry_after: str | None,
) -> None:
    transcriber = groq(groq_settings, lambda _: httpx.Response(status, headers=headers))

    with pytest.raises(ApiError) as caught:
        transcriber.transcribe(wav)

    assert caught.value.code is ErrorCode.BUSY
    assert (caught.value.headers or {}).get("Retry-After") == retry_after


def test_groq_timeout_is_busy(groq_settings: Settings, wav: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ApiError) as caught:
        groq(groq_settings, handler).transcribe(wav)

    assert caught.value.code is ErrorCode.BUSY


def test_groq_rejecting_our_key_is_our_bug(groq_settings: Settings, wav: Path) -> None:
    # Not `busy`: retrying cannot fix a wrong GROQ_API_KEY, so it is a 500.
    transcriber = groq(groq_settings, lambda _: httpx.Response(401, json={"error": {}}))

    with pytest.raises(httpx.HTTPStatusError):
        transcriber.transcribe(wav)


@pytest.mark.slow
@pytest.mark.parametrize(
    "name", ["voice_note.opus", "note.m4a", "note.aac", "note.mp3", "note.wav"]
)
def test_real_groq_accepts_every_remux(
    settings: Settings, clips: dict[str, Path], name: str
) -> None:
    """Calls Groq for real, as production does. Needs GROQ_API_KEY: `pytest -m slow`."""
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set")
    real = with_groq(settings, os.environ["GROQ_API_KEY"])
    transcriber = GroqTranscriber(real)
    with prepared_audio(
        io.BytesIO(clips[name].read_bytes()), real, pcm=transcriber.needs_pcm
    ) as audio:
        segments = transcriber.transcribe(audio.path)

    assert isinstance(segments, list)  # a tone has no words to get right
