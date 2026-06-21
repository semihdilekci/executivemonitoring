"""RSS/Atom feed ortak yardımcıları — tarih penceresi filtresi.

Collector'lar feed'in tüm geçmişini değil, yalnızca son N günü toplamalı
(varsayılan 7 gün). Aksi halde bir feed aylar öncesine kadar makale döker
(ör. perakende.org 05.03.2026'ya kadar). `max_age_days` kaynak config'inden
override edilebilir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

DEFAULT_COLLECT_WINDOW_DAYS = 7


def resolve_window_days(config: dict[str, Any], default: int = DEFAULT_COLLECT_WINDOW_DAYS) -> int:
    """Kaynak config'inden tarih penceresini (gün) çözer; geçersizse default."""
    raw = config.get("max_age_days", default)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return default
    return days if days > 0 else default


def is_within_window(
    published_at: datetime | None,
    window_days: int,
    *,
    now: datetime | None = None,
    keep_undated: bool = True,
) -> bool:
    """Yayın tarihi son `window_days` içinde mi?

    `published_at` yoksa `keep_undated` döner — tarihsiz feed'lerde içerik
    kaybetmemek için varsayılan olarak tutulur (debug log ile görünür).
    """
    if published_at is None:
        return keep_undated

    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)

    cutoff = reference - timedelta(days=window_days)
    return published_at >= cutoff
