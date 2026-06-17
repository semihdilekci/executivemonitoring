"""PasswordResetService unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.exceptions import (
    PasswordPolicyViolationException,
    UnauthorizedException,
)
from apps.api.core.security import hash_password
from apps.api.services.email_service import CapturingEmailService
from apps.api.services.password_reset_service import PasswordResetService
from packages.shared.enums import UserRole
from packages.shared.models.password_reset_token import PasswordResetToken
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_reset_repo() -> MagicMock:
    repo = MagicMock()
    repo.invalidate_active_for_user = AsyncMock()
    repo.create = AsyncMock()
    repo.find_valid_by_raw_token = AsyncMock()
    repo.mark_used = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.update_password_hash = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_service() -> MagicMock:
    svc = MagicMock()
    svc.log_event = AsyncMock()
    return svc


@pytest.fixture
def capturing_mailer() -> CapturingEmailService:
    return CapturingEmailService()


@pytest.fixture
def password_reset_service(
    mock_reset_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
    capturing_mailer: CapturingEmailService,
) -> PasswordResetService:
    return PasswordResetService(
        resets=mock_reset_repo,
        users=mock_user_repo,
        audit_svc=mock_audit_service,
        mailer=capturing_mailer,
    )


@pytest.mark.asyncio
async def test_initiate_creates_token_and_sends_email(
    password_reset_service: PasswordResetService,
    mock_reset_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
    capturing_mailer: CapturingEmailService,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    actor_id = uuid.uuid4()
    user_id = uuid.uuid4()
    actor = User(
        id=actor_id,
        email="admin@example.com",
        password_hash="hash",
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    target = User(
        id=user_id,
        email="user@example.com",
        password_hash="hash",
        full_name="User",
        role=UserRole.VIEWER,
        is_active=True,
    )
    mock_user_repo.get_by_id.return_value = target
    mock_reset_repo.create.return_value = PasswordResetToken(
        user_id=user_id,
        token_hash="stored",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )

    response = await password_reset_service.initiate(db, actor=actor, user_id=user_id)

    assert "e-posta" in response.message
    mock_reset_repo.invalidate_active_for_user.assert_awaited_once_with(db, user_id)
    mock_reset_repo.create.assert_awaited_once()
    create_kwargs = mock_reset_repo.create.await_args.kwargs
    assert create_kwargs["user_id"] == user_id
    assert create_kwargs["token_hash"]
    assert capturing_mailer.last_email == "user@example.com"
    assert capturing_mailer.last_raw_token
    mock_audit_service.log_event.assert_awaited_once()
    assert (
        mock_audit_service.log_event.await_args.kwargs["event_type"]
        == "password.reset_initiated"
    )


@pytest.mark.asyncio
async def test_complete_rejects_invalid_token(
    password_reset_service: PasswordResetService,
    mock_reset_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    mock_reset_repo.find_valid_by_raw_token.return_value = None

    with pytest.raises(UnauthorizedException) as exc_info:
        await password_reset_service.complete(
            db,
            raw_token="invalid-token",
            new_password="NewPass1",
        )

    assert exc_info.value.error_code == "AUTH_INVALID_RESET_TOKEN"


@pytest.mark.asyncio
async def test_complete_rejects_weak_password(
    password_reset_service: PasswordResetService,
    mock_reset_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    mock_reset_repo.find_valid_by_raw_token.return_value = PasswordResetToken(
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    with pytest.raises(PasswordPolicyViolationException):
        await password_reset_service.complete(
            db,
            raw_token="some-token",
            new_password="weak",
        )


@pytest.mark.asyncio
async def test_complete_updates_password_and_marks_token_used(
    password_reset_service: PasswordResetService,
    mock_reset_repo: MagicMock,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user_id = uuid.uuid4()
    raw_token = "valid-reset-token-value"
    reset_row = PasswordResetToken(
        user_id=user_id,
        token_hash=hash_password(raw_token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    user = User(
        id=user_id,
        email="user@example.com",
        password_hash="old-hash",
        full_name="User",
        role=UserRole.VIEWER,
        is_active=True,
    )
    mock_reset_repo.find_valid_by_raw_token.return_value = reset_row
    mock_user_repo.get_by_id.return_value = user

    response = await password_reset_service.complete(
        db,
        raw_token=raw_token,
        new_password="NewPass9",
    )

    assert response.message == "Şifre başarıyla güncellendi."
    mock_user_repo.update_password_hash.assert_awaited_once()
    mock_reset_repo.mark_used.assert_awaited_once_with(db, reset_row)
    assert (
        mock_audit_service.log_event.await_args.kwargs["event_type"]
        == "password.reset_completed"
    )
