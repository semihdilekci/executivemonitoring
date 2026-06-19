"""LLM HTTP exception handler unit testleri."""

from __future__ import annotations

import pytest
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from services.ai_engine.llm_client import LLMClient


@pytest.mark.asyncio
async def test_no_active_llm_provider_returns_502_with_error_code() -> None:
    """Aktif provider yokken API `502` + `NO_ACTIVE_LLM_PROVIDER` döner."""
    backend = InMemoryRateLimiterBackend()
    app = create_app(rate_limiter_backend=backend)

    probe_router = APIRouter()

    @probe_router.get("/probe/no-llm")
    async def probe_no_llm() -> dict[str, bool]:
        await LLMClient().complete("ping")
        return {"ok": True}

    app.include_router(probe_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe/no-llm")

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "NO_ACTIVE_LLM_PROVIDER"
