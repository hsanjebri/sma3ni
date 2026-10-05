"""Speech recognition with faster-whisper, decoded exactly like the benchmark.

Same language, task and beam size as `sma3ni_ml.benchmark.FasterWhisperBackend`,
so the numbers in `ml/RESULTS.md` describe what users get. Change both together.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.config import Settings

# The benchmark backend's defaults (ml/configs/benchmark.yaml): forced Arabic.
DECODE_OPTIONS = {"language": "ar", "task": "transcribe", "beam_size": 5}


@dataclass(frozen=True)
class RawSegment:
    start: float
    end: float
    text: str  # as the model wrote it, before normalization


class Transcriber(Protocol):
    def transcribe(self, wav: Path) -> list[RawSegment]: ...


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


def samples(wav: Path) -> np.ndarray:
    """The float32 samples of a 16 kHz mono 16-bit WAV from `services.audio`.

    ffmpeg already decoded the upload, so Whisper gets samples, not a path: a
    path would be decoded a second time by PyAV, and PyAV 19 dropped an
    argument faster-whisper 1.2 still passes to it.
    """
    with wave.open(str(wav)) as source:
        frames = source.readframes(source.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
