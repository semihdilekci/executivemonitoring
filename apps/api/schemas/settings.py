"""Sistem ayarları request/response şemaları."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    description: str | None = None
    updated_at: datetime
    warning: str | None = None


class SettingListResponse(BaseModel):
    data: list[SettingResponse]


class UpdateSettingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any = Field(..., description="JSONB ayar değeri (int, string vb.)")
