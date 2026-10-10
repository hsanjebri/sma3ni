"""All server configuration, read from environment variables (or `server/.env`).

Every field here has a line in `.env.example`; a test enforces it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `extra="ignore"`: .env.example lists variables for features not built yet.
    # `env_ignore_empty`: `NAME=` (as in .env.example) means "use the default",
    # never an empty path or string. `hide_input_in_errors`: a startup error
    # must not print the other settings, secrets included, into the logs.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    # `local`: faster-whisper in this process. `groq`: Whisper on Groq's API, so
    # no GPU is needed, but the audio leaves the server (docs/PRIVACY.md).
    asr_backend: Literal["local", "groq"] = "local"
    groq_api_key: SecretStr | None = None
    groq_model: str = "whisper-large-v3-turbo"

    # Local backend. Defaults run anywhere: Whisper `small` from Hugging Face, on
    # CPU. With our own model: the exported CTranslate2 dir, with DEVICE=cuda.
    model_path: str = "small"
    model_version: str = "dev"
    device: str = "cpu"
    compute_type: str = "int8"
    # Transcriptions running at once; more queue. 1 per GPU is the safe start.
    asr_concurrency: int = 1

    max_audio_seconds: int = 300
    max_upload_mb: int = 25
    rate_limit_per_day: int = 60
    # Signs install tokens. Unset (dev only): a random key per process, so
    # tokens stop working on restart and differ between workers.
    token_secret: SecretStr | None = None
    # One `req-*` directory per request lives here and is deleted in `finally`.
    audio_tmp_dir: Path = Path(tempfile.gettempdir()) / "sma3ni-audio"
    # The deployed commit, shown by /v1/health. Render sets RENDER_GIT_COMMIT.
    git_commit: str | None = Field(
        default=None, validation_alias=AliasChoices("GIT_COMMIT", "RENDER_GIT_COMMIT")
    )

    @field_validator("token_secret")
    @classmethod
    def _long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("TOKEN_SECRET must be at least 32 characters")
        return value

    @model_validator(mode="after")
    def _groq_needs_a_key(self) -> Settings:
        if self.asr_backend == "groq" and self.groq_api_key is None:
            raise ValueError("ASR_BACKEND=groq needs GROQ_API_KEY")
        return self
