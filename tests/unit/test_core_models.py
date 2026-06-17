"""Core tablo modelleri ve enum unit testleri."""

import uuid

from packages.shared.enums import UserRole
from packages.shared.models import (
    AuditLog,
    Base,
    PasswordResetToken,
    SystemSetting,
    User,
)


def test_user_role_enum_values() -> None:
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.VIEWER.value == "viewer"
    assert len(UserRole) == 2


def test_core_models_importable() -> None:
    assert Base.metadata is not None


def test_core_table_names() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert {
        "users",
        "audit_logs",
        "password_reset_tokens",
        "system_settings",
    }.issubset(table_names)


def test_user_model_columns() -> None:
    columns = {column.name for column in User.__table__.columns}
    assert columns == {
        "id",
        "email",
        "password_hash",
        "full_name",
        "role",
        "is_active",
        "created_at",
        "last_login_at",
    }


def test_audit_log_model_columns() -> None:
    columns = {column.name for column in AuditLog.__table__.columns}
    assert "event_type" in columns
    assert "payload" in columns
    assert "actor_user_id" in columns


def test_password_reset_token_fk_to_users() -> None:
    fks = {fk.target_fullname for fk in PasswordResetToken.__table__.foreign_keys}
    assert "users.id" in fks


def test_system_setting_natural_key() -> None:
    pk_columns = [column.name for column in SystemSetting.__table__.primary_key.columns]
    assert pk_columns == ["key"]


def test_user_role_enum_mapped_on_user() -> None:
    role_column = User.__table__.c.role
    assert role_column.type.name == "user_role_enum"  # type: ignore[attr-defined]


def test_uuid_primary_key_defaults() -> None:
    id_column = User.__table__.c.id
    assert id_column.server_default is not None


def test_audit_log_payload_not_null() -> None:
    payload_column = AuditLog.__table__.c.payload
    assert payload_column.nullable is False


def test_audit_log_payload_jsonb_default() -> None:
    payload_column = AuditLog.__table__.c.payload
    assert payload_column.server_default is not None


def test_system_setting_value_is_jsonb() -> None:
    from sqlalchemy.dialects.postgresql import JSONB

    assert isinstance(SystemSetting.__table__.c.value.type, JSONB)


def test_password_reset_token_hash_unique() -> None:
    token_hash = PasswordResetToken.__table__.c.token_hash
    assert token_hash.unique is True


def test_system_setting_updated_by_nullable() -> None:
    updated_by = SystemSetting.__table__.c.updated_by
    assert updated_by.nullable is True


def test_user_id_type_is_uuid() -> None:
    assert isinstance(User.__table__.c.id.type.python_type, type)
    assert User.__table__.c.id.type.python_type is uuid.UUID
