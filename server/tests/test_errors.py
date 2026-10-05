from __future__ import annotations

import logging

import httpx
import pytest
from fastapi import FastAPI

from app.errors import STATUS, ApiError
from app.schemas import ErrorCode

pytestmark = pytest.mark.anyio


def test_every_error_code_has_a_status() -> None:
    assert set(STATUS) == set(ErrorCode)


async def test_api_error_uses_the_contract_envelope(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    @app.get("/boom")
    async def boom() -> None:
        raise ApiError(ErrorCode.AUDIO_TOO_LONG, "Audio must be 5 minutes or less.")

    response = await client.get("/boom")

    assert response.status_code == 413
    assert response.json() == {
        "error": {"code": "audio_too_long", "message": "Audio must be 5 minutes or less."}
    }


async def test_unhandled_error_is_answered_and_its_message_never_logged(
    app: FastAPI, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    transcript = "عسلامة، توا نوصل للـ réunion"

    @app.get("/crash")
    async def crash() -> None:
        raise ValueError(f"could not parse {transcript}")

    with caplog.at_level(logging.DEBUG):
        response = await client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert transcript not in response.text
    assert "ValueError" in caplog.text
    assert transcript not in caplog.text
