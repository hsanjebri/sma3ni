"""Manifests: load, validate, hash and summarize the datasets.

Manifest format is defined in `docs/ML_PLAN.md` - one JSON object per line:

    {"id": "vn_000123", "audio": "data/own/vn_000123.opus", "text": "...",
     "duration": 12.4, "speaker": "spk_017", "region": "sfax", "gender": "f",
     "source": "own", "consent": ["eval", "train"], "split": "test"}

`manifest_sha256()` is what freezes the test set: the hash in `ml/RESULTS.md`
must match, otherwise the numbers in that file describe a different test set.

External dataset loaders (LinTO, TuniSpeech, TEDxTN, Common Voice) are NOT here
yet on purpose: `ml/AGENTS.md` requires each loader to record its verified
license in the docstring, so they land in Phase 2 once each license is checked.
TODO(question): confirm the license of each dataset in `docs/ML_PLAN.md` before
adding its loader (redistribution and model-release terms, not just research use).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
