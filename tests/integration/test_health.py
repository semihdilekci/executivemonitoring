"""Health ve ready endpoint integration testleri."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(api_client: AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
    body_text = response.text.lower()
    assert "secret" not in body_text
    assert "password" not in body_text


@pytest.mark.asyncio
async def test_health_preserves_request_id(api_client: AsyncClient) -> None:
    custom_id = "test-request-id-12345"
    response = await api_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_ready_returns_ready_when_db_available(api_client: AsyncClient) -> None:
    response = await api_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
