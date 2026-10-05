from __future__ import annotations

import io
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path

import pytest

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode
from app.services.audio import SAMPLE_RATE, clear_leftovers, prepared_audio

TONE = ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
# Synthetic clips only: the repo never holds real voices (AGENTS.md).
CLIPS = {
    "voice_note.opus": [*TONE, "-c:a", "libopus", "-f", "ogg"],  # what WhatsApp shares
    "note.m4a": [*TONE, "-c:a", "aac"],
    "note.aac": [*TONE, "-c:a", "aac", "-f", "adts"],
    "note.mp3": [*TONE, "-c:a", "libmp3lame"],
    "note.wav": TONE,
    "note.flac": [*TONE, "-c:a", "flac"],  # real audio, but not a format API.md accepts
    "silent.mp4": ["-f", "lavfi", "-i", "color=c=black:s=16x16:d=1", "-c:v", "mpeg4"],
}
ACCEPTED = ["voice_note.opus", "note.m4a", "note.aac", "note.mp3", "note.wav"]


@pytest.fixture(scope="session")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("ffmpeg/ffprobe not on PATH: see 'System dependencies' in server/AGENTS.md")
    out = tmp_path_factory.mktemp("clips")
    for name, args in CLIPS.items():
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", *args, str(out / name)],
            check=True,
            capture_output=True,
        )
    return {name: out / name for name in CLIPS}


def upload(path: Path) -> io.BytesIO:
    return io.BytesIO(path.read_bytes())


def assert_nothing_left(settings: Settings) -> None:
    assert list(settings.audio_tmp_dir.iterdir()) == []


def error_code(settings: Settings, data: io.BytesIO) -> ErrorCode:
    with pytest.raises(ApiError) as caught, prepared_audio(data, settings):
        pass
    assert_nothing_left(settings)
    return caught.value.code


@pytest.mark.parametrize("name", ACCEPTED)
def test_accepted_formats_decode_to_16k_mono_wav(
    settings: Settings, clips: dict[str, Path], name: str
) -> None:
    with prepared_audio(upload(clips[name]), settings) as audio:
        assert audio.path.parent.parent == settings.audio_tmp_dir
        assert audio.duration_s == pytest.approx(2.0, abs=0.1)
        with wave.open(str(audio.path)) as decoded:
            assert decoded.getframerate() == SAMPLE_RATE
            assert decoded.getnchannels() == 1
            assert decoded.getsampwidth() == 2
        # Only the decoded copy is kept while the request runs.
        assert [p.name for p in audio.path.parent.iterdir()] == ["audio.wav"]

    assert_nothing_left(settings)


def test_too_large_is_rejected_while_copying(settings: Settings) -> None:
    settings.max_upload_mb = 1
    too_big = io.BytesIO(b"\0" * (1024 * 1024 + 1))

    assert error_code(settings, too_big) is ErrorCode.AUDIO_TOO_LARGE


def test_too_long_is_rejected_before_decoding(settings: Settings, clips: dict[str, Path]) -> None:
    settings.max_audio_seconds = 1

    assert error_code(settings, upload(clips["voice_note.opus"])) is ErrorCode.AUDIO_TOO_LONG


def test_format_outside_the_contract_is_unsupported(
    settings: Settings, clips: dict[str, Path]
) -> None:
    assert error_code(settings, upload(clips["note.flac"])) is ErrorCode.UNSUPPORTED_FORMAT


@pytest.mark.parametrize(
    "data",
    [b"", b"this is not audio\n" * 200],
    ids=["empty", "text"],
)
def test_unreadable_upload_is_invalid(settings: Settings, data: bytes) -> None:
    assert error_code(settings, io.BytesIO(data)) is ErrorCode.INVALID_AUDIO


def test_container_without_an_audio_stream_is_invalid(
    settings: Settings, clips: dict[str, Path]
) -> None:
    assert error_code(settings, upload(clips["silent.mp4"])) is ErrorCode.INVALID_AUDIO


def test_temp_dir_is_removed_when_the_caller_fails(
    settings: Settings, clips: dict[str, Path]
) -> None:
    # Stands in for the ASR step crashing while the decoded audio is on disk.
    with pytest.raises(RuntimeError), prepared_audio(upload(clips["note.wav"]), settings):
        raise RuntimeError("model crashed")

    assert_nothing_left(settings)


def test_clear_leftovers_only_removes_old_request_dirs(tmp_path: Path) -> None:
    stale = tmp_path / "req-stale"
    live = tmp_path / "req-live"
    unrelated = tmp_path / "keep-me"
    for directory in (stale, live, unrelated):
        directory.mkdir()
        (directory / "audio.wav").write_bytes(b"\0")
    an_hour_ago = time.time() - 3600
    os.utime(stale, (an_hour_ago, an_hour_ago))
    os.utime(unrelated, (an_hour_ago, an_hour_ago))

    assert clear_leftovers(tmp_path) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep-me", "req-live"]


def test_clear_leftovers_without_a_tmp_dir_is_a_no_op(tmp_path: Path) -> None:
    assert clear_leftovers(tmp_path / "missing") == 0
