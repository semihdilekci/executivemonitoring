"""Kaynak (source) yönetimi iş mantığı."""

from __future__ import annotations

import uuid
from typing import Any

from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import NotFoundException, ValidationException
from apps.api.repositories.source_repository import SourceRepository
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.source import (
    CreateSourceRequest,
    DeleteSourceResponse,
    PatchSourceStatusRequest,
    SourceListResponse,
    SourceResponse,
    UpdateSourceRequest,
)
from apps.api.services.audit_service import AuditService, audit_service

source_repository = SourceRepository()

_SOURCES_DEFAULT_LIMIT = 20
_SOURCES_MAX_LIMIT = 100

_INGEST_MODES = frozenset({"all", "filtered"})

_TYPE_REQUIRED_CONFIG_FIELDS: dict[SourceType, tuple[str, ...]] = {
    SourceType.RSS: ("feed_url",),
    SourceType.EMAIL: ("imap_host", "mailbox", "sender_allowlist"),
    SourceType.GOV: ("endpoint_url",),
    SourceType.REST_API: ("endpoint",),
    SourceType.WEBSOCKET: ("endpoint",),
}


def _to_source_response(source: Source) -> SourceResponse:
    return SourceResponse.model_validate(source)


def validate_source_config(source_type: SourceType, config: dict[str, Any]) -> None:
    """MVP-0 config doğrulaması (`Docs/02` §4.2, `Docs/04` §8.3)."""
    errors: list[str] = []

    ingest_mode = config.get("ingest_mode")
    if ingest_mode not in _INGEST_MODES:
        errors.append("config.ingest_mode zorunludur ve 'all' veya 'filtered' olmalıdır.")

    default_category = config.get("default_category")
    if not isinstance(default_category, str) or not default_category.strip():
        errors.append("config.default_category zorunludur.")

    for field in _TYPE_REQUIRED_CONFIG_FIELDS.get(source_type, ()):
        value = config.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"config.{field} zorunludur ({source_type.value}).")

    if source_type == SourceType.EMAIL:
        allowlist = config.get("sender_allowlist")
        if allowlist is not None and not isinstance(allowlist, list):
            errors.append("config.sender_allowlist liste olmalıdır.")

    if errors:
        raise ValidationException(
            message="Kaynak yapılandırması geçersiz.",
            details={"fields": errors},
        )


class SourceService:
    """Admin kaynak CRUD ve durum yönetimi."""

    def __init__(
        self,
        sources: SourceRepository | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._sources = sources or source_repository
        self._audit_service = audit_svc or audit_service

    async def list_sources(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _SOURCES_DEFAULT_LIMIT,
        source_type: SourceType | None = None,
        status: SourceStatus | None = None,
        category: SourceCategory | None = None,
    ) -> SourceListResponse:
        resolved_limit = min(max(limit, 1), _SOURCES_MAX_LIMIT)
        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError as exc:
                raise NotFoundException(message="Geçersiz pagination cursor.") from exc

        sources, next_cursor, has_more = await self._sources.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            source_type=source_type,
            status=status,
            category=category,
        )
        return SourceListResponse(
            data=[_to_source_response(source) for source in sources],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )

    async def get_source(self, db: AsyncSession, source_id: uuid.UUID) -> SourceResponse:
        source = await self._sources.get_by_id(db, source_id)
        if source is None:
            raise NotFoundException(message="Kaynak bulunamadı.")
        return _to_source_response(source)

    async def create_source(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: CreateSourceRequest,
    ) -> SourceResponse:
        validate_source_config(body.source_type, body.config)

        source = await self._sources.create(
            db,
            name=body.name,
            source_type=body.source_type,
            config=body.config,
            polling_interval_minutes=body.polling_interval_minutes,
            category=body.category,
            target_phase=body.target_phase,
        )
        await self._audit_service.log_event(
            db,
            event_type="source.created",
            actor_user_id=actor.id,
            target_type="source",
            target_id=source.id,
            payload={
                "name": source.name,
                "source_type": source.source_type.value,
                "category": source.category.value,
            },
        )
        return _to_source_response(source)

    async def update_source(
        self,
        db: AsyncSession,
        *,
        actor: User,
        source_id: uuid.UUID,
        body: UpdateSourceRequest,
    ) -> SourceResponse:
        source = await self._sources.get_by_id(db, source_id)
        if source is None:
            raise NotFoundException(message="Kaynak bulunamadı.")

        if (
            body.name is None
            and body.config is None
            and body.polling_interval_minutes is None
            and body.category is None
            and body.target_phase is None
        ):
            return _to_source_response(source)

        merged_config = source.config
        if body.config is not None:
            merged_config = {**source.config, **body.config}
            validate_source_config(source.source_type, merged_config)

        updated = await self._sources.update(
            db,
            source,
            name=body.name,
            config=merged_config if body.config is not None else None,
            polling_interval_minutes=body.polling_interval_minutes,
            category=body.category,
            target_phase=body.target_phase,
        )
        return _to_source_response(updated)

    async def delete_source(
        self,
        db: AsyncSession,
        *,
        actor: User,
        source_id: uuid.UUID,
    ) -> DeleteSourceResponse:
        source = await self._sources.get_by_id(db, source_id)
        if source is None:
            raise NotFoundException(message="Kaynak bulunamadı.")

        payload = {
            "name": source.name,
            "source_type": source.source_type.value,
        }
        deleted_raw_items_count = await self._sources.delete(db, source)
        await self._audit_service.log_event(
            db,
            event_type="source.deleted",
            actor_user_id=actor.id,
            target_type="source",
            target_id=source_id,
            payload=payload,
        )
        return DeleteSourceResponse(
            message="Kaynak ve ilişkili veriler silindi.",
            deleted_raw_items_count=deleted_raw_items_count,
        )

    async def patch_source_status(
        self,
        db: AsyncSession,
        *,
        actor: User,
        source_id: uuid.UUID,
        body: PatchSourceStatusRequest,
    ) -> SourceResponse:
        source = await self._sources.get_by_id(db, source_id)
        if source is None:
            raise NotFoundException(message="Kaynak bulunamadı.")

        previous_status = source.status
        if previous_status == body.status:
            return _to_source_response(source)

        reset_error_count = (
            previous_status == SourceStatus.ERROR and body.status == SourceStatus.ACTIVE
        )
        updated = await self._sources.update_status(
            db,
            source,
            status=body.status,
            reset_error_count=reset_error_count,
        )
        await self._audit_service.log_event(
            db,
            event_type="source.status_changed",
            actor_user_id=actor.id,
            target_type="source",
            target_id=updated.id,
            payload={
                "from": previous_status.value,
                "to": updated.status.value,
            },
        )
        return _to_source_response(updated)


source_service = SourceService()
