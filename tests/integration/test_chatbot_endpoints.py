"""Chatbot endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from apps.api.core.config import Settings
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend
from apps.api.services.chatbot_service import chatbot_service
from httpx import ASGITransport, AsyncClient
from packages.shared.models.chat_history import ChatHistory
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.rag_models import RagResult, RagSource
from services.ai_engine.rag_pipeline import RAGPipeline
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    TEST_ENCRYPTION_KEY,
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


class _StubRagPipeline(RAGPipeline):
    def __init__(self) -> None:
        pass

    async def ask(self, _db: Any, question: str, **_kwargs: Any) -> RagResult:
        return RagResult(
            answer=f"Yanıt: {question}",
            sources=[
                RagSource(
                    chunk_id=uuid.uuid4(),
                    processed_item_id=uuid.uuid4(),
                    title="Örnek kaynak",
                    url="https://example.com/article",
                    score=0.88,
                )
            ],
            model="mock/groq-model",
            tokens_used=120,
        )


def _stub_rag_factory(_llm_client: LLMClient) -> RAGPipeline:
    return _StubRagPipeline()


@pytest.fixture(autouse=True)
def _patch_rag_pipeline() -> AsyncIterator[None]:
    original_factory = chatbot_service._rag_pipeline_factory
    chatbot_service._rag_pipeline_factory = _stub_rag_factory
    yield
    chatbot_service._rag_pipeline_factory = original_factory


@pytest.fixture
async def chat_api_client(database_url: str) -> AsyncIterator[AsyncClient]:
    """Düşük chat rate limit ile test client."""
    settings = Settings(
        DATABASE_URL=database_url,
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET_KEY="test-secret-key",
        CORS_ORIGINS=["http://localhost:3000"],
        ENVIRONMENT="development",
        ENCRYPTION_KEY=TEST_ENCRYPTION_KEY,
        RATE_LIMIT_CHATBOT=3,
    )
    backend = InMemoryRateLimiterBackend()
    app = create_app(settings=settings, rate_limiter_backend=backend)
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


async def _cleanup_chat_history(database_url: str, user_id: uuid.UUID) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(ChatHistory).where(ChatHistory.user_id == user_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_can_ask_chat(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.post(
        "/api/v1/chat",
        headers=auth_headers(token),
        json={"question": "FMCG trendleri neler?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Yanıt: FMCG trendleri neler?"
    assert body["model"] == "mock/groq-model"
    assert body["tokens_used"] == 120
    assert len(body["sources"]) == 1
    assert body["sources"][0]["title"] == "Örnek kaynak"

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ChatHistory).where(ChatHistory.user_id == viewer_test_user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].question == "FMCG trendleri neler?"
        assert rows[0].tokens_used == 120
    await engine.dispose()
    await _cleanup_chat_history(database_url, viewer_test_user.id)


@pytest.mark.asyncio
async def test_empty_question_returns_422(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.post(
        "/api/v1/chat",
        headers=auth_headers(token),
        json={"question": ""},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_viewer_cannot_list_chat_history(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get(
        "/api/v1/chat/history",
        headers=auth_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_lists_chat_history(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    history_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            ChatHistory(
                id=history_id,
                user_id=viewer_test_user.id,
                question="Soru?",
                answer="Cevap.",
                sources=[],
                tokens_used=50,
                model="mock/model",
                created_at=datetime(2026, 6, 16, 8, 30, tzinfo=UTC),
            )
        )
        await session.commit()

    admin_token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        "/api/v1/chat/history",
        headers=auth_headers(admin_token),
        params={"user_id": str(viewer_test_user.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["has_more"] is False
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(history_id)
    assert body["data"][0]["user_name"] == "Viewer Test User"

    async with session_factory() as session:
        await session.execute(delete(ChatHistory).where(ChatHistory.id == history_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_rate_limit_exceeded(
    chat_api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(chat_api_client, viewer_test_user)
    headers = auth_headers(token)

    for _ in range(3):
        ok_response = await chat_api_client.post(
            "/api/v1/chat",
            headers=headers,
            json={"question": "test sorusu"},
        )
        assert ok_response.status_code == 200

    limited = await chat_api_client.post(
        "/api/v1/chat",
        headers=headers,
        json={"question": "limit aşımı"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in limited.headers

    await _cleanup_chat_history(database_url, viewer_test_user.id)
