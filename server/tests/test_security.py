from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from conftest import FakeTranscriber
from fastapi import FastAPI

from app.config import Settings
from app.security import MemoryUsageStore, TokenSigner

pytestmark = pytest.mark.anyio


def voice_note(clips: dict[str, Path]) -> dict[str, tuple[str, bytes, str]]:
    return {"audio": ("note.opus", clips["voice_note.opus"].read_bytes(), "audio/ogg")}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_an_installed_token_can_transcribe(
    anon_client: httpx.AsyncClient, clips: dict[str, Path]
) -> None:
    install = await anon_client.post("/v1/install")
    assert install.status_code == 200
    token = install.json()["token"]

    response = await anon_client.post(
        "/v1/transcribe", files=voice_note(clips), headers=bearer(token)
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer ",
        "Bearer not-a-token",
        "Bearer abc.def",
        "Bearer café.signé".encode("latin-1"),  # non-ASCII must be a 401, not a crash
        "Basic dXNlcjpwYXNz",
    ],
    ids=["missing", "empty", "no-signature", "bad-signature", "non-ascii", "wrong-scheme"],
)
async def test_requests_without_a_valid_token_are_unauthorized(
    anon_client: httpx.AsyncClient,
    clips: dict[str, Path],
    transcriber: FakeTranscriber,
    authorization: str | bytes | None,
) -> None:
    headers = {"Authorization": authorization} if authorization is not None else {}

    response = await anon_client.post("/v1/transcribe", files=voice_note(clips), headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert transcriber.calls == []


async def test_a_token_signed_with_another_secret_is_rejected(
    anon_client: httpx.AsyncClient, clips: dict[str, Path]
) -> None:
    # What every install sees after TOKEN_SECRET is rotated: 401, then re-install.
    foreign = TokenSigner(b"another-secret-another-secret-12").issue()

    response = await anon_client.post(
        "/v1/transcribe", files=voice_note(clips), headers=bearer(foreign)
    )

    assert response.status_code == 401


async def test_the_daily_limit_answers_429_with_retry_after(
    app: FastAPI, anon_client: httpx.AsyncClient, clips: dict[str, Path], settings: Settings
) -> None:
    settings.rate_limit_per_day = 2
    token = app.state.token_signer.issue()

    statuses = []
    for _ in range(3):
        response = await anon_client.post(
            "/v1/transcribe", files=voice_note(clips), headers=bearer(token)
        )
        statuses.append(response.status_code)

    assert statuses == [200, 200, 429]
    assert response.json()["error"]["code"] == "rate_limited"
    assert 0 < int(response.headers["Retry-After"]) <= 24 * 3600
    # Another install still has its own quota.
    other = await anon_client.post(
        "/v1/transcribe", files=voice_note(clips), headers=bearer(app.state.token_signer.issue())
    )
    assert other.status_code == 200


async def test_failed_requests_do_not_use_the_quota(
    app: FastAPI,
    anon_client: httpx.AsyncClient,
    clips: dict[str, Path],
    settings: Settings,
    transcriber: FakeTranscriber,
) -> None:
    settings.rate_limit_per_day = 1
    headers = bearer(app.state.token_signer.issue())
    not_audio = {"audio": ("note.opus", b"this is not audio\n" * 200, "audio/ogg")}

    assert (
        await anon_client.post("/v1/transcribe", files=not_audio, headers=headers)
    ).status_code == 400
    transcriber.error = RuntimeError("model crashed")
    assert (
        await anon_client.post("/v1/transcribe", files=voice_note(clips), headers=headers)
    ).status_code == 500
    transcriber.error = None
    assert (
        await anon_client.post("/v1/transcribe", files=voice_note(clips), headers=headers)
    ).status_code == 200
    assert (
        await anon_client.post("/v1/transcribe", files=voice_note(clips), headers=headers)
    ).status_code == 429


async def test_tokens_never_reach_the_logs(
    anon_client: httpx.AsyncClient, clips: dict[str, Path], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        token = (await anon_client.post("/v1/install")).json()["token"]
        await anon_client.post("/v1/transcribe", files=voice_note(clips), headers=bearer(token))

    assert token not in caplog.text
    assert token.partition(".")[0] not in caplog.text


async def test_usage_store_resets_each_day() -> None:
    store = MemoryUsageStore()

    assert await store.reserve("2026-10-05", "tok", limit=1)
    assert not await store.reserve("2026-10-05", "tok", limit=1)
    assert await store.reserve("2026-10-06", "tok", limit=1)


async def test_usage_store_release_gives_one_back() -> None:
    store = MemoryUsageStore()
    await store.reserve("2026-10-05", "tok", limit=1)

    await store.release("2026-10-05", "tok")

    assert await store.reserve("2026-10-05", "tok", limit=1)
