"""Run one or more ASR models over a manifest and report WER / CER / CS-F1.

    uv run python -m sma3ni_ml.benchmark --config configs/benchmark.yaml

One command, one config file, reproducible: the config names the manifest and
its frozen hash, the models and the slices. The run writes a JSON report per
model and prints the `RESULTS.md` row to paste (see `ml/AGENTS.md`).

Model backends are imported lazily, so scoring a predictions file needs neither
a GPU nor torch installed.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, Field

from sma3ni_ml import data as data_module
from sma3ni_ml import metrics as metrics_module
from sma3ni_ml.data import ManifestEntry
from sma3ni_ml.text import normalize_for_scoring


class ModelSpec(BaseModel):
    """One model to benchmark."""

    model_config = {"extra": "forbid"}

    name: str
    """Label used in reports and in `RESULTS.md`."""

    backend: str
    """`faster_whisper`, `transformers` or `predictions`."""

    model: str = ""
    """Model id or path, as the backend understands it."""

    options: dict[str, Any] = Field(default_factory=dict)
    """Backend-specific knobs (device, compute_type, beam_size, predictions...)."""


class BenchmarkConfig(BaseModel):
    """Contents of `configs/benchmark.yaml`."""

    model_config = {"extra": "forbid"}

    manifest: str
    manifest_sha256: str | None = None
    """Set once the test set is frozen; the run aborts if the data changed."""

    split: data_module.Split | None = "test"
    audio_root: str = "."
    """Prefix for relative `audio` paths in the manifest."""

    limit: int | None = None
    seed: int = 1337
    output_dir: str = "reports"
    slices: list[str] = Field(default_factory=lambda: ["region", "gender", "duration_bucket"])
    min_slice_utterances: int = 10
    models: list[ModelSpec]


class Backend(Protocol):
    """Anything that turns an audio file into text."""

    def transcribe(self, audio_path: Path) -> str: ...


class FasterWhisperBackend:
    """faster-whisper / CTranslate2 - the runtime the server uses."""

    def __init__(self, model: str, options: dict[str, Any]) -> None:
        from faster_whisper import WhisperModel  # lazy: needs the `asr` extra

        options = dict(options)
        self._decode = {
            "language": options.pop("language", "ar"),
            "task": options.pop("task", "transcribe"),
            "beam_size": options.pop("beam_size", 5),
            **options.pop("decode", {}),
        }
        self._model = WhisperModel(
            model,
            device=options.pop("device", "auto"),
            compute_type=options.pop("compute_type", "int8"),
            **options,
        )

    def transcribe(self, audio_path: Path) -> str:
        segments, _info = self._model.transcribe(str(audio_path), **self._decode)
        return "".join(segment.text for segment in segments)


class TransformersBackend:
    """Hugging Face pipeline - for checkpoints not exported to CTranslate2 yet."""

    def __init__(self, model: str, options: dict[str, Any]) -> None:
        from transformers import pipeline  # lazy: needs the `asr` extra

        options = dict(options)
        self._generate_kwargs = {
            "language": options.pop("language", "ar"),
            "task": options.pop("task", "transcribe"),
            **options.pop("generate_kwargs", {}),
        }
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            device=options.pop("device", -1),
            chunk_length_s=options.pop("chunk_length_s", 30),
            **options,
        )

    def transcribe(self, audio_path: Path) -> str:
        result = self._pipe(str(audio_path), generate_kwargs=self._generate_kwargs)
        return str(result["text"])


class PredictionsBackend:
    """Replay hypotheses from a jsonl file of `{"id": ..., "text": ...}`.

    For scoring a system we cannot run here (a hosted API, a colleague's model,
    a Kaggle notebook's output) with exactly the same metrics.
    """

    def __init__(self, model: str, options: dict[str, Any]) -> None:
        path = Path(options.get("predictions") or model)
        self._by_id: dict[str, str] = {}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                self._by_id[record["id"]] = record.get("text", "")
        self._current_id: str | None = None

    def set_entry(self, entry: ManifestEntry) -> None:
        self._current_id = entry.id

    def transcribe(self, audio_path: Path) -> str:
        # audio_path is unused: hypotheses are keyed by clip id.
        if self._current_id is None:
            raise RuntimeError("PredictionsBackend needs set_entry() before transcribe()")
        if self._current_id not in self._by_id:
            raise KeyError(f"no prediction for clip {self._current_id}")
        return self._by_id[self._current_id]


BACKENDS: dict[str, type] = {
    "faster_whisper": FasterWhisperBackend,
    "transformers": TransformersBackend,
    "predictions": PredictionsBackend,
}


def build_backend(spec: ModelSpec) -> Backend:
    """Instantiate the backend named by `spec`."""
    try:
        backend_class = BACKENDS[spec.backend]
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise ValueError(f"unknown backend {spec.backend!r}; known: {known}") from None
    return backend_class(spec.model, spec.options)


@dataclass
class ModelResult:
    """Outcome of one model over one manifest."""

    spec: ModelSpec
    metrics: metrics_module.Metrics
    slices: dict[str, metrics_module.Metrics]
    audio_seconds: float
    processing_seconds: float
    hypotheses: dict[str, str]

    @property
    def rtf(self) -> float:
        """Real-time factor: processing time over audio duration."""
        return self.processing_seconds / self.audio_seconds if self.audio_seconds else 0.0

    def results_row(self, commit: str = "", notes: str = "", test_set: str = "test_v1") -> str:
        """The `RESULTS.md` table row for this run."""
        cs = self.metrics.code_switch
        return (
            f"| {date.today().isoformat()} | {self.spec.name} | {test_set} "
            f"| {self.metrics.wer:.3f} | {self.metrics.cer:.3f} | {cs.f1:.3f} "
            f"| {self.rtf:.3f} | {commit} | {notes} |"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.spec.name,
            "backend": self.spec.backend,
            "model_id": self.spec.model,
            "options": self.spec.options,
            "date": date.today().isoformat(),
            "audio_seconds": round(self.audio_seconds, 2),
            "processing_seconds": round(self.processing_seconds, 2),
            "rtf": round(self.rtf, 4),
            "overall": self.metrics.as_dict(),
            "slices": {
                name: slice_metrics.as_dict() for name, slice_metrics in self.slices.items()
            },
        }


def run_model(
    spec: ModelSpec,
    entries: Sequence[ManifestEntry],
    *,
    audio_root: Path,
    slices: Sequence[str] = (),
    min_slice_utterances: int = 1,
) -> ModelResult:
    """Transcribe every entry with one model and score the result."""
    backend = build_backend(spec)
    refs: list[str] = []
    hyps: list[str] = []
    hypotheses: dict[str, str] = {}
    audio_seconds = 0.0
    processing_seconds = 0.0

    for entry in entries:
        audio_path = audio_root / entry.audio
        if hasattr(backend, "set_entry"):
            backend.set_entry(entry)  # type: ignore[attr-defined]
        started = time.perf_counter()
        hypothesis = backend.transcribe(audio_path)
        processing_seconds += time.perf_counter() - started
        audio_seconds += entry.duration
        refs.append(entry.text)
        hyps.append(hypothesis)
        hypotheses[entry.id] = hypothesis

    # Normalize once; metrics and slices reuse the normalized text.
    normalized_refs = [normalize_for_scoring(ref) for ref in refs]
    normalized_hyps = [normalize_for_scoring(hyp) for hyp in hyps]

    overall = metrics_module.evaluate(normalized_refs, normalized_hyps, already_normalized=True)
    slice_metrics: dict[str, metrics_module.Metrics] = {}
    for key in slices:
        labels = [entry.slice_label(key) for entry in entries]
        slice_metrics.update(
            metrics_module.slice_report(
                normalized_refs,
                normalized_hyps,
                labels,
                already_normalized=True,
                min_utterances=min_slice_utterances,
            )
        )

    return ModelResult(
        spec=spec,
        metrics=overall,
        slices=slice_metrics,
        audio_seconds=audio_seconds,
        processing_seconds=processing_seconds,
        hypotheses=hypotheses,
    )


def load_config(path: str | Path) -> BenchmarkConfig:
    """Parse and validate a benchmark YAML config."""
    with Path(path).open(encoding="utf-8") as handle:
        return BenchmarkConfig.model_validate(yaml.safe_load(handle))


def run(config: BenchmarkConfig, *, only: Sequence[str] = ()) -> list[ModelResult]:
    """Run every model in the config (or only the named ones)."""
    config_dir = Path(".")
    entries = data_module.load_manifest(config.manifest, split=config.split)
    if config.manifest_sha256 and config.manifest_sha256 != "TBD":
        data_module.assert_frozen(entries, config.manifest_sha256)
    entries = sorted(entries, key=lambda entry: entry.id)
    if config.limit:
        entries = entries[: config.limit]
    if not entries:
        raise ValueError(f"no clips in {config.manifest} for split {config.split}")

    specs = [spec for spec in config.models if not only or spec.name in only]
    if not specs:
        raise ValueError(f"no model matched {list(only)}")

    summary = data_module.summarize(entries)
    print(f"manifest: {config.manifest} -> {summary.describe()}")

    results: list[ModelResult] = []
    for spec in specs:
        print(f"\n== {spec.name} ({spec.backend})")
        result = run_model(
            spec,
            entries,
            audio_root=config_dir / config.audio_root,
            slices=config.slices,
            min_slice_utterances=config.min_slice_utterances,
        )
        results.append(result)
        print(
            f"   WER {result.metrics.wer:.3f}  CER {result.metrics.cer:.3f}  "
            f"CS-F1 {result.metrics.code_switch.f1:.3f}  RTF {result.rtf:.3f}"
        )
        write_report(result, Path(config.output_dir))
    return results


def write_report(result: ModelResult, output_dir: Path) -> Path:
    """Write the JSON report for one model. Hypotheses go in a sibling file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date.today().isoformat()}_{result.spec.name.replace('/', '_')}"
    report_path = output_dir / f"{stem}.json"
    report_path.write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    hypotheses_path = output_dir / f"{stem}.hyp.jsonl"
    with hypotheses_path.open("w", encoding="utf-8", newline="\n") as handle:
        for clip_id, text in sorted(result.hypotheses.items()):
            handle.write(json.dumps({"id": clip_id, "text": text}, ensure_ascii=False) + "\n")
    print(f"   report: {report_path}")
    return report_path


def print_results_table(results: Sequence[ModelResult], test_set: str, commit: str = "") -> None:
    """Print rows ready to paste into `ml/RESULTS.md` (append-only, by hand)."""
    print("\nPaste into ml/RESULTS.md:")
    print("| date | model | test set | WER | CER | CS-F1 | RTF | commit | notes |")
    print("|---|---|---|---|---|---|---|---|---|")
    for result in sorted(results, key=lambda item: item.metrics.wer):
        print(result.results_row(commit=commit, test_set=test_set))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="YAML config, e.g. configs/benchmark.yaml")
    parser.add_argument(
        "--model", action="append", default=[], help="run only this model (repeatable)"
    )
    parser.add_argument("--limit", type=int, help="override config limit (quick smoke run)")
    parser.add_argument("--output-dir", help="override config output_dir")
    parser.add_argument("--commit", default="", help="git commit to record in the results row")
    parser.add_argument("--test-set", default="test_v1", help="test set name for the results row")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.limit is not None:
        config = config.model_copy(update={"limit": args.limit})
    if args.output_dir:
        config = config.model_copy(update={"output_dir": args.output_dir})

    results = run(config, only=args.model)
    print_results_table(results, test_set=args.test_set, commit=args.commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
