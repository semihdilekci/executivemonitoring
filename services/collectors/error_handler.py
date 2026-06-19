"""Collector hata yönetimi — retry, audit ve admin bildirimi."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from packages.shared.models.audit_log import AuditLog
from packages.shared.models.source import Source

from services.collectors.db_session import collector_db_session

logger = logging.getLogger("ygip.collectors.error_handler")

# Exponential backoff: 2s, 4s, 8s (`Docs/04` §7)
RETRY_DELAYS_SECONDS: tuple[int, ...] = (2, 4, 8)
MAX_RETRIES: int = 3

_SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
    }
)


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    delays: tuple[int, ...] = RETRY_DELAYS_SECONDS,
    max_retries: int = MAX_RETRIES,
) -> T:
    """Geçici hatalarda exponential backoff ile yeniden dener."""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            delay = delays[min(attempt, len(delays) - 1)]
            logger.warning(
                "collector_retry",
                extra={"attempt": attempt + 1, "delay_seconds": delay},
                exc_info=True,
            )
            await asyncio.sleep(delay)
    assert last_error is not None
    raise last_error


class CollectionAuditLogger(Protocol):
    async def log_collection_error(
        self,
        *,
        source: Source,
        error_message: str,
        retry_count: int,
    ) -> None: ...


class CollectionNotifier(Protocol):
    async def notify_admin_collection_error(
        self,
        *,
        source: Source,
        error_message: str,
    ) -> None: ...


class StubCollectionAuditLogger:
    """Lambda/test — audit yazımı log stub."""

    async def log_collection_error(
        self,
        *,
        source: Source,
        error_message: str,
        retry_count: int,
    ) -> None:
        logger.error(
            "system.error",
            extra={
                "event_type": "system.error",
                "target_type": "source",
                "target_id": str(source.id),
                "source_name": source.name,
                "error_message": error_message,
                "retry_count": retry_count,
            },
        )


def _sanitize_error_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in payload.items() if key.lower() not in _SENSITIVE_PAYLOAD_KEYS
    }


class DbCollectionAuditLogger:
    """Production path — `audit_logs` tablosuna `system.error` yazar (`Docs/07` §9.1)."""

    async def log_collection_error(
        self,
        *,
        source: Source,
        error_message: str,
        retry_count: int,
    ) -> None:
        payload = _sanitize_error_payload(
            {
                "source_id": str(source.id),
                "source_name": source.name,
                "error_message": error_message,
                "retry_count": retry_count,
            }
        )
        async with collector_db_session() as session:
            session.add(
                AuditLog(
                    event_type="system.error",
                    actor_user_id=None,
                    target_type="source",
                    target_id=source.id,
                    payload=payload,
                )
            )
            await session.flush()


def default_audit_logger() -> CollectionAuditLogger:
    return DbCollectionAuditLogger()


class StubCollectionNotifier:
    """Admin e-posta bildirimi stub — Faz 5 SMTP entegrasyonu öncesi."""

    def __init__(self, *, is_development: bool = True) -> None:
        self._is_development = is_development

    async def notify_admin_collection_error(
        self,
        *,
        source: Source,
        error_message: str,
    ) -> None:
        logger.info(
            "collection_error_admin_notification",
            extra={
                "source_id": str(source.id),
                "source_name": source.name,
                "error_message": error_message,
                "dev_detail": self._is_development,
            },
        )


async def handle_collection_error(
    *,
    source: Source,
    error: Exception,
    audit_logger: CollectionAuditLogger | None = None,
    notifier: CollectionNotifier | None = None,
    retry_count: int = MAX_RETRIES,
) -> None:
    """3. retry sonrası audit + admin bildirimi (`Docs/04` §7, `Docs/07` §9.1)."""
    audit = audit_logger if audit_logger is not None else default_audit_logger()
    notify = notifier or StubCollectionNotifier()
    error_message = str(error)

    await audit.log_collection_error(
        source=source,
        error_message=error_message,
        retry_count=retry_count,
    )
    await notify.notify_admin_collection_error(source=source, error_message=error_message)
