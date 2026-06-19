"""LLM API key yönetimi request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from packages.shared.enums import ApiProvider
from pydantic import BaseModel, ConfigDict, Field


class ApiKeyResponse(BaseModel):
    """API key DTO — plaintext key asla dönmez."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: ApiProvider
    key_alias: str
    is_active: bool
    priority_order: int
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    data: list[ApiKeyResponse]


class CreateApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ApiProvider
    key_alias: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=8, max_length=500)
    priority_order: int = Field(ge=1, le=1000)
    is_active: bool = True


class PatchApiKeyStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class DeleteApiKeyResponse(BaseModel):
    message: str


class RequestTypeStats(BaseModel):
    requests: int
    tokens: int


class UsageStatsRow(BaseModel):
    date: date
    provider: ApiProvider
    api_key_alias: str
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_latency_ms: int | None
    error_count: int
    by_request_type: dict[str, RequestTypeStats]


class ApiUsageStatsResponse(BaseModel):
    period: Literal["daily", "weekly", "monthly"]
    data: list[UsageStatsRow]
