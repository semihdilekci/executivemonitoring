"""Chatbot request/response şemaları — `Docs/03` §8."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.common import PaginatedResponse


class AskRequest(BaseModel):
    """POST /api/v1/chat body."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


class ChatSourceResponse(BaseModel):
    """RAG kaynak referansı."""

    chunk_id: uuid.UUID
    processed_item_id: uuid.UUID
    title: str
    url: str | None = None
    score: float


class AskResponse(BaseModel):
    """Chatbot yanıtı."""

    answer: str
    sources: list[ChatSourceResponse]
    model: str
    tokens_used: int


class ChatHistoryItemResponse(BaseModel):
    """Admin chat geçmişi satırı."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    question: str
    answer: str
    sources: list[ChatSourceResponse]
    tokens_used: int
    model: str
    created_at: datetime


class ChatHistoryListResponse(PaginatedResponse[ChatHistoryItemResponse]):
    pass
