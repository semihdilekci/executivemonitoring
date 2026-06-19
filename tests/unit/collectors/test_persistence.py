"""Collector persistence unit testleri."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from packages.shared.enums import RawItemStatus
from packages.shared.models.raw_item import RawItem
from services.collectors.persistence import (
    IngestStatus,
    ingest_message,
    parse_sqs_message,
)


def test_parse_sqs_message_valid() -> None:
    source_id = uuid.uuid4()
    collected_at = datetime.now(UTC).isoformat()
    body = json.dumps(
        {
            "source_id": str(source_id),
            "source_type": "rss",
            "title": "Başlık",
            "content": "İçerik metni",
            "url": "https://example.com/a",
            "content_hash": "sha256:abc",
            "collected_at": collected_at,
            "raw_metadata": {"k": "v"},
            "external_id": "ext-1",
        }
    )
    message = parse_sqs_message(body)
    assert message.source_id == source_id
    assert message.source_type == "rss"
    assert message.external_id == "ext-1"
    assert message.raw_metadata == {"k": "v"}


def test_parse_sqs_message_missing_field_raises() -> None:
    with pytest.raises(ValueError, match="zorunlu alanlar eksik"):
        parse_sqs_message(json.dumps({"source_id": str(uuid.uuid4())}))


def test_parse_sqs_message_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="geçerli JSON değil"):
        parse_sqs_message("not-json")


def _valid_message_body(source_id: uuid.UUID | None = None) -> str:
    return json.dumps(
        {
            "source_id": str(source_id or uuid.uuid4()),
            "source_type": "rss",
            "title": "Başlık",
            "content": "İçerik metni",
            "url": "https://example.com/a",
            "content_hash": "sha256:abc",
            "collected_at": datetime.now(UTC).isoformat(),
            "raw_metadata": {"k": "v"},
            "external_id": "ext-1",
        }
    )


@pytest.mark.asyncio
async def test_ingest_message_inserts_raw_item() -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    redis = AsyncMock()
    redis.sismember = AsyncMock(return_value=False)
    redis.sadd = AsyncMock()

    result = await ingest_message(mock_session, _valid_message_body(), redis=redis)  # type: ignore[arg-type]  # type: ignore[arg-type]

    assert result.status == IngestStatus.INSERTED
    mock_session.add.assert_called_once()
    raw_item = mock_session.add.call_args.args[0]
    assert isinstance(raw_item, RawItem)
    assert raw_item.status == RawItemStatus.PENDING
    redis.sadd.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_message_skips_redis_duplicate() -> None:
    mock_session = AsyncMock()
    redis = AsyncMock()
    redis.sismember = AsyncMock(return_value=True)

    result = await ingest_message(mock_session, _valid_message_body(), redis=redis)  # type: ignore[arg-type]

    assert result.status == IngestStatus.DUPLICATE
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_message_skips_db_duplicate() -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    redis = AsyncMock()
    redis.sismember = AsyncMock(return_value=False)

    result = await ingest_message(mock_session, _valid_message_body(), redis=redis)  # type: ignore[arg-type]

    assert result.status == IngestStatus.DUPLICATE
    mock_session.add.assert_not_called()
