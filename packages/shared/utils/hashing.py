"""İçerik hash yardımcıları — dedup anahtarı."""

from __future__ import annotations

import hashlib


def compute_content_hash(content: str) -> str:
    """SHA-256 hex digest; SQS mesajında `sha256:` prefix ile kullanılır."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sqs_content_hash(content: str) -> str:
    """Collector/Processor SQS mesajı formatı."""
    return f"sha256:{compute_content_hash(content)}"


def storage_content_hash(content_hash: str) -> str:
    """DB `raw_items.content_hash` — VARCHAR(64) hex digest, prefix yok."""
    return content_hash.removeprefix("sha256:")[:64]
