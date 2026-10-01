"""Manifests: build, load, validate, hash and summarize the datasets.

Manifest format is defined in `docs/ML_PLAN.md` - one JSON object per line:

    {"id": "vn_000123", "audio": "data/own/vn_000123.opus", "text": "...",
     "duration": 12.4, "speaker": "spk_017", "region": "sfax", "gender": "f",
     "source": "own", "consent": ["eval", "train"], "split": "test"}

`manifest_sha256()` is what freezes the test set: the hash in `ml/RESULTS.md`
must match, otherwise the numbers in that file describe a different test set.

The Phase 1 collection workflow (also `uv run sma3ni-manifest --help`):

    sma3ni-manifest build --audio-dir data/own/audio --metadata clips.tsv \
        --split test --out data/test_v1/manifest.jsonl
    sma3ni-manifest validate data/test_v1/manifest.jsonl
    sma3ni-manifest agreement pass_a.tsv pass_b.tsv
    sma3ni-manifest hash data/test_v1/manifest.jsonl   # -> paste into RESULTS.md

External dataset loaders (LinTO, TuniSpeech, TEDxTN, Common Voice) are NOT here
yet on purpose: `ml/AGENTS.md` requires each loader to record its verified
license in the docstring, so they land in Phase 2 once each license is checked.
TODO(question): confirm the license of each dataset in `docs/ML_PLAN.md` before
adding its loader (redistribution and model-release terms, not just research use).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from sma3ni_ml.metrics import cer, wer
from sma3ni_ml.text import lint

Split = Literal["train", "dev", "test"]
Consent = Literal["eval", "train", "release"]

# Duration buckets used for slice reports (seconds, upper bound exclusive).
DURATION_BUCKETS: tuple[tuple[float, str], ...] = (
    (5.0, "0-5s"),
    (15.0, "5-15s"),
    (30.0, "15-30s"),
    (60.0, "30-60s"),
    (float("inf"), "60s+"),
)


class ManifestEntry(BaseModel):
    """One clip. Extra fields are rejected so a typo cannot silently vanish."""

    model_config = {"extra": "forbid"}

    id: str
    audio: str
    text: str
    duration: float = Field(gt=0)
    speaker: str
    split: Split
    source: str
    region: str | None = None
    gender: Literal["m", "f", "other"] | None = None
    consent: list[Consent] = Field(default_factory=list)
    noise: str | None = None
    """Optional noise-level label (e.g. clean / street / cafe) for slice reports."""

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value

    @property
    def duration_bucket(self) -> str:
        return duration_bucket(self.duration)

    def slice_label(self, key: str) -> str:
        """Label used by `metrics.slice_report`, e.g. `region=sfax`."""
        if key == "duration_bucket":
            return f"duration_bucket={self.duration_bucket}"
        value = getattr(self, key, None)
        return f"{key}={value if value is not None else 'unknown'}"


def duration_bucket(seconds: float) -> str:
    """Duration slice label for `seconds`."""
    for upper, label in DURATION_BUCKETS:
        if seconds < upper:
            return label
    return DURATION_BUCKETS[-1][1]


def load_manifest(path: str | Path, *, split: Split | None = None) -> list[ManifestEntry]:
    """Read a jsonl manifest, optionally keeping only one split.

    Raises `ValueError` naming the offending line, so a bad manifest is fixable
    without bisecting the file.
    """
    path = Path(path)
    entries: list[ManifestEntry] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = ManifestEntry.model_validate_json(line)
            except Exception as error:  # re-raised below with the file location
                raise ValueError(f"{path}:{line_number}: {error}") from error
            if split is None or entry.split == split:
                entries.append(entry)

    ids = Counter(entry.id for entry in entries)
    duplicates = sorted(entry_id for entry_id, count in ids.items() if count > 1)
    if duplicates:
        raise ValueError(f"{path}: duplicate ids: {', '.join(duplicates)}")
    return entries


def write_manifest(entries: Iterable[ManifestEntry], path: str | Path) -> Path:
    """Write entries as jsonl, one compact object per line, sorted by id."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in sorted(entries, key=lambda item: item.id):
            handle.write(json.dumps(entry.model_dump(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path


def manifest_sha256(entries: Sequence[ManifestEntry]) -> str:
    """Content hash of a manifest, used to freeze a test set.

    Computed from the entries sorted by id with sorted keys, so reordering or
    reformatting the file does not change the hash - only the data does.
    """
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.id):
        digest.update(json.dumps(entry.model_dump(), ensure_ascii=False, sort_keys=True).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def assert_frozen(entries: Sequence[ManifestEntry], expected_sha256: str) -> None:
    """Fail loudly if a frozen test set has changed.

    Called by the benchmark whenever the config declares a hash. The rule from
    `ml/AGENTS.md`: a new test set means `test_v2` plus approval, never an edit
    to `test_v1`.
    """
    actual = manifest_sha256(entries)
    if actual != expected_sha256:
        raise ValueError(
            "frozen test set changed: expected sha256 "
            f"{expected_sha256}, got {actual}. Do not edit a frozen set - "
            "create test_v2 and get approval."
        )


def check_speaker_separation(entries: Sequence[ManifestEntry]) -> list[str]:
    """Speakers appearing in more than one split (`docs/ML_PLAN.md`)."""
    splits: dict[str, set[str]] = {}
    for entry in entries:
        splits.setdefault(entry.speaker, set()).add(entry.split)
    return sorted(speaker for speaker, found in splits.items() if len(found) > 1)


def check_consent(entries: Sequence[ManifestEntry], purpose: Consent) -> list[str]:
    """Ids lacking consent for `purpose` - must be empty before using them."""
    return sorted(entry.id for entry in entries if purpose not in entry.consent)


def iter_split(entries: Iterable[ManifestEntry], split: Split) -> Iterator[ManifestEntry]:
    """Entries of one split."""
    return (entry for entry in entries if entry.split == split)


class ManifestSummary(BaseModel):
    """Headline numbers for a manifest - fills the TBDs in `RESULTS.md`."""

    clips: int
    hours: float
    speakers: int
    sha256: str
    by_split: dict[str, int]
    by_region: dict[str, int]
    by_gender: dict[str, int]
    by_duration_bucket: dict[str, int]

    def describe(self) -> str:
        return (
            f"{self.clips} clips, {self.hours:.2f} h, {self.speakers} speakers, "
            f"sha256 {self.sha256[:12]}..."
        )


def summarize(entries: Sequence[ManifestEntry]) -> ManifestSummary:
    """Clip / hour / speaker counts and the distributions ML_PLAN asks us to balance."""
    return ManifestSummary(
        clips=len(entries),
        hours=sum(entry.duration for entry in entries) / 3600,
        speakers=len({entry.speaker for entry in entries}),
        sha256=manifest_sha256(entries),
        by_split=dict(sorted(Counter(entry.split for entry in entries).items())),
        by_region=dict(sorted(Counter(entry.region or "unknown" for entry in entries).items())),
        by_gender=dict(sorted(Counter(entry.gender or "unknown" for entry in entries).items())),
        by_duration_bucket=dict(
            sorted(Counter(entry.duration_bucket for entry in entries).items())
        ),
    )


# --------------------------------------------------------------------------- #
# Collection workflow (Phase 1): build, validate, agreement, hash
# --------------------------------------------------------------------------- #

AUDIO_EXTENSIONS = (".opus", ".ogg", ".m4a", ".aac", ".mp3", ".wav", ".flac")

# Columns a transcriber fills in; `text` and `id` are the only required ones.
METADATA_COLUMNS = ("id", "text", "speaker", "region", "gender", "consent", "duration", "audio")


def read_metadata(path: str | Path) -> list[dict[str, str]]:
    """Read the transcriber's TSV: a header row, then one row per clip.

    Exported straight from a spreadsheet. Unknown columns are ignored so the
    sheet can carry notes; `consent` is comma or pipe separated.
    """
    path = Path(path)
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig") as handle:
        lines = [line.rstrip("\n") for line in handle if line.strip() and not line.startswith("#")]
    if not lines:
        raise ValueError(f"{path}: no rows")
    header = [column.strip().lower() for column in lines[0].split("\t")]
    if "id" not in header:
        raise ValueError(f"{path}: header needs an 'id' column, got {header}")
    for line_number, line in enumerate(lines[1:], start=2):
        values = line.split("\t")
        if len(values) > len(header):
            raise ValueError(
                f"{path}:{line_number}: {len(values)} values for {len(header)} columns"
            )
        row = {name: value.strip() for name, value in zip(header, values, strict=False)}
        rows.append(row)
    return rows


def probe_duration(audio_path: str | Path) -> float:
    """Audio duration in seconds, via ffprobe (ships with ffmpeg)."""
    import shutil
    import subprocess

    if shutil.which("ffprobe") is None:
        raise RuntimeError(
            "ffprobe not found - install ffmpeg, or put a 'duration' column in the "
            "metadata and pass --no-probe"
        )
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed on {audio_path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def find_audio(audio_dir: str | Path, clip_id: str) -> Path:
    """Locate `<clip_id>.<ext>` in `audio_dir`."""
    audio_dir = Path(audio_dir)
    for extension in AUDIO_EXTENSIONS:
        candidate = audio_dir / f"{clip_id}{extension}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no audio for {clip_id} in {audio_dir} (tried {AUDIO_EXTENSIONS})")


def build_manifest(
    rows: Sequence[dict[str, str]],
    *,
    audio_dir: str | Path,
    split: Split,
    source: str = "own",
    probe: bool = True,
    audio_root: str | Path = ".",
) -> list[ManifestEntry]:
    """Turn transcriber rows plus a folder of audio into manifest entries.

    `audio` paths are written relative to `audio_root` so the manifest stays
    portable between machines.
    """
    audio_root = Path(audio_root).resolve()
    entries: list[ManifestEntry] = []
    for row in rows:
        clip_id = row["id"]
        audio_path = Path(row["audio"]) if row.get("audio") else find_audio(audio_dir, clip_id)
        duration = float(row["duration"]) if row.get("duration") else None
        if duration is None:
            if not probe:
                raise ValueError(f"{clip_id}: no duration column and probing is off")
            duration = probe_duration(audio_path)
        consent = [
            value.strip()
            for value in row.get("consent", "").replace("|", ",").split(",")
            if value.strip()
        ]
        try:
            relative_audio = audio_path.resolve().relative_to(audio_root)
        except ValueError:
            relative_audio = audio_path
        entries.append(
            ManifestEntry.model_validate(
                {
                    "id": clip_id,
                    "audio": relative_audio.as_posix(),
                    "text": row["text"],
                    "duration": duration,
                    "speaker": row.get("speaker") or clip_id,
                    "split": row.get("split") or split,
                    "source": row.get("source") or source,
                    "region": row.get("region") or None,
                    "gender": row.get("gender") or None,
                    "consent": consent,
                    "noise": row.get("noise") or None,
                }
            )
        )
    return entries


class ValidationReport(BaseModel):
    """Everything wrong with a manifest, gathered in one pass."""

    missing_audio: list[str] = Field(default_factory=list)
    lint_issues: dict[str, list[str]] = Field(default_factory=dict)
    speakers_in_two_splits: list[str] = Field(default_factory=list)
    missing_consent: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not (
            self.missing_audio
            or self.lint_issues
            or self.speakers_in_two_splits
            or self.missing_consent
        )

    def describe(self) -> str:
        """Human-readable problem list, one per line."""
        lines: list[str] = []
        for clip_id in self.missing_audio:
            lines.append(f"missing audio: {clip_id}")
        for clip_id, issues in sorted(self.lint_issues.items()):
            for issue in issues:
                lines.append(f"transcript {clip_id}: {issue}")
        for speaker in self.speakers_in_two_splits:
            lines.append(f"speaker in more than one split: {speaker}")
        for purpose, clip_ids in sorted(self.missing_consent.items()):
            lines.append(f"missing '{purpose}' consent: {', '.join(clip_ids)}")
        return "\n".join(lines)


# A split's clips must carry at least this consent (docs/ML_PLAN.md).
CONSENT_FOR_SPLIT: dict[str, Consent] = {"test": "eval", "dev": "eval", "train": "train"}


def validate(
    entries: Sequence[ManifestEntry], *, audio_root: str | Path = ".", check_audio: bool = True
) -> ValidationReport:
    """Check a manifest against the guidelines and the ML plan's data rules."""
    audio_root = Path(audio_root)
    report = ValidationReport()

    if check_audio:
        report.missing_audio = [
            entry.id for entry in entries if not (audio_root / entry.audio).exists()
        ]

    for entry in entries:
        issues = [str(issue) for issue in lint(entry.text)]
        if issues:
            report.lint_issues[entry.id] = issues

    report.speakers_in_two_splits = check_speaker_separation(entries)

    for split, purpose in CONSENT_FOR_SPLIT.items():
        in_split = [entry for entry in entries if entry.split == split]
        missing = check_consent(in_split, purpose)
        if missing:
            report.missing_consent[purpose] = missing

    return report


def read_texts(path: str | Path) -> dict[str, str]:
    """`{clip id: transcript}` from a manifest (.jsonl) or a metadata TSV."""
    path = Path(path)
    if path.suffix == ".jsonl":
        return {entry.id: entry.text for entry in load_manifest(path)}
    rows = read_metadata(path)
    return {row["id"]: row.get("text", "") for row in rows}


class AgreementReport(BaseModel):
    """Inter-transcriber agreement, measured as WER between two passes."""

    clips: int
    wer: float
    cer: float
    only_in_first: list[str] = Field(default_factory=list)
    only_in_second: list[str] = Field(default_factory=list)

    @property
    def meets_target(self) -> bool:
        """The guidelines' section 8 target: under 10% disagreement."""
        return self.wer < 0.10

    def describe(self) -> str:
        verdict = "OK" if self.meets_target else "ABOVE the 10% target"
        return (
            f"{self.clips} clips double-transcribed: WER {self.wer:.1%}, "
            f"CER {self.cer:.1%} - {verdict}"
        )


def agreement(first: dict[str, str], second: dict[str, str]) -> AgreementReport:
    """Agreement between two transcription passes of the same clips.

    Section 8 of the guidelines: 10% of clips get a second transcriber, and the
    WER between the two passes is the measure. A high number means the
    guidelines are ambiguous, not that a transcriber is bad.
    """
    shared = sorted(set(first) & set(second))
    refs = [first[clip_id] for clip_id in shared]
    hyps = [second[clip_id] for clip_id in shared]
    return AgreementReport(
        clips=len(shared),
        wer=wer(refs, hyps) if shared else 0.0,
        cer=cer(refs, hyps) if shared else 0.0,
        only_in_first=sorted(set(first) - set(second)),
        only_in_second=sorted(set(second) - set(first)),
    )


def _command_build(args: argparse.Namespace) -> int:
    rows = read_metadata(args.metadata)
    entries = build_manifest(
        rows,
        audio_dir=args.audio_dir,
        split=args.split,
        source=args.source,
        probe=not args.no_probe,
        audio_root=args.audio_root,
    )
    write_manifest(entries, args.out)
    summary = summarize(entries)
    print(f"wrote {args.out}: {summary.describe()}")
    report = validate(entries, audio_root=args.audio_root)
    if not report.ok:
        print("\nproblems found - fix these before freezing:")
        print(report.describe())
        return 1
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    entries = load_manifest(args.manifest)
    summary = summarize(entries)
    print(summary.describe())
    print(f"splits: {summary.by_split}")
    print(f"regions: {summary.by_region}")
    print(f"gender: {summary.by_gender}")
    print(f"durations: {summary.by_duration_bucket}")
    report = validate(entries, audio_root=args.audio_root, check_audio=not args.no_audio_check)
    if report.ok:
        print("\nno problems found")
        return 0
    print("\nproblems:")
    print(report.describe())
    return 0 if args.warn_only else 1


def _command_hash(args: argparse.Namespace) -> int:
    entries = load_manifest(args.manifest, split=args.split)
    summary = summarize(entries)
    print(f"sha256: {summary.sha256}")
    print(f"clips: {summary.clips}  hours: {summary.hours:.2f}  speakers: {summary.speakers}")
    print("\nFor the RESULTS.md header:")
    print(
        f"**Frozen test set:** `{args.name}` - sha256: `{summary.sha256}` - "
        f"clips: {summary.clips} - hours: {summary.hours:.2f} - speakers: {summary.speakers}"
    )
    return 0


def _command_agreement(args: argparse.Namespace) -> int:
    report = agreement(read_texts(args.first), read_texts(args.second))
    if report.clips == 0:
        print("no clips in common between the two passes")
        return 1
    print(report.describe())
    for clip_id in report.only_in_first:
        print(f"  only in {args.first}: {clip_id}")
    for clip_id in report.only_in_second:
        print(f"  only in {args.second}: {clip_id}")
    return 0 if report.meets_target else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sma3ni-manifest", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="metadata TSV + audio folder -> manifest.jsonl")
    build.add_argument("--metadata", required=True, help="TSV with id/text/speaker/... columns")
    build.add_argument("--audio-dir", required=True, help="folder holding <id>.<ext> files")
    build.add_argument("--out", required=True, help="manifest to write")
    build.add_argument("--split", default="test", choices=["train", "dev", "test"])
    build.add_argument("--source", default="own")
    build.add_argument("--audio-root", default=".", help="paths are written relative to this")
    build.add_argument("--no-probe", action="store_true", help="trust the metadata duration column")
    build.set_defaults(handler=_command_build)

    check = subparsers.add_parser("validate", help="schema, audio, transcripts, splits, consent")
    check.add_argument("manifest")
    check.add_argument("--audio-root", default=".")
    check.add_argument("--no-audio-check", action="store_true")
    check.add_argument("--warn-only", action="store_true", help="report problems but exit 0")
    check.set_defaults(handler=_command_validate)

    digest = subparsers.add_parser("hash", help="content hash to freeze a test set")
    digest.add_argument("manifest")
    digest.add_argument("--split", default=None, choices=["train", "dev", "test"])
    digest.add_argument("--name", default="test_v1")
    digest.set_defaults(handler=_command_hash)

    agree = subparsers.add_parser("agreement", help="WER between two transcription passes")
    agree.add_argument("first")
    agree.add_argument("second")
    agree.set_defaults(handler=_command_agreement)

    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
