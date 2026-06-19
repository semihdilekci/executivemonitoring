"""Kaynak (source) yönetimi request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.common import PaginatedResponse


class SourceResponse(BaseModel):
    """Veri kaynağı DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_type: SourceType
    config: dict[str, Any]
    polling_interval_minutes: int
    status: SourceStatus
    last_fetched_at: datetime | None = None
    error_count: int
    category: SourceCategory
    target_phase: str
    created_at: datetime
    updated_at: datetime


class CreateSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    config: dict[str, Any]
    polling_interval_minutes: int = Field(ge=1, le=1440)
    category: SourceCategory
    target_phase: str = Field(min_length=1, max_length=10)


class UpdateSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: dict[str, Any] | None = None
    polling_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    category: SourceCategory | None = None
    target_phase: str | None = Field(default=None, min_length=1, max_length=10)


class PatchSourceStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SourceStatus


class DeleteSourceResponse(BaseModel):
    message: str
    deleted_raw_items_count: int


class SourceListResponse(PaginatedResponse[SourceResponse]):
    pass
