from __future__ import annotations

import io
import json
import os
import subprocess
import time
import wave
from pathlib import Path

import pytest
from conftest import assert_nothing_left

from app.config import Settings
from app.errors import ApiError
from app.schemas import ErrorCode
from app.services import audio as audio_service
from app.services.audio import SAMPLE_RATE, clear_leftovers, prepared_audio

ACCEPTED = ["voice_note.opus", "note.m4a", "note.aac", "note.mp3", "note.wav"]


def upload(path: Path) -> io.BytesIO:
    return io.BytesIO(path.read_bytes())


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


def probe(path: Path) -> dict[str, str]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "json", str(path)],
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)["streams"][0]


@pytest.mark.parametrize(
    ("name", "suffix", "codec"),
    [
        ("voice_note.opus", ".ogg", "opus"),
        ("note.m4a", ".m4a", "aac"),
        ("note.aac", ".m4a", "aac"),  # raw ADTS goes into an m4a
        ("note.mp3", ".mp3", "mp3"),
        ("note.wav", ".wav", "pcm_s16le"),
    ],
)
def test_without_pcm_the_stream_is_remuxed_not_decoded(
    settings: Settings, clips: dict[str, Path], name: str, suffix: str, codec: str
) -> None:
    with prepared_audio(upload(clips[name]), settings, pcm=False) as audio:
        assert audio.path.suffix == suffix
        assert probe(audio.path)["codec_name"] == codec  # copied, not re-encoded
        assert audio.duration_s == pytest.approx(2.0, abs=0.1)
        assert [p.name for p in audio.path.parent.iterdir()] == [audio.path.name]

    assert_nothing_left(settings)


@pytest.mark.parametrize("pcm", [True, False], ids=["decoded", "remuxed"])
def test_metadata_never_leaves_the_server(
    settings: Settings, clips: dict[str, Path], pcm: bool
) -> None:
    assert b"SECRET-TITLE-TAG" in clips["tagged.m4a"].read_bytes()

    with prepared_audio(upload(clips["tagged.m4a"]), settings, pcm=pcm) as audio:
        assert b"SECRET-TITLE-TAG" not in audio.path.read_bytes()


def test_a_failed_remux_falls_back_to_wav(
    settings: Settings, clips: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The mp3 muxer cannot carry Opus, like any stream a container refuses.
    monkeypatch.setitem(audio_service._REMUX, "ogg", ("mp3", ".mp3"))

    with prepared_audio(upload(clips["voice_note.opus"]), settings, pcm=False) as audio:
        assert audio.path.name == "audio.wav"
        assert [p.name for p in audio.path.parent.iterdir()] == ["audio.wav"]

    assert_nothing_left(settings)
