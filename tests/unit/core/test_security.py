"""JWT ve bcrypt unit testleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from apps.api.core.config import Settings
from apps.api.core.exceptions import UnauthorizedException
from apps.api.core.security import (
    ALGORITHM,
    access_token_expires_in_seconds,
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    verify_password,
)
from packages.shared.enums import UserRole

TEST_SETTINGS = Settings(
    DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/ygip_test",
    JWT_SECRET_KEY="test-secret-key-with-enough-length-for-hs256",
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS=30,
    ENVIRONMENT="development",
)

USER_ID = str(uuid.uuid4())
EMAIL = "admin@example.com"


def test_access_token_round_trip() -> None:
    token = create_access_token(
        USER_ID,
        UserRole.ADMIN.value,
        EMAIL,
        settings=TEST_SETTINGS,
    )
    payload = decode_jwt(token, expected_type="access", settings=TEST_SETTINGS)
    assert payload["sub"] == USER_ID
    assert payload["role"] == UserRole.ADMIN.value
    assert payload["email"] == EMAIL
    assert payload["type"] == "access"


def test_refresh_token_round_trip() -> None:
    token = create_refresh_token(USER_ID, settings=TEST_SETTINGS)
    payload = decode_jwt(token, expected_type="refresh", settings=TEST_SETTINGS)
    assert payload["sub"] == USER_ID
    assert payload["type"] == "refresh"
    assert "jti" in payload
    assert "role" not in payload


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(
        USER_ID,
        UserRole.VIEWER.value,
        EMAIL,
        settings=TEST_SETTINGS,
    )
    tampered = f"{token[:-1]}X"
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_jwt(tampered, expected_type="access", settings=TEST_SETTINGS)
    assert exc_info.value.error_code == "AUTH_TOKEN_INVALID"


def test_decode_rejects_expired_access_token() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": USER_ID,
        "role": UserRole.ADMIN.value,
        "email": EMAIL,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "type": "access",
    }
    token = jwt.encode(payload, TEST_SETTINGS.JWT_SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_jwt(token, expected_type="access", settings=TEST_SETTINGS)
    assert exc_info.value.error_code == "AUTH_TOKEN_EXPIRED"


def test_decode_rejects_wrong_token_type() -> None:
    refresh_token = create_refresh_token(USER_ID, settings=TEST_SETTINGS)
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_jwt(refresh_token, expected_type="access", settings=TEST_SETTINGS)
    assert exc_info.value.error_code == "AUTH_TOKEN_INVALID"


def test_decode_expired_refresh_token_uses_refresh_error_code() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": USER_ID,
        "iat": now - timedelta(days=31),
        "exp": now - timedelta(days=1),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, TEST_SETTINGS.JWT_SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(UnauthorizedException) as exc_info:
        decode_jwt(token, expected_type="refresh", settings=TEST_SETTINGS)
    assert exc_info.value.error_code == "AUTH_INVALID_REFRESH_TOKEN"


def test_bcrypt_hash_and_verify() -> None:
    hashed = hash_password("Parola123")
    assert hashed != "Parola123"
    assert verify_password("Parola123", hashed) is True
    assert verify_password("WrongPass1", hashed) is False


def test_access_token_expires_in_seconds() -> None:
    assert access_token_expires_in_seconds(TEST_SETTINGS) == 3600
