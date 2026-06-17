"""Kimlik doğrulama request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import datetime

from packages.shared.enums import UserRole
from pydantic import BaseModel, EmailStr, Field, field_validator

from apps.api.core.security import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserAuthResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(TokenResponse):
    refresh_token: str
    user: UserAuthResponse


class RefreshResponse(TokenResponse):
    pass


class LogoutResponse(BaseModel):
    message: str


class PasswordResetInitiateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    user_id: uuid.UUID


class PasswordResetInitiateResponse(BaseModel):
    message: str
    expires_at: datetime


class PasswordResetCompleteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=1, max_length=128)


class PasswordResetCompleteResponse(BaseModel):
    message: str


class PasswordValue(BaseModel):
    """Şifre politikası doğrulaması — user create/reset şemalarında kullanılır."""

    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        return validate_password_strength(value)
