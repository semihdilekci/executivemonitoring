"""Chatbot iş mantığı — RAG pipeline + chat_history persist."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

from packages.shared.models.chat_history import ChatHistory
from packages.shared.models.user import User
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.rag_models import RagResult, RagSource
from services.ai_engine.rag_pipeline import RAGPipeline
from services.processor.embedding_service import EmbeddingService
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import NotFoundException
from apps.api.repositories.chat_repository import ChatRepository, chat_repository
from apps.api.schemas.chatbot import (
    AskResponse,
    ChatHistoryItemResponse,
    ChatHistoryListResponse,
    ChatSourceResponse,
)
from apps.api.schemas.common import PaginationMeta

_HISTORY_DEFAULT_LIMIT = 20
_HISTORY_MAX_LIMIT = 50

RagPipelineFactory = Callable[[LLMClient], RAGPipeline]


def _default_rag_pipeline_factory(llm_client: LLMClient) -> RAGPipeline:
    return RAGPipeline(
        embedding_service=EmbeddingService(),
        llm_client=llm_client,
    )


def _source_to_dict(source: RagSource) -> dict[str, object]:
    return {
        "chunk_id": str(source.chunk_id),
        "processed_item_id": str(source.processed_item_id),
        "title": source.title,
        "url": source.url,
        "score": source.score,
    }


def _parse_sources(raw: Any) -> list[ChatSourceResponse]:
    if not isinstance(raw, list):
        return []
    parsed: list[ChatSourceResponse] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        chunk_id = item.get("chunk_id")
        processed_item_id = item.get("processed_item_id")
        title = item.get("title")
        if not chunk_id or not processed_item_id or not title:
            continue
        try:
            parsed.append(
                ChatSourceResponse(
                    chunk_id=uuid.UUID(str(chunk_id)),
                    processed_item_id=uuid.UUID(str(processed_item_id)),
                    title=str(title),
                    url=item.get("url") if isinstance(item.get("url"), str) else None,
                    score=float(item.get("score", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return parsed


def _to_ask_response(result: RagResult) -> AskResponse:
    return AskResponse(
        answer=result.answer,
        sources=[
            ChatSourceResponse(
                chunk_id=source.chunk_id,
                processed_item_id=source.processed_item_id,
                title=source.title,
                url=source.url,
                score=source.score,
            )
            for source in result.sources
        ],
        model=result.model,
        tokens_used=result.tokens_used,
    )


def _to_history_item(row: ChatHistory) -> ChatHistoryItemResponse:
    user_name = row.user.full_name if row.user is not None else "Bilinmeyen"
    return ChatHistoryItemResponse(
        id=row.id,
        user_id=row.user_id,
        user_name=user_name,
        question=row.question,
        answer=row.answer,
        sources=_parse_sources(row.sources),
        tokens_used=row.tokens_used,
        model=row.model,
        created_at=row.created_at,
    )


class ChatbotService:
    """RAG chatbot soru/yanıt ve admin geçmiş listesi."""

    def __init__(
        self,
        chats: ChatRepository | None = None,
        rag_pipeline_factory: RagPipelineFactory | None = None,
    ) -> None:
        self._chats = chats or chat_repository
        self._rag_pipeline_factory = rag_pipeline_factory or _default_rag_pipeline_factory

    async def ask(
        self,
        db: AsyncSession,
        *,
        user: User,
        question: str,
        llm_client: LLMClient,
    ) -> AskResponse:
        pipeline = self._rag_pipeline_factory(llm_client)
        rag_result = await pipeline.ask(db, question)

        await self._chats.create(
            db,
            user_id=user.id,
            question=question,
            answer=rag_result.answer,
            sources=[_source_to_dict(source) for source in rag_result.sources],
            tokens_used=rag_result.tokens_used,
            model=rag_result.model or "unknown",
        )
        return _to_ask_response(rag_result)

    async def list_history(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _HISTORY_DEFAULT_LIMIT,
        user_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ChatHistoryListResponse:
        resolved_limit = min(max(limit, 1), _HISTORY_MAX_LIMIT)

        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError as exc:
                raise NotFoundException(message="Geçersiz pagination cursor.") from exc

        rows, next_cursor, has_more = await self._chats.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        return ChatHistoryListResponse(
            data=[_to_history_item(row) for row in rows],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )


chatbot_service = ChatbotService()
