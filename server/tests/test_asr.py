from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings
from app.services.asr import samples
from app.services.audio import SAMPLE_RATE, prepared_audio


def test_samples_are_what_whisper_expects(settings: Settings, clips: dict[str, Path]) -> None:
    with prepared_audio(io.BytesIO(clips["voice_note.opus"].read_bytes()), settings) as audio:
        decoded = samples(audio.path)

    assert decoded.dtype == np.float32
    assert decoded.ndim == 1
    assert len(decoded) / SAMPLE_RATE == pytest.approx(2.0, abs=0.1)
    assert 0.1 < np.abs(decoded).max() <= 1.0  # a real signal, scaled to [-1, 1]
