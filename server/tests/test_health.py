from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings

pytestmark = pytest.mark.anyio


async def test_health_needs_no_token(anon_client: httpx.AsyncClient) -> None:
    response = await anon_client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "test-model", "commit": None}


async def test_health_names_the_deployed_commit(
    app: FastAPI, anon_client: httpx.AsyncClient, settings: Settings
) -> None:
    settings.git_commit = "889a06b0123456789abcdef"

    response = await anon_client.get("/v1/health")

    assert response.json()["commit"] == "889a06b"
