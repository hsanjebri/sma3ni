"""End-to-end benchmark run, scored from a predictions file (no GPU, no model)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sma3ni_ml import benchmark, data

CLIPS = [
    {
        "id": "vn_000001",
        "audio": "audio/vn_000001.opus",
        "text": "شنوة أخبارك يا صاحبي",
        "duration": 4.0,
        "speaker": "spk_001",
        "split": "test",
        "source": "own",
        "region": "tunis",
        "gender": "m",
        "consent": ["eval"],
    },
    {
        "id": "vn_000002",
        "audio": "audio/vn_000002.opus",
        "text": "نمشي للـ réunion متاع demain",
        "duration": 20.0,
        "speaker": "spk_002",
        "split": "test",
        "source": "own",
        "region": "sfax",
        "gender": "f",
        "consent": ["eval"],
    },
    {
        "id": "vn_000003",
        "audio": "audio/vn_000003.opus",
        "text": "برشا خير",
        "duration": 3.0,
        "speaker": "spk_003",
        "split": "train",
        "source": "own",
        "region": "tunis",
        "gender": "f",
        "consent": ["train"],
    },
]

HYPOTHESES = {
    # One substitution out of four words.
    "vn_000001": "شنوة أحوالك يا صاحبي",
    # Perfect, including both code-switched words.
    "vn_000002": "نمشي للـ réunion متاع demain",
    "vn_000003": "برشا خير",
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A manifest plus a predictions file, as a benchmark config would see them."""
    manifest = tmp_path / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        for clip in CLIPS:
            handle.write(json.dumps(clip, ensure_ascii=False) + "\n")

    predictions = tmp_path / "hyp.jsonl"
    with predictions.open("w", encoding="utf-8", newline="\n") as handle:
        for clip_id, text in HYPOTHESES.items():
            handle.write(json.dumps({"id": clip_id, "text": text}, ensure_ascii=False) + "\n")
    return tmp_path


def config_for(project: Path, **overrides: object) -> benchmark.BenchmarkConfig:
    payload: dict[str, object] = {
        "manifest": str(project / "manifest.jsonl"),
        "split": "test",
        "output_dir": str(project / "reports"),
        "slices": ["region", "duration_bucket"],
        "min_slice_utterances": 1,
        "models": [
            {
                "name": "replay",
                "backend": "predictions",
                "model": str(project / "hyp.jsonl"),
            }
        ],
    }
    payload.update(overrides)
    return benchmark.BenchmarkConfig.model_validate(payload)


class TestConfig:
    def test_rejects_unknown_key(self, project: Path) -> None:
        with pytest.raises(ValueError):
            config_for(project, unexpected="x")

    def test_loads_the_shipped_config(self) -> None:
        # configs/benchmark.yaml must stay valid as the schema changes.
        config_path = Path(__file__).resolve().parents[1] / "configs" / "benchmark.yaml"
        config = benchmark.load_config(config_path)
        assert config.models
        assert config.split == "test"

    def test_unknown_backend_is_named(self) -> None:
        spec = benchmark.ModelSpec(name="x", backend="telepathy")
        with pytest.raises(ValueError, match="unknown backend"):
            benchmark.build_backend(spec)


class TestRun:
    def test_scores_only_the_requested_split(self, project: Path) -> None:
        results = benchmark.run(config_for(project))
        assert len(results) == 1
        result = results[0]
        # 1 substitution over the 9 reference words of the two test clips.
        assert result.metrics.utterances == 2
        assert result.metrics.wer == pytest.approx(1 / 9)

    def test_code_switch_words_are_tracked(self, project: Path) -> None:
        result = benchmark.run(config_for(project))[0]
        assert result.metrics.code_switch.support == 2
        assert result.metrics.code_switch.f1 == 1.0

    def test_slices_are_reported(self, project: Path) -> None:
        result = benchmark.run(config_for(project))[0]
        assert result.slices["region=tunis"].wer == pytest.approx(0.25)
        assert result.slices["region=sfax"].wer == 0.0
        assert "duration_bucket=15-30s" in result.slices

    def test_limit_truncates_deterministically(self, project: Path) -> None:
        result = benchmark.run(config_for(project, limit=1))[0]
        assert result.metrics.utterances == 1

    def test_writes_report_and_hypotheses(self, project: Path) -> None:
        benchmark.run(config_for(project))
        reports = sorted((project / "reports").glob("*.json"))
        hypotheses = sorted((project / "reports").glob("*.hyp.jsonl"))
        assert len(reports) == 1
        assert len(hypotheses) == 1
        payload = json.loads(reports[0].read_text(encoding="utf-8"))
        assert payload["model"] == "replay"
        assert payload["overall"]["wer"] == pytest.approx(1 / 9, abs=1e-4)
        assert "region=sfax" in payload["slices"]

    def test_results_row_is_pasteable(self, project: Path) -> None:
        result = benchmark.run(config_for(project))[0]
        row = result.results_row(commit="abc1234", notes="smoke")
        assert row.startswith("|")
        assert row.count("|") == 10
        assert "replay" in row and "test_v1" in row and "abc1234" in row

    def test_rtf_uses_manifest_durations(self, project: Path) -> None:
        result = benchmark.run(config_for(project))[0]
        assert result.audio_seconds == pytest.approx(24.0)
        assert result.rtf >= 0.0

    def test_model_filter(self, project: Path) -> None:
        with pytest.raises(ValueError, match="no model matched"):
            benchmark.run(config_for(project), only=["does-not-exist"])

    def test_empty_split_is_an_error(self, project: Path) -> None:
        with pytest.raises(ValueError, match="no clips"):
            benchmark.run(config_for(project, split="dev"))

    def test_missing_prediction_is_an_error(self, project: Path) -> None:
        predictions = project / "partial.jsonl"
        predictions.write_text(
            json.dumps({"id": "vn_000001", "text": "x"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        config = config_for(
            project,
            models=[{"name": "partial", "backend": "predictions", "model": str(predictions)}],
        )
        with pytest.raises(KeyError, match="vn_000002"):
            benchmark.run(config)


class TestFrozenTestSet:
    def test_matching_hash_runs(self, project: Path) -> None:
        entries = data.load_manifest(project / "manifest.jsonl", split="test")
        config = config_for(project, manifest_sha256=data.manifest_sha256(entries))
        assert benchmark.run(config)

    def test_tbd_hash_skips_the_check(self, project: Path) -> None:
        assert benchmark.run(config_for(project, manifest_sha256="TBD"))

    def test_changed_test_set_aborts_the_run(self, project: Path) -> None:
        config = config_for(project, manifest_sha256="0" * 64)
        with pytest.raises(ValueError, match="frozen test set changed"):
            benchmark.run(config)


class TestCli:
    def test_main_runs_end_to_end(self, project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        config_path = project / "benchmark.yaml"
        config_path.write_text(
            json.dumps(config_for(project).model_dump(), ensure_ascii=False), encoding="utf-8"
        )
        exit_code = benchmark.main(["--config", str(config_path), "--commit", "abc1234"])
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Paste into ml/RESULTS.md" in output
        assert "replay" in output
