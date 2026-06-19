"""SourceService unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.exceptions import ValidationException
from apps.api.schemas.source import PatchSourceStatusRequest
from apps.api.services.source_service import SourceService, validate_source_config
from packages.shared.enums import SourceCategory, SourceStatus, SourceType, UserRole
from packages.shared.models.source import Source
from packages.shared.models.user import User


def _rss_source() -> Source:
    now = datetime.now(UTC)
    return Source(
        id=uuid.uuid4(),
        name="RSS",
        source_type=SourceType.RSS,
        config={
            "feed_url": "https://example.com/feed.xml",
            "ingest_mode": "filtered",
            "default_category": "turkish_media",
        },
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.TURKISH_MEDIA,
        target_phase="mvp-0",
        created_at=now,
        updated_at=now,
    )


def test_validate_source_config_accepts_valid_rss() -> None:
    validate_source_config(
        SourceType.RSS,
        {
            "feed_url": "https://example.com/feed.xml",
            "ingest_mode": "all",
            "default_category": "fmcg",
        },
    )


def test_validate_source_config_rejects_missing_ingest_mode() -> None:
    with pytest.raises(ValidationException) as exc_info:
        validate_source_config(
            SourceType.RSS,
            {"feed_url": "https://example.com/feed.xml", "default_category": "fmcg"},
        )
    assert exc_info.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_source_status_resets_error_count_from_error() -> None:
    source = _rss_source()
    source.status = SourceStatus.ERROR
    source.error_count = 3

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=source)

    async def _update_status(
        _db: object,
        src: Source,
        *,
        status: SourceStatus,
        reset_error_count: bool = False,
    ) -> Source:
        src.status = status
        if reset_error_count:
            src.error_count = 0
        return src

    repo.update_status = AsyncMock(side_effect=_update_status)
    audit = MagicMock()
    audit.log_event = AsyncMock()

    service = SourceService(sources=repo, audit_svc=audit)
    actor = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash="hash",
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    db = AsyncMock()
    result = await service.patch_source_status(
        db,
        actor=actor,
        source_id=source.id,
        body=PatchSourceStatusRequest(status=SourceStatus.ACTIVE),
    )

    repo.update_status.assert_awaited_once_with(
        db,
        source,
        status=SourceStatus.ACTIVE,
        reset_error_count=True,
    )
    audit.log_event.assert_awaited_once()
    assert result.status == SourceStatus.ACTIVE
