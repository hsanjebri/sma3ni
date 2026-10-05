"""Speech recognition: Whisper here (`local`) or on Groq's API (`groq`), per ASR_BACKEND.

The local backend decodes exactly like `sma3ni_ml.benchmark.FasterWhisperBackend`
(same language, task and beam size), so the numbers in `ml/RESULTS.md` describe
what users get; change both together. Groq takes no beam size, so what it
serves has to be benchmarked on its own (ROADMAP Phase 1).
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode

# The benchmark backend's defaults (ml/configs/benchmark.yaml): forced Arabic.
DECODE_OPTIONS = {"language": "ar", "task": "transcribe", "beam_size": 5}

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


@dataclass(frozen=True)
class RawSegment:
    start: float
    end: float
    text: str  # as the model wrote it, before normalization


class Transcriber(Protocol):
    def transcribe(self, wav: Path) -> list[RawSegment]: ...

    def close(self) -> None: ...


def build_transcriber(settings: Settings) -> Transcriber:
    """The backend ASR_BACKEND names. Blocking (may load or download a model)."""
    if settings.asr_backend == "groq":
        return GroqTranscriber(settings)
    return WhisperTranscriber(settings)


class WhisperTranscriber:
    """Loads the model once. `transcribe` blocks: call it from a worker thread."""

    def __init__(self, settings: Settings) -> None:
        from faster_whisper import WhisperModel  # lazy: unit tests never load a model

        self._model = WhisperModel(
            settings.model_path, device=settings.device, compute_type=settings.compute_type
        )

    def transcribe(self, wav: Path) -> list[RawSegment]:
        segments, _info = self._model.transcribe(samples(wav), **DECODE_OPTIONS)
        # `segments` is lazy and decoding happens while iterating, so finish it
        # here, while the caller still holds the WAV.
        return [RawSegment(segment.start, segment.end, segment.text) for segment in segments]

    def close(self) -> None:
        pass


class GroqTranscriber:
    """Whisper on Groq: no GPU here, and the audio is sent to Groq (docs/PRIVACY.md).

    `transcribe` blocks: call it from a worker thread. Groq being rate limited,
    down or slow becomes `503 busy` (the client retries); anything else, like a
    bad API key, is our fault and becomes `500 internal_error`.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if settings.groq_api_key is None:
            raise ValueError("GroqTranscriber needs GROQ_API_KEY")
        self._model = settings.groq_model
        self._client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self._headers = {"Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}"}

    def transcribe(self, wav: Path) -> list[RawSegment]:
        try:
            with wav.open("rb") as audio:
                response = self._client.post(
                    GROQ_URL,
                    headers=self._headers,
                    files={"file": ("audio.wav", audio, "audio/wav")},
                    data={
                        "model": self._model,
                        "language": DECODE_OPTIONS["language"],
                        "response_format": "verbose_json",
                    },
                )
        except httpx.TimeoutException:
            raise _busy() from None
        if response.status_code == 429 or response.status_code >= 500:
            raise _busy(response.headers.get("retry-after"))
        response.raise_for_status()
        return [
            RawSegment(segment["start"], segment["end"], segment["text"])
            for segment in response.json().get("segments", [])
        ]

    def close(self) -> None:
        self._client.close()


def _busy(retry_after: str | None = None) -> ApiError:
    headers = {"Retry-After": retry_after} if retry_after else None
    return ApiError(ErrorCode.BUSY, "Transcription is busy, try again shortly.", headers)


def samples(wav: Path) -> np.ndarray:
    """The float32 samples of a 16 kHz mono 16-bit WAV from `services.audio`.

    ffmpeg already decoded the upload, so Whisper gets samples, not a path: a
    path would be decoded a second time by PyAV, and PyAV 19 dropped an
    argument faster-whisper 1.2 still passes to it.
    """
    with wave.open(str(wav)) as source:
        frames = source.readframes(source.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
