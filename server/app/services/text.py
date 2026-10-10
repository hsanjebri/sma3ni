"""Transcript text for API output. The one implementation is `sma3ni_ml.text`.

Never re-implement a rule here: `docs/TRANSCRIPTION_GUIDELINES.md`, the
training targets and the metrics all go through `sma3ni_ml.text` too.
"""

from __future__ import annotations

from sma3ni_ml.text import arabizi, normalize

from app.schemas import Script


def render(text: str, script: Script) -> str:
    """Canonical written form (guidelines section 1-3), in the script asked for."""
    return arabizi(text) if script is Script.ARABIZI else normalize(text)
