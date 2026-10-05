"""All server configuration, read from environment variables (or `server/.env`).

Every field here has a line in `.env.example`; a test enforces it.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `extra="ignore"`: .env.example lists variables for features not built yet.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_version: str = "dev"
