"""get_current_user ve require_admin dependency unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.config import Settings
from apps.api.core.deps import get_current_user, require_admin
from apps.api.core.exceptions import ForbiddenException, UnauthorizedException
from apps.api.core.security import create_access_token
from fastapi.security import HTTPAuthorizationCredentials
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

TEST_SETTINGS = Settings(
    DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/ygip_test",
    JWT_SECRET_KEY="test-secret-key-with-enough-length-for-hs256",
    ENVIRONMENT="development",
)


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.api.core.security.get_settings", lambda: TEST_SETTINGS)


def _make_user(*, is_active: bool = True, role: UserRole = UserRole.VIEWER) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        password_hash="hash",
        full_name="Test User",
        role=role,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


def _mock_db_with_user(user: User | None) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_current_user_raises_when_no_credentials() -> None:
    with pytest.raises(UnauthorizedException) as exc_info:
        await get_current_user(credentials=None, db=AsyncMock(spec=AsyncSession))

    assert exc_info.value.error_code == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_current_user_raises_on_invalid_token() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")

    with pytest.raises(UnauthorizedException) as exc_info:
        await get_current_user(credentials=credentials, db=AsyncMock(spec=AsyncSession))

    assert exc_info.value.error_code == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_get_current_user_raises_when_user_not_found() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(
        str(user_id),
        UserRole.VIEWER.value,
        "ghost@example.com",
        settings=TEST_SETTINGS,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    db = _mock_db_with_user(None)

    with pytest.raises(UnauthorizedException) as exc_info:
        await get_current_user(credentials=credentials, db=db)

    assert exc_info.value.error_code == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_get_current_user_raises_when_user_inactive() -> None:
    user = _make_user(is_active=False)
    token = create_access_token(
        str(user.id),
        user.role.value,
        user.email,
        settings=TEST_SETTINGS,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    db = _mock_db_with_user(user)

    with pytest.raises(ForbiddenException) as exc_info:
        await get_current_user(credentials=credentials, db=db)

    assert exc_info.value.error_code == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user() -> None:
    user = _make_user(role=UserRole.ADMIN)
    token = create_access_token(
        str(user.id),
        user.role.value,
        user.email,
        settings=TEST_SETTINGS,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    db = _mock_db_with_user(user)

    result = await get_current_user(credentials=credentials, db=db)

    assert result is user
    assert result.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_require_admin_raises_for_viewer() -> None:
    viewer = _make_user(role=UserRole.VIEWER)

    with pytest.raises(ForbiddenException) as exc_info:
        await require_admin(current_user=viewer)

    assert exc_info.value.error_code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_require_admin_passes_for_admin() -> None:
    admin = _make_user(role=UserRole.ADMIN)

    result = await require_admin(current_user=admin)

    assert result is admin


@pytest.mark.asyncio
async def test_require_role_factory_allows_matching_role() -> None:
    from apps.api.core.deps import require_role

    viewer = _make_user(role=UserRole.VIEWER)
    guard = require_role(UserRole.VIEWER)

    result = await guard(current_user=viewer)

    assert result is viewer


@pytest.mark.asyncio
async def test_require_role_factory_denies_wrong_role() -> None:
    from apps.api.core.deps import require_role

    viewer = _make_user(role=UserRole.VIEWER)
    guard = require_role(UserRole.ADMIN)

    with pytest.raises(ForbiddenException):
        await guard(current_user=viewer)
