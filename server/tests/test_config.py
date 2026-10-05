from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_render_sets_the_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "889a06b0123")

    assert Settings(_env_file=None).git_commit == "889a06b0123"


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_VERSION", "whisper-darija-turbo-2026.10.1")

    assert Settings(_env_file=None).model_version == "whisper-darija-turbo-2026.10.1"


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # `AUDIO_TMP_DIR=` copied from .env.example must not become Path("") (the cwd).
    monkeypatch.setenv("AUDIO_TMP_DIR", "")

    assert Settings(_env_file=None).audio_tmp_dir == Settings.model_fields["audio_tmp_dir"].default


def test_a_short_token_secret_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(_env_file=None, token_secret="too-short")


def test_groq_backend_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(_env_file=None, asr_backend="groq")


def test_startup_errors_never_print_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    secret = "do-not-print-me-do-not-print-me-0123"

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, asr_backend="groq", token_secret=secret)

    assert secret not in str(caught.value)
