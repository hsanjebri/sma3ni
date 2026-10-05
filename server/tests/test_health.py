from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.anyio


async def test_health_reports_the_model_version(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "test-model"}
