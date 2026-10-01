"""Manifest loading, validation, hashing and the frozen-test-set guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sma3ni_ml import data


def entry(**overrides: object) -> data.ManifestEntry:
    payload: dict[str, object] = {
        "id": "vn_000001",
        "audio": "data/own/vn_000001.opus",
        "text": "شنوة أخبارك",
        "duration": 12.4,
        "speaker": "spk_001",
        "split": "test",
        "source": "own",
        "region": "sfax",
        "gender": "f",
        "consent": ["eval"],
    }
    payload.update(overrides)
    return data.ManifestEntry.model_validate(payload)


def write_jsonl(path: Path, entries: list[data.ManifestEntry]) -> Path:
    return data.write_manifest(entries, path)


class TestManifestEntry:
    def test_rejects_empty_text(self) -> None:
        with pytest.raises(ValueError, match="text"):
            entry(text="   ")

    def test_rejects_zero_duration(self) -> None:
        with pytest.raises(ValueError):
            entry(duration=0)

    def test_rejects_unknown_field(self) -> None:
        # A typo in a manifest must fail loudly, not be ignored.
        with pytest.raises(ValueError):
            entry(regionn="sfax")

    def test_rejects_unknown_split(self) -> None:
        with pytest.raises(ValueError):
            entry(split="validation")

    def test_slice_labels(self) -> None:
        clip = entry(duration=12.4, region="sfax")
        assert clip.slice_label("region") == "region=sfax"
        assert clip.slice_label("duration_bucket") == "duration_bucket=5-15s"
        assert clip.slice_label("noise") == "noise=unknown"


class TestDurationBucket:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [(1.0, "0-5s"), (5.0, "5-15s"), (29.9, "15-30s"), (45.0, "30-60s"), (120.0, "60s+")],
    )
    def test_buckets(self, seconds: float, expected: str) -> None:
        assert data.duration_bucket(seconds) == expected


class TestLoadManifest:
    def test_round_trip(self, tmp_path: Path) -> None:
        entries = [entry(id="vn_000002"), entry(id="vn_000001")]
        path = write_jsonl(tmp_path / "manifest.jsonl", entries)
        loaded = data.load_manifest(path)
        assert [item.id for item in loaded] == ["vn_000001", "vn_000002"]

    def test_filters_by_split(self, tmp_path: Path) -> None:
        entries = [
            entry(id="vn_000001", split="test"),
            entry(id="vn_000002", split="train", speaker="spk_002", consent=["train"]),
        ]
        path = write_jsonl(tmp_path / "manifest.jsonl", entries)
        assert [item.id for item in data.load_manifest(path, split="train")] == ["vn_000002"]

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        payload = json.dumps(entry().model_dump(), ensure_ascii=False)
        path.write_text(f"\n{payload}\n\n", encoding="utf-8")
        assert len(data.load_manifest(path)) == 1

    def test_error_names_the_line(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        path.write_text('{"id": "vn_1"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match=r"manifest\.jsonl:1"):
            data.load_manifest(path)

    def test_rejects_duplicate_ids(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.jsonl"
        payload = json.dumps(entry().model_dump(), ensure_ascii=False)
        path.write_text(f"{payload}\n{payload}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate ids"):
            data.load_manifest(path)


class TestHashing:
    def test_hash_is_stable_across_ordering(self) -> None:
        a, b = entry(id="vn_000001"), entry(id="vn_000002")
        assert data.manifest_sha256([a, b]) == data.manifest_sha256([b, a])

    def test_hash_changes_with_content(self) -> None:
        before = data.manifest_sha256([entry()])
        after = data.manifest_sha256([entry(text="باهي برشا")])
        assert before != after

    def test_assert_frozen_passes_on_match(self) -> None:
        entries = [entry()]
        data.assert_frozen(entries, data.manifest_sha256(entries))

    def test_assert_frozen_fails_when_the_test_set_changed(self) -> None:
        entries = [entry()]
        expected = data.manifest_sha256(entries)
        changed = [entry(text="كلام آخر")]
        with pytest.raises(ValueError, match="frozen test set changed"):
            data.assert_frozen(changed, expected)


class TestChecks:
    def test_detects_speaker_in_two_splits(self) -> None:
        entries = [
            entry(id="vn_000001", speaker="spk_001", split="test"),
            entry(id="vn_000002", speaker="spk_001", split="train"),
        ]
        assert data.check_speaker_separation(entries) == ["spk_001"]

    def test_clean_split_has_no_leak(self) -> None:
        entries = [
            entry(id="vn_000001", speaker="spk_001", split="test"),
            entry(id="vn_000002", speaker="spk_002", split="train"),
        ]
        assert data.check_speaker_separation(entries) == []

    def test_consent_check_lists_missing_ids(self) -> None:
        entries = [entry(id="vn_000001", consent=["eval"])]
        assert data.check_consent(entries, "train") == ["vn_000001"]
        assert data.check_consent(entries, "eval") == []


class TestSummarize:
    def test_headline_numbers(self) -> None:
        entries = [
            entry(id="vn_000001", duration=1800.0, speaker="spk_001", region="tunis", gender="m"),
            entry(id="vn_000002", duration=1800.0, speaker="spk_002", region="sfax", gender="f"),
        ]
        summary = data.summarize(entries)
        assert summary.clips == 2
        assert summary.hours == pytest.approx(1.0)
        assert summary.speakers == 2
        assert summary.by_region == {"sfax": 1, "tunis": 1}
        assert "2 clips" in summary.describe()

    def test_unknown_metadata_is_bucketed(self) -> None:
        summary = data.summarize([entry(region=None, gender=None)])
        assert summary.by_region == {"unknown": 1}
        assert summary.by_gender == {"unknown": 1}
