"""AuditService unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.services.audit_service import AuditService
from packages.shared.enums import UserRole
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_audit_repo() -> MagicMock:
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def audit_service(mock_audit_repo: MagicMock) -> AuditService:
    return AuditService(audits=mock_audit_repo)


@pytest.mark.asyncio
async def test_log_event_delegates_to_repository(
    audit_service: AuditService,
    mock_audit_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()
    expected = AuditLog(
        event_type="user.created",
        actor_user_id=actor_id,
        target_type="user",
        target_id=target_id,
        payload={"email": "test@example.com"},
    )
    mock_audit_repo.create.return_value = expected

    result = await audit_service.log_event(
        db,
        event_type="user.created",
        actor_user_id=actor_id,
        target_type="user",
        target_id=target_id,
        payload={"email": "test@example.com"},
    )

    assert result is expected
    mock_audit_repo.create.assert_awaited_once_with(
        db,
        event_type="user.created",
        actor_user_id=actor_id,
        target_type="user",
        target_id=target_id,
        payload={"email": "test@example.com"},
    )


@pytest.mark.asyncio
async def test_log_event_strips_sensitive_payload_keys(
    audit_service: AuditService,
    mock_audit_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    mock_audit_repo.create.return_value = AuditLog(event_type="user.updated", payload={})

    await audit_service.log_event(
        db,
        event_type="user.updated",
        payload={
            "full_name": "Test User",
            "password": "SecretPass1",
            "access_token": "tok",
        },
    )

    call_kwargs = mock_audit_repo.create.await_args.kwargs
    assert call_kwargs["payload"] == {"full_name": "Test User"}


@pytest.mark.asyncio
async def test_list_audit_logs_maps_actor_name(
    audit_service: AuditService,
    mock_audit_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        password_hash="hash",
        full_name="Admin Kullanıcı",
        role=UserRole.ADMIN,
        is_active=True,
    )
    log = AuditLog(
        id=uuid.uuid4(),
        event_type="user.login",
        actor_user_id=actor.id,
        target_type="user",
        target_id=actor.id,
        payload={"ip": "127.0.0.1"},
        created_at=datetime.now(UTC),
    )
    log.actor = actor
    mock_audit_repo.list_paginated = AsyncMock(return_value=([log], None, False))

    response = await audit_service.list_audit_logs(db)

    assert len(response.data) == 1
    assert response.data[0].actor_name == "Admin Kullanıcı"
    assert response.data[0].event_type == "user.login"
    assert response.pagination.has_more is False
