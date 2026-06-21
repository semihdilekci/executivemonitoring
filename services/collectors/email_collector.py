"""E-posta newsletter collector — IMAP + gönderici filtresi + body çıkarma."""

from __future__ import annotations

import asyncio
import imaplib
import logging
import re
from datetime import UTC, datetime
from email import policy
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from packages.shared.enums import SourceType
from packages.shared.models.source import Source

from services.collectors.base_collector import BaseCollector
from services.collectors.config import get_collector_settings
from services.collectors.models import RawArticle

logger = logging.getLogger("ygip.collectors.email")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMAIL_ADDRESS_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


class EmailCollector(BaseCollector):
    """IMAP üzerinden newsletter e-postalarını toplar (`Docs/04` §7)."""

    source_type = SourceType.EMAIL

    async def collect(self, source: Source) -> list[RawArticle]:
        collector_settings = get_collector_settings()
        imap_host = source.config.get("imap_host") or collector_settings.IMAP_HOST
        mailbox = source.config.get("mailbox", "INBOX")
        allowlist = source.config.get("sender_allowlist")

        if not isinstance(imap_host, str) or not imap_host.strip():
            logger.warning(
                "email_missing_imap_host",
                extra={"source_id": str(source.id)},
            )
            return []

        if not isinstance(mailbox, str) or not mailbox.strip():
            logger.warning(
                "email_missing_mailbox",
                extra={"source_id": str(source.id)},
            )
            return []

        if not isinstance(allowlist, list) or not allowlist:
            logger.warning(
                "email_missing_sender_allowlist",
                extra={"source_id": str(source.id)},
            )
            return []

        normalized_allowlist = {
            addr.lower()
            for item in allowlist
            if isinstance(item, str) and (addr := _extract_email_address(item))
        }
        if not normalized_allowlist:
            return []

        try:
            raw_messages = await self._fetch_messages(source, imap_host.strip(), mailbox.strip())
        except (imaplib.IMAP4.error, OSError, TimeoutError) as exc:
            logger.warning(
                "email_imap_fetch_failed",
                extra={"source_id": str(source.id), "imap_host": imap_host},
                exc_info=True,
            )
            raise RuntimeError(f"IMAP bağlantısı başarısız: {imap_host}") from exc

        articles: list[RawArticle] = []
        for raw in raw_messages:
            article = self._parse_message(source, raw, normalized_allowlist)
            if article is not None:
                articles.append(article)
        return articles

    async def _fetch_messages(self, source: Source, imap_host: str, mailbox: str) -> list[bytes]:
        """IMAP'ten ham e-posta baytlarını çeker — unit testlerde mock'lanır."""

        def _download() -> list[bytes]:
            collector_settings = get_collector_settings()
            imap_user = source.config.get("imap_user") or collector_settings.IMAP_USER
            if not isinstance(imap_user, str) or not imap_user.strip():
                msg = "config.imap_user veya IMAP_USER ortam değişkeni zorunludur"
                raise ValueError(msg)

            password = collector_settings.IMAP_PASSWORD
            if not password:
                msg = "IMAP_PASSWORD ortam değişkeni tanımlı değil"
                raise ValueError(msg)

            client = imaplib.IMAP4_SSL(imap_host, timeout=30)
            try:
                client.login(imap_user.strip(), password)
                status, _ = client.select(mailbox, readonly=True)
                if status != "OK":
                    msg = f"Mailbox seçilemedi: {mailbox}"
                    raise imaplib.IMAP4.error(msg)

                status, data = client.search(None, "UNSEEN")
                if status != "OK" or not data or not data[0]:
                    return []

                messages: list[bytes] = []
                for msg_id in data[0].split():
                    fetch_status, fetched = client.fetch(msg_id, "(RFC822)")
                    if fetch_status != "OK" or not fetched:
                        continue
                    for item in fetched:
                        if isinstance(item, tuple) and len(item) >= 2:
                            payload = item[1]
                            if isinstance(payload, bytes):
                                messages.append(payload)
                return messages
            finally:
                try:
                    client.logout()
                except imaplib.IMAP4.error:
                    logger.debug("imap_logout_failed", exc_info=True)

        return await asyncio.to_thread(_download)

    def _parse_message(
        self,
        source: Source,
        raw: bytes,
        allowlist: set[str],
    ) -> RawArticle | None:
        from email.parser import BytesParser

        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception:
            logger.debug(
                "email_parse_failed",
                extra={"source_id": str(source.id)},
                exc_info=True,
            )
            return None

        sender = _extract_sender_email(message)
        if sender is None or sender not in allowlist:
            return None

        title = _clean_text(str(message.get("Subject", "")))
        content = _extract_body(message)
        if not title or not content:
            return None

        message_id = _clean_text(str(message.get("Message-ID", "")))
        external_id = message_id or f"{sender}:{title}"
        published_at = _parse_email_date(message)
        link = _extract_url_from_message(message, content)
        url = link or f"email://{external_id.lstrip('<').rstrip('>')}"

        metadata: dict[str, Any] = {
            "collector": "email",
            "sender": sender,
            "mailbox": source.config.get("mailbox", "INBOX"),
        }
        if message_id:
            metadata["message_id"] = message_id

        return RawArticle(
            source_id=source.id,
            title=title,
            content=content,
            url=url,
            published_at=published_at,
            metadata=metadata,
            external_id=external_id,
        )


def _extract_sender_email(message: Message) -> str | None:
    from_header = message.get("From", "")
    if not from_header:
        return None
    addresses = getaddresses([str(from_header)])
    for _name, addr in addresses:
        normalized = _extract_email_address(addr)
        if normalized:
            return normalized
    return None


def _extract_email_address(value: str) -> str | None:
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    match = _EMAIL_ADDRESS_RE.search(cleaned)
    return match.group(0) if match else None


def _extract_body(message: Message) -> str:
    if message.is_multipart():
        html = _find_part_text(message, "html")
        if html:
            return _html_to_text(html)
        plain = _find_part_text(message, "plain")
        if plain:
            return plain
        return ""

    content_type = message.get_content_type()
    payload = _decode_payload(message)
    if not payload:
        return ""

    if content_type == "text/html":
        return _html_to_text(payload)
    return _clean_text(payload)


def _find_part_text(message: Message, subtype: str) -> str:
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_subtype() == subtype:
            decoded = _decode_payload(part)
            if decoded:
                return _clean_text(decoded)
    return ""


def _decode_payload(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        logger.debug("email_payload_decode_failed", exc_info=True)
        return ""


def _html_to_text(html: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return _clean_text(extracted)
    except Exception:
        logger.debug("trafilatura_extract_failed", exc_info=True)

    return _clean_text(_HTML_TAG_RE.sub(" ", html))


def _extract_first_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s<>\"']+", text)
    return match.group(0) if match else None


def _extract_url_from_message(message: Message, content: str) -> str | None:
    link = _extract_first_url(content)
    if link:
        return link
    if message.is_multipart():
        html = _find_part_text(message, "html")
        if html:
            return _extract_first_url(html)
    return None


def _parse_email_date(message: Message) -> datetime | None:
    date_header = message.get("Date")
    if not isinstance(date_header, str) or not date_header.strip():
        return None
    try:
        dt = parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _clean_text(value: str) -> str:
    return " ".join(value.split())
