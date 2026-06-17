"""AuthService unit testleri."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.config import Settings
from apps.api.core.exceptions import ForbiddenException, UnauthorizedException
from apps.api.core.security import create_refresh_token, hash_password, verify_password
from apps.api.services.auth_service import AuthService
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

TEST_SETTINGS = Settings(
    DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/ygip_test",
    JWT_SECRET_KEY="test-secret-key-with-enough-length-for-hs256",
    ENVIRONMENT="development",
)


def _make_user(
    *,
    email: str = "user@example.com",
    password: str = "ValidPass1",
    is_active: bool = True,
    role: UserRole = UserRole.VIEWER,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )


@pytest.fixture
def mock_user_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_email = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.update_last_login = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_service() -> MagicMock:
    svc = MagicMock()
    svc.log_event = AsyncMock()
    return svc


@pytest.fixture
def mock_settings_service() -> MagicMock:
    svc = MagicMock()
    svc.get_jwt_access_token_minutes = AsyncMock(return_value=60)
    svc.get_jwt_refresh_token_days = AsyncMock(return_value=30)
    return svc


@pytest.fixture
def auth_service(
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
    mock_settings_service: MagicMock,
) -> AuthService:
    return AuthService(
        users=mock_user_repo,
        audit_svc=mock_audit_service,
        settings=TEST_SETTINGS,
        settings_svc=mock_settings_service,
    )


@pytest.mark.asyncio
async def test_login_success_returns_tokens(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()
    mock_user_repo.get_by_email.return_value = user

    response = await auth_service.login(
        db,
        email=user.email,
        password="ValidPass1",
        client_ip="127.0.0.1",
    )

    assert response.access_token
    assert response.refresh_token
    assert response.user.email == user.email
    mock_user_repo.update_last_login.assert_awaited_once_with(db, user)
    mock_audit_service.log_event.assert_awaited_once()
    assert mock_audit_service.log_event.await_args.kwargs["event_type"] == "user.login"


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    mock_user_repo.get_by_email.return_value = None
    db.commit = AsyncMock()

    with pytest.raises(UnauthorizedException) as exc_info:
        await auth_service.login(
            db,
            email="unknown@example.com",
            password="ValidPass1",
            client_ip="127.0.0.1",
        )

    assert exc_info.value.error_code == "AUTH_INVALID_CREDENTIALS"
    mock_audit_service.log_event.assert_awaited_once()
    assert mock_audit_service.log_event.await_args.kwargs["event_type"] == "user.login_failed"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()
    mock_user_repo.get_by_email.return_value = user
    db.commit = AsyncMock()

    with pytest.raises(UnauthorizedException) as exc_info:
        await auth_service.login(
            db,
            email=user.email,
            password="WrongPass9",
            client_ip="127.0.0.1",
        )

    assert exc_info.value.error_code == "AUTH_INVALID_CREDENTIALS"
    assert not verify_password("WrongPass9", user.password_hash)


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(is_active=False)
    mock_user_repo.get_by_email.return_value = user
    db.commit = AsyncMock()

    with pytest.raises(ForbiddenException) as exc_info:
        await auth_service.login(
            db,
            email=user.email,
            password="ValidPass1",
            client_ip="127.0.0.1",
        )

    assert exc_info.value.error_code == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()
    refresh_token = create_refresh_token(str(user.id), settings=TEST_SETTINGS)
    mock_user_repo.get_by_id.return_value = user

    response = await auth_service.refresh(db, refresh_token=refresh_token)

    assert response.access_token
    assert response.expires_in > 0


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_user(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user_id = uuid.uuid4()
    refresh_token = create_refresh_token(str(user_id), settings=TEST_SETTINGS)
    mock_user_repo.get_by_id.return_value = None

    with pytest.raises(UnauthorizedException) as exc_info:
        await auth_service.refresh(db, refresh_token=refresh_token)

    assert exc_info.value.error_code == "AUTH_INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(
    auth_service: AuthService,
    mock_user_repo: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user(is_active=False)
    refresh_token = create_refresh_token(str(user.id), settings=TEST_SETTINGS)
    mock_user_repo.get_by_id.return_value = user

    with pytest.raises(ForbiddenException) as exc_info:
        await auth_service.refresh(db, refresh_token=refresh_token)

    assert exc_info.value.error_code == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_logout_writes_audit_event(
    auth_service: AuthService,
    mock_audit_service: MagicMock,
) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    response = await auth_service.logout(db, user=user)

    assert response.message == "Oturum sonlandırıldı."
    mock_audit_service.log_event.assert_awaited_once()
    assert mock_audit_service.log_event.await_args.kwargs["event_type"] == "user.logout"
