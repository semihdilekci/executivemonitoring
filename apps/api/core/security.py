"""JWT, bcrypt ve şifre politikası yardımcıları."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from apps.api.core.config import Settings, get_settings
from apps.api.core.exceptions import UnauthorizedException

ALGORITHM = "HS256"
_BCRYPT_ROUNDS = 12

_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128


def validate_password_strength(password: str) -> str:
    """Şifre politikasını doğrular; ihlalde ValueError fırlatır."""
    if len(password) < _PASSWORD_MIN_LENGTH:
        raise ValueError("Şifre en az 8 karakter olmalıdır.")
    if len(password) > _PASSWORD_MAX_LENGTH:
        raise ValueError("Şifre en fazla 128 karakter olabilir.")
    if not any(char.isupper() for char in password):
        raise ValueError("Şifre en az 1 büyük harf içermelidir.")
    if not any(char.isdigit() for char in password):
        raise ValueError("Şifre en az 1 rakam içermelidir.")
    return password


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _resolve_settings(settings: Settings | None) -> Settings:
    return settings or get_settings()


def _access_token_ttl(
    settings: Settings,
    *,
    expire_minutes: int | None = None,
) -> timedelta:
    minutes = (
        expire_minutes if expire_minutes is not None else settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return timedelta(minutes=minutes)


def _refresh_token_ttl(
    settings: Settings,
    *,
    expire_days: int | None = None,
) -> timedelta:
    days = expire_days if expire_days is not None else settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    return timedelta(days=days)


def access_token_expires_in_seconds(
    settings: Settings | None = None,
    *,
    expire_minutes: int | None = None,
) -> int:
    resolved = _resolve_settings(settings)
    return int(_access_token_ttl(resolved, expire_minutes=expire_minutes).total_seconds())


def create_access_token(
    user_id: str,
    role: str,
    email: str,
    *,
    settings: Settings | None = None,
    expire_minutes: int | None = None,
) -> str:
    resolved = _resolve_settings(settings)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + _access_token_ttl(resolved, expire_minutes=expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, resolved.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: str,
    *,
    settings: Settings | None = None,
    expire_days: int | None = None,
) -> str:
    resolved = _resolve_settings(settings)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + _refresh_token_ttl(resolved, expire_days=expire_days),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, resolved.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(
    token: str,
    *,
    expected_type: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved = _resolve_settings(settings)
    try:
        payload = jwt.decode(
            token,
            resolved.JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        code = "AUTH_TOKEN_EXPIRED" if expected_type == "access" else "AUTH_INVALID_REFRESH_TOKEN"
        raise UnauthorizedException(
            message="Token süresi dolmuş.",
            error_code=code,
        ) from exc
    except jwt.InvalidTokenError as exc:
        code = "AUTH_TOKEN_INVALID" if expected_type == "access" else "AUTH_INVALID_REFRESH_TOKEN"
        raise UnauthorizedException(
            message="Geçersiz token.",
            error_code=code,
        ) from exc

    token_type = payload.get("type")
    if expected_type is not None and token_type != expected_type:
        code = "AUTH_TOKEN_INVALID" if expected_type == "access" else "AUTH_INVALID_REFRESH_TOKEN"
        raise UnauthorizedException(
            message="Geçersiz token.",
            error_code=code,
        )

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        invalid_code = (
            "AUTH_TOKEN_INVALID" if expected_type == "access" else "AUTH_INVALID_REFRESH_TOKEN"
        )
        raise UnauthorizedException(
            message="Geçersiz token.",
            error_code=invalid_code,
        )

    return payload
