"""İçerik tablo modelleri ve enum unit testleri."""

import uuid

from packages.shared.enums import DigestStatus, DigestType
from packages.shared.models import (
    Base,
    ChatHistory,
    Digest,
    DigestSection,
    NotificationPreference,
    PromptTemplate,
)
from sqlalchemy.dialects.postgresql import JSONB


def test_digest_enums_values() -> None:
    assert DigestType.TURKISH_MEDIA_WEEKLY.value == "turkish_media_weekly"
    assert DigestType.FMCG_WEEKLY.value == "fmcg_weekly"
    assert DigestType.STRATEGY_WEEKLY.value == "strategy_weekly"
    assert DigestStatus.GENERATING.value == "generating"
    assert DigestStatus.READY.value == "ready"
    assert DigestStatus.FAILED.value == "failed"


def test_content_table_names() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert {
        "prompt_templates",
        "digests",
        "digest_sections",
        "chat_history",
        "notification_preferences",
    }.issubset(table_names)


def test_prompt_template_columns() -> None:
    columns = {column.name for column in PromptTemplate.__table__.columns}
    assert {
        "name",
        "digest_type",
        "section_key",
        "system_prompt",
        "user_prompt_template",
        "version",
        "updated_at",
    }.issubset(columns)


def test_prompt_template_name_unique() -> None:
    name_column = PromptTemplate.__table__.c.name
    assert name_column.unique is True


def test_digest_status_default_generating() -> None:
    status_column = Digest.__table__.c.status
    assert status_column.server_default is not None


def test_digest_period_columns_are_date() -> None:
    from sqlalchemy import Date

    assert isinstance(Digest.__table__.c.period_start.type, Date)
    assert isinstance(Digest.__table__.c.period_end.type, Date)


def test_digest_section_cascade_fk_to_digests() -> None:
    digest_fk = {
        fk.target_fullname
        for fk in DigestSection.__table__.foreign_keys
        if fk.parent.name == "digest_id"
    }
    assert "digests.id" in digest_fk


def test_digest_section_prompt_template_set_null() -> None:
    template_fk = next(
        fk for fk in DigestSection.__table__.foreign_keys if fk.parent.name == "prompt_template_id"
    )
    assert template_fk.ondelete == "SET NULL"


def test_digest_section_source_references_jsonb() -> None:
    column = DigestSection.__table__.c.source_references
    assert isinstance(column.type, JSONB)
    assert column.server_default is not None


def test_chat_history_sources_jsonb_default() -> None:
    column = ChatHistory.__table__.c.sources
    assert isinstance(column.type, JSONB)
    assert column.server_default is not None


def test_chat_history_fk_to_users() -> None:
    fks = {fk.target_fullname for fk in ChatHistory.__table__.foreign_keys}
    assert "users.id" in fks


def test_notification_preference_user_id_unique() -> None:
    user_id_column = NotificationPreference.__table__.c.user_id
    assert user_id_column.unique is True


def test_notification_preference_no_created_at() -> None:
    columns = {column.name for column in NotificationPreference.__table__.columns}
    assert "created_at" not in columns
    assert "updated_at" in columns


def test_digest_type_enum_on_prompt_template() -> None:
    column = PromptTemplate.__table__.c.digest_type
    assert column.type.name == "digest_type_enum"  # type: ignore[attr-defined]


def test_content_models_uuid_primary_keys() -> None:
    for model in (PromptTemplate, Digest, DigestSection, ChatHistory, NotificationPreference):
        assert model.__table__.c.id.type.python_type is uuid.UUID
