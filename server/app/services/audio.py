"""Audio intake: copy the upload, check it, decode it to 16 kHz mono WAV, delete it.

Each request gets its own `req-*` directory under `AUDIO_TMP_DIR`, removed in
`finally` whatever happens. Size, format and duration are checked before
decoding, and decoding happens before any model runs. Nothing here logs, and
ffmpeg's stderr is dropped: it echoes the file's metadata tags.

Blocking (file copy and subprocesses): call it from a worker thread.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
# ffprobe `format_name` entries covering the formats in API.md:
# opus and ogg, m4a, aac (ADTS), mp3, wav.
ACCEPTED_FORMATS = frozenset({"ogg", "mov", "mp4", "m4a", "aac", "mp3", "wav"})

_REQUEST_DIR_PREFIX = "req-"
_CHUNK_BYTES = 1024 * 1024
# A 5-minute note decodes in about a second; this only stops a pathological file.
_SUBPROCESS_TIMEOUT_S = 60
# Far longer than any request, so a startup sweep never removes a live one.
_LEFTOVER_AGE_S = 600


@dataclass(frozen=True)
class Audio:
    path: Path  # 16 kHz mono 16-bit WAV inside the request's temp dir
    duration_s: float


@contextmanager
def prepared_audio(upload: BinaryIO, settings: Settings) -> Iterator[Audio]:
    """Yield the decoded audio of one upload; its temp dir is gone once this exits.

    Raises `ApiError` for anything the contract names: `audio_too_large`,
    `invalid_audio`, `unsupported_format`, `audio_too_long`.
    """
    settings.audio_tmp_dir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=_REQUEST_DIR_PREFIX, dir=settings.audio_tmp_dir))
    try:
        # No extension on purpose: ffprobe detects the format from the content,
        # not from a client-supplied file name.
        original = workdir / "upload"
        _copy_capped(upload, original, settings.max_upload_mb)
        duration_s = _probe(original, settings.max_audio_seconds)
        wav = workdir / "audio.wav"
        _decode(original, wav)
        original.unlink()
        yield Audio(path=wav, duration_s=duration_s)
    finally:
        _remove(workdir)


def clear_leftovers(tmp_dir: Path) -> int:
    """Delete request dirs a crashed process left behind. Returns how many.

    Run at startup. Only touches old `req-*` directories, so it is safe with
    several workers sharing `tmp_dir` and never deletes anything else there.
    """
    if not tmp_dir.is_dir():
        return 0
    cutoff = time.time() - _LEFTOVER_AGE_S
    removed = 0
    for leftover in tmp_dir.glob(f"{_REQUEST_DIR_PREFIX}*"):
        if leftover.is_dir() and leftover.stat().st_mtime < cutoff:
            _remove(leftover)
            removed += 1
    return removed


def _copy_capped(upload: BinaryIO, dest: Path, max_mb: int) -> None:
    max_bytes = max_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := upload.read(_CHUNK_BYTES):
            size += len(chunk)
            if size > max_bytes:
                raise ApiError(ErrorCode.AUDIO_TOO_LARGE, f"Audio must be {max_mb} MB or less.")
            out.write(chunk)
    if size == 0:
        raise ApiError(ErrorCode.INVALID_AUDIO, "The audio file is empty.")


def _probe(path: Path, max_seconds: int) -> float:
    """Check format, audio stream and duration; return the duration in seconds."""
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise ApiError(ErrorCode.INVALID_AUDIO, "This file could not be read as audio.")

    info = json.loads(result.stdout)
    container = info.get("format", {})
    if not set(container.get("format_name", "").split(",")) & ACCEPTED_FORMATS:
        raise ApiError(
            ErrorCode.UNSUPPORTED_FORMAT, "Supported formats: opus, ogg, m4a, aac, mp3, wav."
        )
    if not any(stream.get("codec_type") == "audio" for stream in info.get("streams", [])):
        raise ApiError(ErrorCode.INVALID_AUDIO, "This file has no audio.")

    try:
        duration_s = float(container["duration"])
    except (KeyError, ValueError):
        raise ApiError(ErrorCode.INVALID_AUDIO, "This file has no readable duration.") from None
    if duration_s > max_seconds:
        raise ApiError(ErrorCode.AUDIO_TOO_LONG, f"Audio must be {max_seconds} seconds or less.")
    return duration_s


def _decode(src: Path, dest: Path) -> None:
    result = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    if result.returncode != 0:
        raise ApiError(ErrorCode.INVALID_AUDIO, "This file could not be decoded.")


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    # stderr is captured only to be dropped (it carries metadata tags).
    return subprocess.run(args, capture_output=True, timeout=_SUBPROCESS_TIMEOUT_S, check=False)


def _remove(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        # The dir name is random: it says nothing about the audio.
        logger.error("could not delete audio temp dir %s", path.name)
