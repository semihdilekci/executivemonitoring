"""Processor pipeline veri modelleri — SQS mesajı ↔ pipeline context."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

ProcessorResultStatus = Literal["success", "skipped", "failed"]


class MessageParseError(ValueError):
    """SQS mesaj gövdesi deserialize veya validate edilemedi."""


@dataclass(frozen=True, slots=True)
class ProcessorInput:
    """Collector SQS mesajından deserialize edilen girdi (`Docs/04` §7)."""

    source_id: UUID
    source_type: str
    title: str
    content: str
    content_hash: str
    published_at: datetime | None
    raw_metadata: dict[str, Any]
    url: str | None = None
    external_id: str | None = None
    collected_at: datetime | None = None
    sqs_message_id: str | None = None

    @classmethod
    def from_sqs_body(cls, body: str, *, sqs_message_id: str | None = None) -> ProcessorInput:
        """JSON SQS body → ProcessorInput; malformed input → MessageParseError."""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MessageParseError("SQS body geçerli JSON değil") from exc

        if not isinstance(payload, dict):
            raise MessageParseError("SQS body JSON object olmalı")

        return cls.from_dict(payload, sqs_message_id=sqs_message_id)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        sqs_message_id: str | None = None,
    ) -> ProcessorInput:
        source_id_raw = payload.get("source_id")
        if source_id_raw is None:
            raise MessageParseError("source_id zorunlu")
        if isinstance(source_id_raw, int):
            raise MessageParseError("source_id UUID string olmalı, sayı değil")
        try:
            source_id = UUID(str(source_id_raw))
        except (TypeError, ValueError) as exc:
            raise MessageParseError("source_id geçerli UUID değil") from exc

        source_type = payload.get("source_type")
        if not isinstance(source_type, str) or not source_type.strip():
            raise MessageParseError("source_type zorunlu")

        title = payload.get("title")
        content = payload.get("content")
        content_hash = payload.get("content_hash")
        if not isinstance(title, str):
            raise MessageParseError("title zorunlu")
        if not isinstance(content, str):
            raise MessageParseError("content zorunlu")
        if not isinstance(content_hash, str) or not content_hash.strip():
            raise MessageParseError("content_hash zorunlu")

        raw_metadata = payload.get("raw_metadata", {})
        if not isinstance(raw_metadata, dict):
            raise MessageParseError("raw_metadata object olmalı")

        url = payload.get("url")
        external_id = payload.get("external_id")
        published_at = _parse_optional_datetime(payload.get("published_at"))
        collected_at = _parse_optional_datetime(payload.get("collected_at"))

        return cls(
            source_id=source_id,
            source_type=source_type.strip(),
            title=title,
            content=content,
            content_hash=content_hash.strip(),
            published_at=published_at,
            raw_metadata=raw_metadata,
            url=url if isinstance(url, str) else None,
            external_id=external_id if isinstance(external_id, str) else None,
            collected_at=collected_at,
            sqs_message_id=sqs_message_id,
        )


@dataclass(slots=True)
class ProcessorOutput:
    """Pipeline adımları arasında taşınan işlenmiş veri."""

    source_id: UUID
    source_type: str
    title: str
    content: str
    content_hash: str
    published_at: datetime | None
    raw_metadata: dict[str, Any]
    url: str | None = None
    external_id: str | None = None
    collected_at: datetime | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_input(cls, item: ProcessorInput) -> ProcessorOutput:
        return cls(
            source_id=item.source_id,
            source_type=item.source_type,
            title=item.title,
            content=item.content,
            content_hash=item.content_hash,
            published_at=item.published_at,
            raw_metadata=dict(item.raw_metadata),
            url=item.url,
            external_id=item.external_id,
            collected_at=item.collected_at,
        )


@dataclass(frozen=True, slots=True)
class ProcessedResult:
    """Tek mesaj için pipeline sonucu."""

    status: ProcessorResultStatus
    output: ProcessorOutput | None = None
    skip_reason: str | None = None
    error: str | None = None
    processor_name: str | None = None


@dataclass(slots=True)
class ProcessorContext:
    """Zincir boyunca paylaşılan mutable context."""

    input: ProcessorInput
    data: ProcessorOutput


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise MessageParseError("published_at/collected_at ISO 8601 olmalı") from exc
