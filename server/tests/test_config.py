from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_every_setting_is_documented_in_env_example() -> None:
    documented = {
        line.split("=", 1)[0].strip()
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    for field in Settings.model_fields:
        assert field.upper() in documented, f"{field.upper()} missing from .env.example"


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_VERSION", "whisper-darija-turbo-2026.10.1")

    assert Settings(_env_file=None).model_version == "whisper-darija-turbo-2026.10.1"


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # `AUDIO_TMP_DIR=` copied from .env.example must not become Path("") (the cwd).
    monkeypatch.setenv("AUDIO_TMP_DIR", "")

    assert Settings(_env_file=None).audio_tmp_dir == Settings.model_fields["audio_tmp_dir"].default
