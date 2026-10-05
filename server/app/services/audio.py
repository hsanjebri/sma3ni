"""Audio intake: copy the upload, check it, convert it for the ASR backend, delete it.

`pcm=True` decodes to 16 kHz mono WAV, for a model run here. `pcm=False` keeps
the compressed stream and only remuxes it into a clean container without
metadata, for an API such as Groq: about 3x less CPU on a small host, an upload
about 10x smaller, and no tags (e.g. an iPhone's location) leave the server.

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
# For a `pcm=False` remux: ffprobe format name -> (ffmpeg muxer, file suffix).
# Raw ADTS AAC goes into an .m4a, which ASR APIs accept and ADTS isn't.
_REMUX = {
    "ogg": ("ogg", ".ogg"),
    "mp3": ("mp3", ".mp3"),
    "wav": ("wav", ".wav"),
    "mov": ("mp4", ".m4a"),
    "mp4": ("mp4", ".m4a"),
    "m4a": ("mp4", ".m4a"),
    "aac": ("mp4", ".m4a"),
}

_REQUEST_DIR_PREFIX = "req-"
_CHUNK_BYTES = 1024 * 1024
# A 5-minute note decodes in about a second; this only stops a pathological file.
_SUBPROCESS_TIMEOUT_S = 60
# Far longer than any request, so a startup sweep never removes a live one.
_LEFTOVER_AGE_S = 600


@dataclass(frozen=True)
class Audio:
    # Inside the request's temp dir: a 16 kHz mono 16-bit WAV (`pcm=True`), or
    # the original stream remuxed without metadata, its suffix naming the format.
    path: Path
    duration_s: float


@contextmanager
def prepared_audio(upload: BinaryIO, settings: Settings, *, pcm: bool = True) -> Iterator[Audio]:
    """Yield one upload, ready for the ASR backend; its temp dir is gone once this exits.

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
        duration_s, formats = _probe(original, settings.max_audio_seconds)
        ready = _decode(original, workdir) if pcm else _remux(original, workdir, formats)
        original.unlink()
        yield Audio(path=ready, duration_s=duration_s)
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


def _probe(path: Path, max_seconds: int) -> tuple[float, set[str]]:
    """Check format, audio stream and duration; return the duration and format names."""
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
    formats = set(container.get("format_name", "").split(","))
    if not formats & ACCEPTED_FORMATS:
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
    return duration_s, formats


def _remux(src: Path, workdir: Path, formats: set[str]) -> Path:
    """Copy the first audio stream into a clean container: no re-encoding, no metadata."""
    muxer, suffix = next(_REMUX[name] for name in sorted(formats) if name in _REMUX)
    dest = workdir / f"audio{suffix}"
    result = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(src),
            "-map",
            "0:a:0",
            "-map_metadata",
            "-1",
            "-c:a",
            "copy",
            # No encoder version tag either.
            "-fflags",
            "+bitexact",
            "-f",
            muxer,
            str(dest),
        ]
    )
    if result.returncode != 0:
        # A stream the container can't carry as is: decoding always works.
        dest.unlink(missing_ok=True)
        return _decode(src, workdir)
    return dest


def _decode(src: Path, workdir: Path) -> Path:
    dest = workdir / "audio.wav"
    result = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(src),
            "-vn",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
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
    return dest


def _run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    # stderr is captured only to be dropped (it carries metadata tags).
    return subprocess.run(args, capture_output=True, timeout=_SUBPROCESS_TIMEOUT_S, check=False)


def _remove(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        # The dir name is random: it says nothing about the audio.
        logger.error("could not delete audio temp dir %s", path.name)
