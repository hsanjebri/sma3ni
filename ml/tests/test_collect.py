"""The Phase 1 collection workflow: build, validate, agreement, hash."""

from __future__ import annotations

from pathlib import Path

import pytest

from sma3ni_ml import data

METADATA = "\t".join(["id", "text", "speaker", "region", "gender", "consent", "duration"])
ROWS = [
    ["vn_000001", "شنوة أخبارك يا صاحبي", "spk_001", "tunis", "m", "eval", "4.0"],
    ["vn_000002", "نمشي لل réunion متاع demain", "spk_002", "sfax", "f", "eval,train", "22.0"],
]


@pytest.fixture
def collection(tmp_path: Path) -> Path:
    """A metadata TSV plus a folder of (empty) audio files, as collected."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for row in ROWS:
        (audio_dir / f"{row[0]}.opus").write_bytes(b"")
    metadata = tmp_path / "clips.tsv"
    metadata.write_text(
        "\n".join([METADATA, *["\t".join(row) for row in ROWS]]) + "\n", encoding="utf-8"
    )
    return tmp_path


class TestReadMetadata:
    def test_reads_rows(self, collection: Path) -> None:
        rows = data.read_metadata(collection / "clips.tsv")
        assert [row["id"] for row in rows] == ["vn_000001", "vn_000002"]
        assert rows[1]["region"] == "sfax"

    def test_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "clips.tsv"
        path.write_text(f"# notes\n{METADATA}\n\n{chr(9).join(ROWS[0])}\n", encoding="utf-8")
        assert len(data.read_metadata(path)) == 1

    def test_requires_an_id_column(self, tmp_path: Path) -> None:
        path = tmp_path / "clips.tsv"
        path.write_text("text\tspeaker\nhello\tspk_001\n", encoding="utf-8")
        with pytest.raises(ValueError, match="needs an 'id' column"):
            data.read_metadata(path)

    def test_rejects_a_row_with_too_many_values(self, tmp_path: Path) -> None:
        path = tmp_path / "clips.tsv"
        path.write_text("id\ttext\nvn_1\thello\toops\n", encoding="utf-8")
        with pytest.raises(ValueError, match="values for"):
            data.read_metadata(path)

    def test_tolerates_a_bom(self, tmp_path: Path) -> None:
        # Excel writes UTF-8 with a BOM; the id column must still be found.
        path = tmp_path / "clips.tsv"
        path.write_bytes(b"\xef\xbb\xbf" + f"{METADATA}\n{chr(9).join(ROWS[0])}\n".encode())
        assert data.read_metadata(path)[0]["id"] == "vn_000001"


class TestFindAudio:
    def test_finds_by_extension(self, collection: Path) -> None:
        assert data.find_audio(collection / "audio", "vn_000001").name == "vn_000001.opus"

    def test_missing_audio_names_the_clip(self, collection: Path) -> None:
        with pytest.raises(FileNotFoundError, match="vn_999"):
            data.find_audio(collection / "audio", "vn_999")


class TestBuildManifest:
    def test_builds_entries_from_metadata(self, collection: Path) -> None:
        entries = data.build_manifest(
            data.read_metadata(collection / "clips.tsv"),
            audio_dir=collection / "audio",
            split="test",
            probe=False,
            audio_root=collection,
        )
        assert [entry.id for entry in entries] == ["vn_000001", "vn_000002"]
        assert entries[0].duration == 4.0
        assert entries[0].split == "test"
        # Paths are relative to audio_root, so the manifest is portable.
        assert entries[0].audio == "audio/vn_000001.opus"

    def test_parses_multi_value_consent(self, collection: Path) -> None:
        entries = data.build_manifest(
            data.read_metadata(collection / "clips.tsv"),
            audio_dir=collection / "audio",
            split="test",
            probe=False,
            audio_root=collection,
        )
        assert entries[1].consent == ["eval", "train"]

    def test_missing_duration_without_probing_is_an_error(self, collection: Path) -> None:
        rows = data.read_metadata(collection / "clips.tsv")
        rows[0]["duration"] = ""
        with pytest.raises(ValueError, match="no duration column"):
            data.build_manifest(rows, audio_dir=collection / "audio", split="test", probe=False)

    def test_probe_duration_explains_a_missing_ffprobe(
        self, collection: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _name: None)
        with pytest.raises(RuntimeError, match="ffprobe not found"):
            data.probe_duration(collection / "audio" / "vn_000001.opus")


class TestValidate:
    def build(self, collection: Path) -> list[data.ManifestEntry]:
        return data.build_manifest(
            data.read_metadata(collection / "clips.tsv"),
            audio_dir=collection / "audio",
            split="test",
            probe=False,
            audio_root=collection,
        )

    def test_clean_manifest_passes(self, collection: Path) -> None:
        report = data.validate(self.build(collection), audio_root=collection)
        assert report.ok
        assert report.describe() == ""

    def test_flags_missing_audio(self, collection: Path) -> None:
        entries = self.build(collection)
        (collection / "audio" / "vn_000001.opus").unlink()
        report = data.validate(entries, audio_root=collection)
        assert report.missing_audio == ["vn_000001"]
        assert not report.ok

    def test_flags_a_transcript_that_breaks_the_guidelines(self, collection: Path) -> None:
        entries = self.build(collection)
        entries[0].text = "٣ ساعات بَرشا"  # Arabic-Indic digits + diacritics
        report = data.validate(entries, audio_root=collection)
        assert "vn_000001" in report.lint_issues
        assert "section 3" in report.describe()

    def test_flags_a_speaker_in_two_splits(self, collection: Path) -> None:
        entries = self.build(collection)
        entries[1].speaker = entries[0].speaker
        entries[1].split = "train"
        entries[1].consent = ["train"]
        report = data.validate(entries, audio_root=collection)
        assert report.speakers_in_two_splits == ["spk_001"]

    def test_flags_a_test_clip_without_eval_consent(self, collection: Path) -> None:
        entries = self.build(collection)
        entries[0].consent = []
        report = data.validate(entries, audio_root=collection)
        assert report.missing_consent["eval"] == ["vn_000001"]
        assert "missing 'eval' consent" in report.describe()


class TestAgreement:
    def test_identical_passes_agree_perfectly(self) -> None:
        first = {"vn_1": "شنوة أخبارك"}
        report = data.agreement(first, dict(first))
        assert report.wer == 0.0
        assert report.meets_target

    def test_disagreement_above_target_is_reported(self) -> None:
        first = {"vn_1": "شنوة أخبارك يا صاحبي"}
        second = {"vn_1": "شنوة أحوالك يا صاحبي"}
        report = data.agreement(first, second)
        assert report.wer == pytest.approx(0.25)
        assert not report.meets_target
        assert "ABOVE the 10% target" in report.describe()

    def test_spelling_only_differences_do_not_count(self) -> None:
        # Normalization means punctuation and hamza choices are not disagreement.
        report = data.agreement({"vn_1": "أنا باهي، برشا."}, {"vn_1": "انا باهي برشا"})
        assert report.wer == 0.0

    def test_reports_clips_only_one_person_transcribed(self) -> None:
        report = data.agreement({"vn_1": "a", "vn_2": "b"}, {"vn_1": "a", "vn_3": "c"})
        assert report.clips == 1
        assert report.only_in_first == ["vn_2"]
        assert report.only_in_second == ["vn_3"]

    def test_no_overlap_is_not_a_crash(self) -> None:
        report = data.agreement({"vn_1": "a"}, {"vn_2": "b"})
        assert report.clips == 0
        assert report.wer == 0.0


class TestReadTexts:
    def test_from_metadata_tsv(self, collection: Path) -> None:
        texts = data.read_texts(collection / "clips.tsv")
        assert texts["vn_000001"] == "شنوة أخبارك يا صاحبي"

    def test_from_manifest_jsonl(self, collection: Path, tmp_path: Path) -> None:
        entries = data.build_manifest(
            data.read_metadata(collection / "clips.tsv"),
            audio_dir=collection / "audio",
            split="test",
            probe=False,
            audio_root=collection,
        )
        manifest = data.write_manifest(entries, tmp_path / "m.jsonl")
        assert data.read_texts(manifest)["vn_000002"].endswith("demain")


class TestCli:
    def test_build_then_validate_then_hash(
        self, collection: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        manifest = collection / "manifest.jsonl"
        assert (
            data.main(
                [
                    "build",
                    "--metadata",
                    str(collection / "clips.tsv"),
                    "--audio-dir",
                    str(collection / "audio"),
                    "--out",
                    str(manifest),
                    "--audio-root",
                    str(collection),
                    "--no-probe",
                ]
            )
            == 0
        )
        assert manifest.exists()

        assert data.main(["validate", str(manifest), "--audio-root", str(collection)]) == 0
        assert "no problems found" in capsys.readouterr().out

        assert data.main(["hash", str(manifest)]) == 0
        output = capsys.readouterr().out
        assert "sha256:" in output
        assert "Frozen test set:" in output

    def test_validate_exits_nonzero_on_problems(
        self, collection: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        manifest = collection / "manifest.jsonl"
        data.main(
            [
                "build",
                "--metadata",
                str(collection / "clips.tsv"),
                "--audio-dir",
                str(collection / "audio"),
                "--out",
                str(manifest),
                "--audio-root",
                str(collection),
                "--no-probe",
            ]
        )
        capsys.readouterr()
        (collection / "audio" / "vn_000001.opus").unlink()
        assert data.main(["validate", str(manifest), "--audio-root", str(collection)]) == 1
        assert "missing audio" in capsys.readouterr().out

    def test_validate_warn_only_exits_zero(self, collection: Path) -> None:
        manifest = collection / "manifest.jsonl"
        data.main(
            [
                "build",
                "--metadata",
                str(collection / "clips.tsv"),
                "--audio-dir",
                str(collection / "audio"),
                "--out",
                str(manifest),
                "--audio-root",
                str(collection),
                "--no-probe",
            ]
        )
        (collection / "audio" / "vn_000001.opus").unlink()
        assert (
            data.main(["validate", str(manifest), "--audio-root", str(collection), "--warn-only"])
            == 0
        )

    def test_agreement_command_fails_above_target(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        first = tmp_path / "a.tsv"
        second = tmp_path / "b.tsv"
        first.write_text("id\ttext\nvn_1\tشنوة أخبارك يا صاحبي\n", encoding="utf-8")
        second.write_text("id\ttext\nvn_1\tشنوة أحوالك يا صاحبي\n", encoding="utf-8")
        assert data.main(["agreement", str(first), str(second)]) == 1
        assert "ABOVE the 10% target" in capsys.readouterr().out
