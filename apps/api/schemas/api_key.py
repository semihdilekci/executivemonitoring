"""LLM API key yönetimi request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from packages.shared.enums import ApiProvider
from packages.shared.llm_models import is_valid_model, models_for
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiKeyResponse(BaseModel):
    """API key DTO — plaintext key asla dönmez."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: ApiProvider
    key_alias: str
    model: str | None
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
    model: str = Field(min_length=1, max_length=100)
    priority_order: int = Field(ge=1, le=1000)
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_model_for_provider(self) -> CreateApiKeyRequest:
        if not is_valid_model(self.provider, self.model):
            allowed = ", ".join(models_for(self.provider))
            msg = f"{self.provider.value} için geçersiz model. Geçerli: {allowed}"
            raise ValueError(msg)
        return self


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
