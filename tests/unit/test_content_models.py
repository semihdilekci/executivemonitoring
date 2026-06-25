"""İçerik tablo modelleri ve enum unit testleri (Faz 6.5 — ADR-0003).

`prompt_templates`/`DigestType` kaldırıldı; serbest bülten modeli
(`newsletter_templates` + `newsletter_sections`) + `digests.newsletter_slug`.
"""

import uuid

from packages.shared.enums import DigestStatus
from packages.shared.models import (
    Base,
    ChatHistory,
    Digest,
    DigestSection,
    NewsletterSection,
    NewsletterTemplate,
    NotificationPreference,
)
from sqlalchemy.dialects.postgresql import JSONB


def test_digest_status_enum_values() -> None:
    assert DigestStatus.GENERATING.value == "generating"
    assert DigestStatus.READY.value == "ready"
    assert DigestStatus.FAILED.value == "failed"


def test_content_table_names() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert {
        "newsletter_templates",
        "newsletter_sections",
        "digests",
        "digest_sections",
        "chat_history",
        "notification_preferences",
    }.issubset(table_names)


def test_newsletter_template_columns() -> None:
    columns = {column.name for column in NewsletterTemplate.__table__.columns}
    assert {
        "slug",
        "name",
        "description",
        "date_range_days",
        "summary_system_prompt",
        "summary_user_prompt",
        "min_content_score",
        "model_preference",
        "is_active",
        "updated_at",
    }.issubset(columns)


def test_newsletter_section_columns() -> None:
    columns = {column.name for column in NewsletterSection.__table__.columns}
    assert {
        "newsletter_template_id",
        "name",
        "sort_order",
        "section_system_prompt",
        "section_user_prompt",
        "impact_prompt",
        "is_active",
    }.issubset(columns)


def test_newsletter_section_cascade_fk_to_template() -> None:
    template_fk = next(
        fk
        for fk in NewsletterSection.__table__.foreign_keys
        if fk.parent.name == "newsletter_template_id"
    )
    assert template_fk.target_fullname == "newsletter_templates.id"
    assert template_fk.ondelete == "CASCADE"


def test_digest_has_newsletter_slug_column() -> None:
    columns = {column.name for column in Digest.__table__.columns}
    assert {"newsletter_slug", "newsletter_template_id", "summary"}.issubset(columns)


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


def test_digest_section_newsletter_section_set_null() -> None:
    section_fk = next(
        fk
        for fk in DigestSection.__table__.foreign_keys
        if fk.parent.name == "newsletter_section_id"
    )
    assert section_fk.ondelete == "SET NULL"


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


def test_content_models_uuid_primary_keys() -> None:
    for model in (
        NewsletterTemplate,
        NewsletterSection,
        Digest,
        DigestSection,
        ChatHistory,
        NotificationPreference,
    ):
        assert model.__table__.c.id.type.python_type is uuid.UUID
