"""Şifre politikası unit testleri."""

from __future__ import annotations

import pytest
from apps.api.core.security import validate_password_strength
from apps.api.schemas.auth import PasswordValue
from pydantic import ValidationError


@pytest.mark.parametrize(
    "password",
    [
        "short1A",
        "alllowercase1",
        "ALLUPPERCASE",
        "NoDigitsHere",
        "",
    ],
)
def test_validate_password_strength_rejects_weak_passwords(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_strength(password)


def test_validate_password_strength_accepts_valid_password() -> None:
    assert validate_password_strength("Parola123") == "Parola123"


def test_password_value_schema_enforces_policy() -> None:
    with pytest.raises(ValidationError):
        PasswordValue(password="weak")


def test_password_value_schema_accepts_valid_password() -> None:
    model = PasswordValue(password="SecurePass1")
    assert model.password == "SecurePass1"
