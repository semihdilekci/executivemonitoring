"""Veri tablo modelleri ve enum unit testleri."""

import uuid

from packages.shared.enums import (
    ARTICLE_SCHEMA,
    PROCESSED_ITEM_SCHEMAS,
    RESERVED_SCHEMAS,
    ApiProvider,
    LlmRequestType,
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models import (
    EMBEDDING_DIMENSION,
    PROCESSED_ITEM_MODELS,
    ApiKey,
    ApiUsageLog,
    Base,
    ContentChunk,
    Digest,
    DigestSection,
    NewsletterSection,
    NewsletterTemplate,
    ProcessedItemTranslation,
    RawItem,
    Source,
)
from packages.shared.models.processed_item import ProcessedItem
from sqlalchemy.dialects.postgresql import JSONB


def test_data_enums_values() -> None:
    assert SourceType.REST_API.value == "rest_api"
    assert SourceStatus.ACTIVE.value == "active"
    assert SourceCategory.MACRO.value == "macro"
    assert RawItemStatus.PENDING.value == "pending"
    assert ApiProvider.GROQ.value == "groq"


def test_data_table_names() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected_public = {
        "sources",
        "raw_items",
        "content_chunks",
        "api_keys",
        "api_usage_logs",
    }
    assert expected_public.issubset(table_names)
    for schema in PROCESSED_ITEM_SCHEMAS:
        assert f"{schema}.processed_items" in table_names


def test_processed_item_models_cover_all_schemas() -> None:
    assert set(PROCESSED_ITEM_MODELS) == set(PROCESSED_ITEM_SCHEMAS)
    for schema, model in PROCESSED_ITEM_MODELS.items():
        assert model.__table__.schema == schema
        assert issubclass(model, ProcessedItem)


def test_article_vs_reserved_schema_split() -> None:
    # Faz 6.4 (ADR-0002): yalnızca `news` aktif haber schema'sı; geri kalanlar rezerve.
    assert ARTICLE_SCHEMA == "news"
    assert ARTICLE_SCHEMA not in RESERVED_SCHEMAS
    assert set(RESERVED_SCHEMAS) == {"market", "geo", "transport", "fmcg"}
    expected_order = (ARTICLE_SCHEMA, *RESERVED_SCHEMAS)
    assert expected_order == PROCESSED_ITEM_SCHEMAS


def test_source_model_columns() -> None:
    columns = {column.name for column in Source.__table__.columns}
    assert {
        "name",
        "source_type",
        "config",
        "polling_interval_minutes",
        "status",
        "category",
        "target_phase",
        "updated_at",
    }.issubset(columns)


def test_raw_item_fk_to_sources() -> None:
    fks = {fk.target_fullname for fk in RawItem.__table__.foreign_keys}
    assert "sources.id" in fks


def test_raw_item_unique_content_hash_per_source() -> None:
    constraint_names = {uc.name for uc in RawItem.__table__.constraints if hasattr(uc, "name")}
    assert "uq_raw_items_source_id_content_hash" in constraint_names


def test_content_chunk_embedding_dimension() -> None:
    embedding_column = ContentChunk.__table__.c.embedding
    assert embedding_column.type.dim == EMBEDDING_DIMENSION  # type: ignore[attr-defined]


def test_content_chunk_fk_to_news_processed_items() -> None:
    # Faz 6.4 İter 6: konsolidasyon sonrası native FK → news.processed_items(id).
    fks = {fk.target_fullname for fk in ContentChunk.__table__.foreign_keys}
    assert "news.processed_items.id" in fks
    fk = next(iter(ContentChunk.__table__.foreign_keys))
    assert fk.ondelete == "CASCADE"
    assert fk.name == "fk_content_chunks_processed_item_id"


def test_api_key_provider_enum() -> None:
    provider_column = ApiKey.__table__.c.provider
    assert provider_column.type.name == "api_provider_enum"  # type: ignore[attr-defined]


def test_api_usage_log_fk_to_api_keys() -> None:
    fks = {fk.target_fullname for fk in ApiUsageLog.__table__.foreign_keys}
    assert "api_keys.id" in fks


def test_source_config_jsonb_default() -> None:
    config_column = Source.__table__.c.config
    assert isinstance(config_column.type, JSONB)
    assert config_column.server_default is not None


def test_processed_item_relevance_check_constraint() -> None:
    model = PROCESSED_ITEM_MODELS["news"]
    check_names = {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name and constraint.name.startswith("ck_")
    }
    assert "ck_news_processed_items_relevance_range" in check_names


def test_raw_item_id_type_is_uuid() -> None:
    assert RawItem.__table__.c.id.type.python_type is uuid.UUID


def test_prompt_templates_table_removed() -> None:
    # Faz 6.5 (ADR-0003): prompt_templates emekliye ayrıldı (migrate→drop).
    assert "prompt_templates" not in Base.metadata.tables


def test_newsletter_tables_registered() -> None:
    table_names = set(Base.metadata.tables.keys())
    assert {"newsletter_templates", "newsletter_sections"}.issubset(table_names)


def test_newsletter_template_constraints() -> None:
    constraint_names = {
        constraint.name
        for constraint in NewsletterTemplate.__table__.constraints
        if constraint.name
    }
    assert "uq_newsletter_templates_slug" in constraint_names
    assert "ck_newsletter_min_score" in constraint_names


def test_newsletter_section_fk_and_order_constraint() -> None:
    fks = {fk.target_fullname for fk in NewsletterSection.__table__.foreign_keys}
    assert "newsletter_templates.id" in fks
    fk = next(iter(NewsletterSection.__table__.foreign_keys))
    assert fk.ondelete == "CASCADE"
    constraint_names = {
        constraint.name
        for constraint in NewsletterSection.__table__.constraints
        if constraint.name
    }
    assert "uq_newsletter_sections_order" in constraint_names


def test_digest_uses_newsletter_slug_not_enum() -> None:
    columns = {column.name for column in Digest.__table__.columns}
    assert {"newsletter_slug", "newsletter_template_id", "summary"}.issubset(columns)
    assert "digest_type" not in columns
    fks = {fk.target_fullname for fk in Digest.__table__.foreign_keys}
    assert "newsletter_templates.id" in fks


def test_digest_section_provenance_is_newsletter_section() -> None:
    columns = {column.name for column in DigestSection.__table__.columns}
    assert "newsletter_section_id" in columns
    assert "prompt_template_id" not in columns
    fk = next(
        fk
        for fk in DigestSection.__table__.foreign_keys
        if fk.column.table.name == "newsletter_sections"
    )
    assert fk.ondelete == "SET NULL"


def test_article_translation_request_type_enum() -> None:
    # Faz 6.5: ingest-time çeviri operasyon tipi.
    assert LlmRequestType.ARTICLE_TRANSLATION.value == "article_translation"


def test_processed_item_translation_table_in_news_schema() -> None:
    table = ProcessedItemTranslation.__table__
    assert table.schema == "news"
    assert "news.processed_item_translations" in Base.metadata.tables


def test_processed_item_translation_fk_and_constraints() -> None:
    # Faz 6.5 (Docs/02 §4.4b): FK → news.processed_items CASCADE; (item, language) UNIQUE.
    fks = {fk.target_fullname for fk in ProcessedItemTranslation.__table__.foreign_keys}
    assert "news.processed_items.id" in fks
    fk = next(iter(ProcessedItemTranslation.__table__.foreign_keys))
    assert fk.ondelete == "CASCADE"
    constraint_names = {
        constraint.name
        for constraint in ProcessedItemTranslation.__table__.constraints
        if constraint.name
    }
    assert "uq_processed_item_translations_item_lang" in constraint_names


def test_news_processed_item_has_translations_relationship() -> None:
    news_model = PROCESSED_ITEM_MODELS["news"]
    assert "translations" in news_model.__mapper__.relationships


def test_api_key_request_type_scope_jsonb_default() -> None:
    # Faz 6.5 (Docs/02 §4.9): [] = tüm operasyonlar (geriye uyumlu varsayılan).
    column = ApiKey.__table__.c.request_type_scope
    assert isinstance(column.type, JSONB)
    assert column.nullable is False
    assert column.server_default is not None
