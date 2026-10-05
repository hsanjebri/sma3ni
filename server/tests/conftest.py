from __future__ import annotations

import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app
from app.services.asr import RawSegment

TONE = ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
# Synthetic clips only: the repo never holds real voices (AGENTS.md).
CLIPS = {
    "voice_note.opus": [*TONE, "-c:a", "libopus", "-f", "ogg"],  # what WhatsApp shares
    "note.m4a": [*TONE, "-c:a", "aac"],
    "note.aac": [*TONE, "-c:a", "aac", "-f", "adts"],
    "note.mp3": [*TONE, "-c:a", "libmp3lame"],
    "note.wav": TONE,
    "note.flac": [*TONE, "-c:a", "flac"],  # real audio, but not a format API.md accepts
    "silent.mp4": ["-f", "lavfi", "-i", "color=c=black:s=16x16:d=1", "-c:v", "mpeg4"],
    # Tags a phone might add: they must never leave the server.
    "tagged.m4a": [*TONE, "-c:a", "aac", "-metadata", "title=SECRET-TITLE-TAG"],
}


class FakeTranscriber:
    """Stands in for Whisper: returns fixed raw segments, records each call."""

    needs_pcm = True

    def __init__(self) -> None:
        # Raw model output: tashkeel, a tatweel and an uppercase French word,
        # which the server must normalize (TRANSCRIPTION_GUIDELINES.md).
        self.segments = [
            RawSegment(0.0, 1.2, " عَسلامة، توا نوصل"),
            RawSegment(1.2, 2.0, " للـ RÉUNION"),
            RawSegment(2.0, 2.0, "  "),
        ]
        self.calls: list[Path] = []
        self.error: Exception | None = None

    def transcribe(self, audio: Path) -> list[RawSegment]:
        assert audio.is_file(), "the audio must still exist while the model runs"
        self.calls.append(audio)
        if self.error is not None:
            raise self.error
        return self.segments

    def close(self) -> None:
        pass


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # `_env_file=None`: a developer's server/.env must not leak into the tests.
    return Settings(
        _env_file=None,
        model_version="test-model",
        audio_tmp_dir=tmp_path / "audio-tmp",
        token_secret="test-secret-test-secret-test-secret-",
    )


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def app(settings: Settings, transcriber: FakeTranscriber) -> FastAPI:
    # The ASGI test transport skips the lifespan, so no real model is loaded.
    app = create_app(settings)
    app.state.transcriber = transcriber
    return app


@pytest.fixture
async def anon_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """No token: for the endpoints that need none, and for auth failures."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An installed app: every request carries a valid token."""
    token = app.state.token_signer.issue()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest.fixture(scope="session")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("ffmpeg/ffprobe not on PATH: see 'System dependencies' in server/AGENTS.md")
    out = tmp_path_factory.mktemp("clips")
    for name, args in CLIPS.items():
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", *args, str(out / name)],
            check=True,
            capture_output=True,
        )
    return {name: out / name for name in CLIPS}


def assert_nothing_left(settings: Settings) -> None:
    """No request dir, so no audio, remains in AUDIO_TMP_DIR."""
    leftovers = list(settings.audio_tmp_dir.iterdir()) if settings.audio_tmp_dir.exists() else []
    assert leftovers == []
