"""Audit log request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.api.schemas.common import PaginatedResponse


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    actor_user_id: uuid.UUID | None = None
    actor_name: str | None = None
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    payload: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(PaginatedResponse[AuditLogResponse]):
    pass
