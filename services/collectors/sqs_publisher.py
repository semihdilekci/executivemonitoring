"""SQS mesaj yayınlama — collector → processor kuyruğu."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Protocol

import boto3
from botocore.client import BaseClient

from services.collectors.config import CollectorSettings, get_collector_settings
from services.collectors.models import NormalizedArticle

logger = logging.getLogger("ygip.collectors.sqs")


class SQSPublisher:
    """Normalize edilmiş makaleyi tip bazlı SQS kuyruğuna gönderir."""

    def __init__(
        self,
        *,
        settings: CollectorSettings | None = None,
        sqs_client: BaseClient | None = None,
    ) -> None:
        self._settings = settings or get_collector_settings()
        self._client: BaseClient = sqs_client or boto3.client(
            "sqs",
            region_name=self._settings.AWS_REGION,
        )

    def _serialize_article(self, article: NormalizedArticle) -> str:
        payload: dict[str, Any] = {
            "source_id": str(article.source_id),
            "source_type": article.source_type,
            "title": article.title,
            "content": article.content,
            "url": article.url,
            "content_hash": article.content_hash,
            "published_at": _isoformat_optional(article.published_at),
            "collected_at": article.collected_at.isoformat(),
            "raw_metadata": article.raw_metadata,
        }
        if article.external_id is not None:
            payload["external_id"] = article.external_id
        return json.dumps(payload, ensure_ascii=False)

    async def publish(self, article: NormalizedArticle) -> str:
        """Mesajı ilgili kuyruğa gönderir; MessageId döner."""
        queue_url = self._settings.queue_url_for_source_type(article.source_type)
        body = self._serialize_article(article)

        def _send() -> str:
            response = self._client.send_message(QueueUrl=queue_url, MessageBody=body)
            return str(response["MessageId"])

        message_id = await asyncio.to_thread(_send)
        logger.info(
            "sqs_message_published",
            extra={
                "source_id": str(article.source_id),
                "source_type": article.source_type,
                "content_hash": article.content_hash,
                "message_id": message_id,
            },
        )
        return message_id


class SQSPublisherProtocol(Protocol):
    async def publish(self, article: NormalizedArticle) -> str: ...


def _isoformat_optional(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
