"""UserService unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.exceptions import ConflictException
from apps.api.schemas.user import CreateUserRequest, UpdateUserRequest
from apps.api.services.user_service import UserService
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


def _make_user(*, role: UserRole = UserRole.VIEWER, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        password_hash="hash",
        full_name="Test User",
        role=role,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_email = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.list_paginated = AsyncMock()
    return repo


@pytest.fixture
def mock_notification_repo() -> MagicMock:
    repo = MagicMock()
    repo.create_default = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_service() -> MagicMock:
    svc = MagicMock()
    svc.log_event = AsyncMock()
    return svc


@pytest.fixture
def user_service(
    mock_user_repo: MagicMock,
    mock_notification_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> UserService:
    return UserService(
        users=mock_user_repo,
        notification_preferences=mock_notification_repo,
        audit_svc=mock_audit_service,
    )


@pytest.mark.asyncio
async def test_create_user_raises_conflict_on_duplicate_email(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    existing = _make_user()
    mock_user_repo.get_by_email.return_value = existing

    body = CreateUserRequest(
        email=existing.email,
        password="ValidPass1",
        full_name="Duplicate",
        role=UserRole.VIEWER,
    )

    with pytest.raises(ConflictException) as exc_info:
        await user_service.create_user(db, actor=actor, body=body)

    assert exc_info.value.error_code == "USER_EMAIL_EXISTS"
    mock_user_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    from apps.api.core.exceptions import PasswordPolicyViolationException

    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    mock_user_repo.get_by_email.return_value = None

    body = CreateUserRequest(
        email="new@example.com",
        password="weak",
        full_name="New User",
        role=UserRole.VIEWER,
    )

    with pytest.raises(PasswordPolicyViolationException):
        await user_service.create_user(db, actor=actor, body=body)


@pytest.mark.asyncio
async def test_create_user_success_writes_audit(
    user_service: UserService,
    mock_user_repo: MagicMock,
    mock_notification_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    created = _make_user()
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.create.return_value = created

    body = CreateUserRequest(
        email="new@example.com",
        password="ValidPass1",
        full_name="New User",
        role=UserRole.VIEWER,
    )

    response = await user_service.create_user(db, actor=actor, body=body)

    assert response.email == created.email
    mock_notification_repo.create_default.assert_awaited_once()
    mock_audit_service.log_event.assert_awaited_once()
    assert mock_audit_service.log_event.await_args.kwargs["event_type"] == "user.created"


@pytest.mark.asyncio
async def test_deactivate_user_writes_audit(
    user_service: UserService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    user = _make_user(is_active=True)
    deactivated = _make_user(is_active=False)
    mock_user_repo.get_by_id.return_value = user
    mock_user_repo.update.return_value = deactivated

    await user_service.update_user(
        db,
        actor=actor,
        user_id=user.id,
        body=UpdateUserRequest(is_active=False),
    )

    event_types = [
        call.kwargs["event_type"] for call in mock_audit_service.log_event.await_args_list
    ]
    assert "user.deactivated" in event_types
    assert "user.updated" in event_types


@pytest.mark.asyncio
async def test_list_users_returns_pagination_meta(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    users = [_make_user(), _make_user()]
    next_cursor = str(uuid.uuid4())
    mock_user_repo.list_paginated.return_value = (users, next_cursor, True)

    response = await user_service.list_users(db, limit=20)

    assert len(response.data) == 2
    assert response.pagination.next_cursor == next_cursor
    assert response.pagination.has_more is True
    mock_user_repo.list_paginated.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_users_rejects_invalid_cursor(
    user_service: UserService,
) -> None:
    from apps.api.core.exceptions import NotFoundException

    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundException):
        await user_service.list_users(db, cursor="not-a-uuid")


@pytest.mark.asyncio
async def test_get_user_returns_user(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()
    mock_user_repo.get_by_id.return_value = user

    response = await user_service.get_user(db, user.id)

    assert response.email == user.email


@pytest.mark.asyncio
async def test_get_user_raises_not_found(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    from apps.api.core.exceptions import NotFoundException

    db = AsyncMock(spec=AsyncSession)
    mock_user_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundException):
        await user_service.get_user(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_me_returns_current_user(user_service: UserService) -> None:
    user = _make_user()

    response = await user_service.get_me(user)

    assert response.email == user.email


@pytest.mark.asyncio
async def test_update_user_role_change_writes_audit(
    user_service: UserService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    user = _make_user(role=UserRole.VIEWER)
    updated = _make_user(role=UserRole.ADMIN)
    mock_user_repo.get_by_id.return_value = user
    mock_user_repo.update.return_value = updated

    await user_service.update_user(
        db,
        actor=actor,
        user_id=user.id,
        body=UpdateUserRequest(role=UserRole.ADMIN),
    )

    event_types = [
        call.kwargs["event_type"] for call in mock_audit_service.log_event.await_args_list
    ]
    assert "user.role_changed" in event_types


@pytest.mark.asyncio
async def test_update_user_noop_returns_existing(
    user_service: UserService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    user = _make_user()
    mock_user_repo.get_by_id.return_value = user

    response = await user_service.update_user(
        db,
        actor=actor,
        user_id=user.id,
        body=UpdateUserRequest(),
    )

    assert response.email == user.email
    mock_user_repo.update.assert_not_awaited()
    mock_audit_service.log_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_not_found_raises(
    user_service: UserService,
    mock_user_repo: MagicMock,
) -> None:
    from apps.api.core.exceptions import NotFoundException

    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    mock_user_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundException):
        await user_service.update_user(
            db,
            actor=actor,
            user_id=uuid.uuid4(),
            body=UpdateUserRequest(full_name="Updated Name"),
        )


@pytest.mark.asyncio
async def test_update_user_full_name_writes_audit(
    user_service: UserService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user(role=UserRole.ADMIN)
    user = _make_user()
    updated = _make_user()
    updated.id = user.id
    updated.full_name = "Updated Name"
    mock_user_repo.get_by_id.return_value = user
    mock_user_repo.update.return_value = updated

    await user_service.update_user(
        db,
        actor=actor,
        user_id=user.id,
        body=UpdateUserRequest(full_name="Updated Name"),
    )

    event_types = [
        call.kwargs["event_type"] for call in mock_audit_service.log_event.await_args_list
    ]
    assert "user.updated" in event_types
