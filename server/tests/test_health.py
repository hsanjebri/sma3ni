from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.anyio


async def test_health_needs_no_token(anon_client: httpx.AsyncClient) -> None:
    response = await anon_client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "test-model"}
