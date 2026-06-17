"""Kullanıcı yönetimi request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import datetime

from packages.shared.enums import UserRole
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from apps.api.schemas.common import PaginatedResponse


class UserResponse(BaseModel):
    """Kullanıcı DTO — password_hash asla dahil edilmez."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.VIEWER
    password: str = Field(min_length=1, max_length=128)


class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserListResponse(PaginatedResponse[UserResponse]):
    pass
