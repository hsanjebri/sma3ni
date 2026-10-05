"""All server configuration, read from environment variables (or `server/.env`).

Every field here has a line in `.env.example`; a test enforces it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `extra="ignore"`: .env.example lists variables for features not built yet.
    # `env_ignore_empty`: `NAME=` (as in .env.example) means "use the default",
    # never an empty path or string.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    model_version: str = "dev"

    max_audio_seconds: int = 300
    max_upload_mb: int = 25
    # One `req-*` directory per request lives here and is deleted in `finally`.
    audio_tmp_dir: Path = Path(tempfile.gettempdir()) / "sma3ni-audio"
