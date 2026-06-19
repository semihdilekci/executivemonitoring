"""API usage tracking integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.llm_client_factory import build_llm_client
from httpx import AsyncClient
from packages.shared.enums import ApiProvider, LlmRequestType
from packages.shared.models.api_key import ApiKey
from packages.shared.models.api_usage_log import ApiUsageLog
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.providers.base import LLMProvider
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)
from tests.integration.test_api_key_endpoints import _create_payload


class _MockLlmProvider(LLMProvider):
    def __init__(self, *, key_id: uuid.UUID) -> None:
        self._key_id = key_id

    @property
    def provider(self) -> ApiProvider:
        return ApiProvider.GROQ

    @property
    def key_id(self) -> uuid.UUID:
        return self._key_id

    @property
    def is_active(self) -> bool:
        return True

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return LLMResponse(
            text="mock yanıt",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            provider=ApiProvider.GROQ,
            model="groq/llama-3.1-70b-versatile",
            latency_ms=250,
            api_key_id=self._key_id,
        )


@pytest.fixture
async def usage_test_api_key_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> AsyncIterator[uuid.UUID]:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/api-keys",
        headers=auth_headers(token),
        json=_create_payload(alias="Usage Stats Key"),
    )
    assert response.status_code == 201
    key_id = uuid.UUID(response.json()["id"])

    yield key_id

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(ApiKey).where(ApiKey.id == key_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_mock_llm_call_persists_usage_and_stats_endpoint(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    usage_test_api_key_id: uuid.UUID,
    database_url: str,
    test_settings,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    api_key_service = ApiKeyService(settings=test_settings)
    usage_service = ApiUsageService()

    async with session_factory() as session:
        mock_provider = _MockLlmProvider(key_id=usage_test_api_key_id)
        client = await build_llm_client(
            session,
            api_key_service,
            usage_service,
            providers=[mock_provider],
        )
        await client.complete(
            "test sorusu",
            operation_type=LlmRequestType.CHATBOT,
        )
        await client.complete(
            "digest prompt",
            operation_type=LlmRequestType.DIGEST_GENERATION,
        )
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    stats_response = await api_client.get(
        "/api/v1/api-keys/usage-stats",
        headers=auth_headers(token),
        params={"period": "daily"},
    )
    assert stats_response.status_code == 200
    payload = stats_response.json()
    assert payload["period"] == "daily"
    assert len(payload["data"]) >= 1

    row = next(
        item for item in payload["data"] if item["api_key_alias"] == "Usage Stats Key"
    )
    assert row["provider"] == "groq"
    assert row["total_requests"] == 2
    assert row["total_prompt_tokens"] == 200
    assert row["total_completion_tokens"] == 100
    assert row["total_tokens"] == 300
    assert row["avg_latency_ms"] == 250
    assert row["error_count"] == 0
    assert row["by_request_type"]["chatbot"]["requests"] == 1
    assert row["by_request_type"]["chatbot"]["tokens"] == 150
    assert row["by_request_type"]["digest_generation"]["requests"] == 1
    assert row["by_request_type"]["digest_generation"]["tokens"] == 150

    await engine.dispose()


@pytest.mark.asyncio
async def test_usage_stats_filters_by_api_key_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    usage_test_api_key_id: uuid.UUID,
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    other_key_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            ApiUsageLog(
                api_key_id=usage_test_api_key_id,
                provider="groq",
                model="groq/llama-3.1-70b-versatile",
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                request_type="chatbot",
                http_status=200,
                latency_ms=100,
            )
        )
        other_key = ApiKey(
            id=other_key_id,
            provider=ApiProvider.GEMINI,
            key_alias="Other Key",
            encrypted_key="v1:other",
            priority_order=2,
            is_active=True,
        )
        session.add(other_key)
        session.add(
            ApiUsageLog(
                api_key_id=other_key_id,
                provider="gemini",
                model="gemini/gemini-1.5-flash",
                prompt_tokens=20,
                completion_tokens=10,
                total_tokens=30,
                request_type="chatbot",
                http_status=200,
                latency_ms=200,
            )
        )
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    stats_response = await api_client.get(
        "/api/v1/api-keys/usage-stats",
        headers=auth_headers(token),
        params={"api_key_id": str(usage_test_api_key_id)},
    )
    assert stats_response.status_code == 200
    data = stats_response.json()["data"]
    assert all(item["api_key_alias"] == "Usage Stats Key" for item in data)
    assert sum(item["total_requests"] for item in data) == 1

    async with session_factory() as session:
        await session.execute(delete(ApiUsageLog).where(ApiUsageLog.api_key_id == other_key_id))
        await session.execute(delete(ApiKey).where(ApiKey.id == other_key_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_forbidden_on_usage_stats(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get(
        "/api/v1/api-keys/usage-stats",
        headers=auth_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_usage_stats_respects_date_range(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    usage_test_api_key_id: uuid.UUID,
    database_url: str,
) -> None:
    today = datetime.now(tz=UTC).date()
    old_date = today - timedelta(days=60)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        log = ApiUsageLog(
            api_key_id=usage_test_api_key_id,
            provider="groq",
            model="groq/llama-3.1-70b-versatile",
            prompt_tokens=5,
            completion_tokens=5,
            total_tokens=10,
            request_type="chatbot",
            http_status=200,
            latency_ms=50,
        )
        session.add(log)
        await session.flush()
        log.created_at = datetime.combine(old_date, datetime.min.time(), tzinfo=UTC)
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    default_response = await api_client.get(
        "/api/v1/api-keys/usage-stats",
        headers=auth_headers(token),
    )
    assert default_response.status_code == 200
    aliases = {row["api_key_alias"] for row in default_response.json()["data"]}
    assert "Usage Stats Key" not in aliases

    filtered_response = await api_client.get(
        "/api/v1/api-keys/usage-stats",
        headers=auth_headers(token),
        params={
            "start_date": old_date.isoformat(),
            "end_date": old_date.isoformat(),
        },
    )
    assert filtered_response.status_code == 200
    filtered_aliases = {row["api_key_alias"] for row in filtered_response.json()["data"]}
    assert "Usage Stats Key" in filtered_aliases

    await engine.dispose()
