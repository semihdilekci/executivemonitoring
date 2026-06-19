"""API key encryption unit testleri."""

from __future__ import annotations

import base64

import pytest
from apps.api.core.encryption import decrypt_api_key, encrypt_api_key, load_encryption_key
from apps.api.core.exceptions import ValidationException

_TEST_KEY = b"t" * 32


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "gsk_super_secret_key_value_12345"
    encrypted = encrypt_api_key(plaintext, encryption_key=_TEST_KEY)
    decrypted = decrypt_api_key(encrypted, encryption_key=_TEST_KEY)
    assert decrypted == plaintext
    assert plaintext not in encrypted


def test_encrypted_values_differ_for_same_plaintext() -> None:
    plaintext = "gsk_super_secret_key_value_12345"
    first = encrypt_api_key(plaintext, encryption_key=_TEST_KEY)
    second = encrypt_api_key(plaintext, encryption_key=_TEST_KEY)
    assert first != second
    assert plaintext not in first
    assert plaintext not in second


def test_encrypt_rejects_empty_plaintext() -> None:
    with pytest.raises(ValidationException) as exc_info:
        encrypt_api_key("  ", encryption_key=_TEST_KEY)
    assert "API key boş" in exc_info.value.message


def test_load_encryption_key_rejects_empty_env() -> None:
    with pytest.raises(ValidationException) as exc_info:
        load_encryption_key("")
    assert "yapılandırılmamış" in exc_info.value.message


def test_load_encryption_key_rejects_invalid_length() -> None:
    short_key = base64.b64encode(b"short").decode()
    with pytest.raises(ValidationException) as exc_info:
        load_encryption_key(short_key)
    assert "32 byte" in exc_info.value.message


def test_decrypt_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Desteklenmeyen"):
        decrypt_api_key("legacy-ciphertext", encryption_key=_TEST_KEY)


def test_encrypt_decrypt_never_logs_plaintext_key(caplog: pytest.LogCaptureFixture) -> None:
    """Roadmap §4.2 — API key plaintext log'a düşmez."""
    import logging

    caplog.set_level(logging.DEBUG)
    plaintext = "gsk_super_secret_key_value_12345"
    encrypted = encrypt_api_key(plaintext, encryption_key=_TEST_KEY)
    decrypted = decrypt_api_key(encrypted, encryption_key=_TEST_KEY)

    assert decrypted == plaintext
    assert plaintext not in caplog.text
