"""LLM API key şifreleme — dev AES-256-GCM (`Docs/07` §8.3)."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apps.api.core.exceptions import ValidationException

_ENCRYPTION_VERSION_PREFIX = "v1:"
_NONCE_SIZE_BYTES = 12
_KEY_SIZE_BYTES = 32


def load_encryption_key(raw_key: str) -> bytes:
    """Base64 `ENCRYPTION_KEY` ortam değişkenini 32-byte AES anahtarına çevirir."""
    if not raw_key.strip():
        raise ValidationException(
            message="Şifreleme anahtarı yapılandırılmamış.",
            details={"field": "ENCRYPTION_KEY"},
        )
    try:
        key = base64.b64decode(raw_key, validate=True)
    except Exception as exc:
        raise ValidationException(
            message="Şifreleme anahtarı geçersiz.",
            details={"field": "ENCRYPTION_KEY"},
        ) from exc
    if len(key) != _KEY_SIZE_BYTES:
        raise ValidationException(
            message="Şifreleme anahtarı 32 byte olmalıdır.",
            details={"field": "ENCRYPTION_KEY", "expected_bytes": _KEY_SIZE_BYTES},
        )
    return key


def encrypt_api_key(plaintext: str, *, encryption_key: bytes) -> str:
    """Plaintext API key'i AES-256-GCM ile şifreler."""
    if not plaintext.strip():
        raise ValidationException(message="API key boş olamaz.", details={"field": "api_key"})

    aesgcm = AESGCM(encryption_key)
    nonce = os.urandom(_NONCE_SIZE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    encoded = base64.b64encode(nonce + ciphertext).decode("ascii")
    return f"{_ENCRYPTION_VERSION_PREFIX}{encoded}"


def decrypt_api_key(encrypted: str, *, encryption_key: bytes) -> str:
    """Şifreli API key'i çözer — yalnızca LLM client iç kullanımı."""
    if not encrypted.startswith(_ENCRYPTION_VERSION_PREFIX):
        msg = "Desteklenmeyen şifreleme formatı"
        raise ValueError(msg)

    try:
        raw = base64.b64decode(encrypted[len(_ENCRYPTION_VERSION_PREFIX) :], validate=True)
    except Exception as exc:
        raise ValueError("Şifreli API key decode edilemedi") from exc

    if len(raw) <= _NONCE_SIZE_BYTES:
        raise ValueError("Şifreli API key verisi geçersiz")

    nonce = raw[:_NONCE_SIZE_BYTES]
    ciphertext = raw[_NONCE_SIZE_BYTES:]
    aesgcm = AESGCM(encryption_key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
