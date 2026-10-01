"""Sma3ni ML: data, benchmarking, fine-tuning and export for Tunisian Darija ASR.

Read `ml/AGENTS.md` first. The two rules that bite hardest: every metric goes
through `metrics.py` after `text.normalize_for_scoring()`, and the frozen test
set is never trained on and never edited.
"""

from sma3ni_ml.text import arabizi, lint, normalize, normalize_for_scoring

__all__ = ["arabizi", "lint", "normalize", "normalize_for_scoring"]
__version__ = "0.1.0"
