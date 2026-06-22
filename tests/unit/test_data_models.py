"""Veri tablo modelleri ve enum unit testleri."""

import uuid

from packages.shared.enums import (
    PROCESSED_ITEM_SCHEMAS,
    ApiProvider,
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


def test_content_chunk_no_processed_item_fk() -> None:
    assert ContentChunk.__table__.foreign_keys == set()


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
