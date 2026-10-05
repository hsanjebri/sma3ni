"""Request and response models. These mirror `docs/API.md` exactly: change both together."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    INVALID_AUDIO = "invalid_audio"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNAUTHORIZED = "unauthorized"
    AUDIO_TOO_LARGE = "audio_too_large"
    AUDIO_TOO_LONG = "audio_too_long"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    MODEL_LOADING = "model_loading"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    model_version: str


class Script(StrEnum):
    ARABIC = "arabic"
    ARABIZI = "arabizi"


class TranslateTarget(StrEnum):
    FR = "fr"
    EN = "en"


class Segment(BaseModel):
    start: float
    end: float
    text: str


class TranscribeResponse(BaseModel):
    request_id: str
    text: str
    script: Script
    language: str
    duration_s: float
    segments: list[Segment]
    summary: str | None = None
    translation: str | None = None
    replies: list[str] | None = None
    model_version: str
    processing_ms: int
