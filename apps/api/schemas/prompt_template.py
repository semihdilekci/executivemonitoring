"""Prompt template request/response şemaları."""

from __future__ import annotations

import uuid
from datetime import datetime

from packages.shared.enums import ApiProvider, DigestType
from pydantic import BaseModel, ConfigDict, Field


class PromptTemplateResponse(BaseModel):
    """Prompt şablonu DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    digest_type: DigestType
    section_key: str
    system_prompt: str
    user_prompt_template: str
    model_preference: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class PromptTemplateListResponse(BaseModel):
    data: list[PromptTemplateResponse]


class CreatePromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    digest_type: DigestType
    section_key: str = Field(min_length=1, max_length=100)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    model_preference: ApiProvider | None = None
    is_active: bool = True


class UpdatePromptTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    digest_type: DigestType
    section_key: str = Field(min_length=1, max_length=100)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    model_preference: ApiProvider | None = None
    is_active: bool = True
