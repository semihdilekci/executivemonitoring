"""Ortak API şemaları."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False


class PaginatedResponse[T](BaseModel):
    data: list[T]
    pagination: PaginationMeta
