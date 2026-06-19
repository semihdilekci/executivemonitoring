"""Chatbot HTTP endpoint'leri — `Docs/03` §8."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from packages.shared.models.user import User
from services.ai_engine.llm_client import LLMClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import (
    enforce_chat_rate_limit,
    get_db,
    get_llm_client,
    require_admin,
)
from apps.api.schemas.chatbot import AskRequest, AskResponse, ChatHistoryListResponse
from apps.api.services.chatbot_service import chatbot_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=AskResponse)
async def ask_chat(
    body: AskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(enforce_chat_rate_limit)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> AskResponse:
    return await chatbot_service.ask(
        db,
        user=user,
        question=body.question,
        llm_client=llm_client,
    )


@router.get("/history", response_model=ChatHistoryListResponse)
async def list_chat_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    user_id: Annotated[UUID | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> ChatHistoryListResponse:
    return await chatbot_service.list_history(
        db,
        cursor=cursor,
        limit=limit,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
