"""Bülten kullanım (reverse-reference) veri erişimi (Faz 6.2).

`processed_items` kayıtlarının hangi bültenlerde kullanıldığını `digest_sections`
`source_references` JSONB alanından çözer (`Docs/04` §8.8).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class DigestUsageRow:
    """Tek bir bülten kullanımı — liste özeti + detay (`section_title`) için ortak."""

    digest_id: uuid.UUID
    newsletter_slug: str
    digest_title: str
    period_start: date
    period_end: date
    section_title: str


def _extract_referenced_ids(source_references: Any) -> set[str]:
    """`source_references` JSONB array → referans verilen processed_item_id string seti."""
    if not isinstance(source_references, list):
        return set()
    referenced: set[str] = set()
    for ref in source_references:
        if isinstance(ref, dict):
            pid = ref.get("processed_item_id")
            if isinstance(pid, str):
                referenced.add(pid)
    return referenced


class DigestUsageRepository:
    """`digest_sections` üzerinden processed_item → bülten eşlemesi."""

    async def find_for_processed_item_ids(
        self,
        db: AsyncSession,
        item_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[DigestUsageRow]]:
        """Sayfa başına batch lookup — id → kullanım listesi (sıralama bülten DESC).

        JSONB `@>` containment ile yalnızca ilgili section'lar çekilir; eşleşme
        Python tarafında id setine göre doğrulanır (object partial match).
        """
        if not item_ids:
            return {}

        id_set = {str(item_id) for item_id in item_ids}
        containment = [
            DigestSection.source_references.contains([{"processed_item_id": str(item_id)}])
            for item_id in item_ids
        ]

        query = (
            select(DigestSection, Digest)
            .join(Digest, Digest.id == DigestSection.digest_id)
            .where(or_(*containment))
            .order_by(Digest.created_at.desc(), DigestSection.section_order.asc())
        )
        result = await db.execute(query)

        usages: dict[uuid.UUID, list[DigestUsageRow]] = {item_id: [] for item_id in item_ids}
        for section, digest in result.all():
            referenced = _extract_referenced_ids(section.source_references) & id_set
            if not referenced:
                continue
            row = DigestUsageRow(
                digest_id=digest.id,
                newsletter_slug=digest.newsletter_slug,
                digest_title=digest.title,
                period_start=digest.period_start,
                period_end=digest.period_end,
                section_title=section.section_title,
            )
            for pid in referenced:
                usages[uuid.UUID(pid)].append(row)
        return usages

    async def find_for_processed_item_id(
        self,
        db: AsyncSession,
        item_id: uuid.UUID,
    ) -> list[DigestUsageRow]:
        """Tek içerik için bülten kullanım listesi (detay endpoint — section_title dahil)."""
        usages = await self.find_for_processed_item_ids(db, [item_id])
        return usages.get(item_id, [])
