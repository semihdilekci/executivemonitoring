"""Digest HTML arşiv servisi — dev stub, prod S3 (Faz 8)."""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime

from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection

logger = logging.getLogger("ygip.ai_engine.archive_service")


class DigestArchiveService:
    """HTML snapshot üretimi ve S3 yükleme stub'ı."""

    async def upload_html(
        self,
        *,
        digest: Digest,
        sections: list[DigestSection],
    ) -> str:
        archive_key = (
            f"{digest.digest_type.value}/"
            f"{digest.period_start.year}/"
            f"{digest.period_start.month:02d}/"
            f"{digest.id}.html"
        )
        html_body = self._render_html(digest=digest, sections=sections)
        logger.info(
            "digest_archive_stub_upload",
            extra={
                "digest_id": str(digest.id),
                "archive_key": archive_key,
                "html_bytes": len(html_body.encode("utf-8")),
            },
        )
        return archive_key

    def _render_html(self, *, digest: Digest, sections: list[DigestSection]) -> str:
        section_blocks: list[str] = []
        for section in sections:
            refs = "".join(
                f"<li>{html.escape(str(ref.get('title', '')))}</li>"
                for ref in section.source_references
                if isinstance(ref, dict)
            )
            impact = (
                f"<p><strong>Etki:</strong> {html.escape(section.impact_note)}</p>"
                if section.impact_note
                else ""
            )
            section_blocks.append(
                "<section>"
                f"<h2>{html.escape(section.section_title)}</h2>"
                f"<div>{html.escape(section.ai_summary)}</div>"
                f"{impact}"
                f"<ul>{refs}</ul>"
                "</section>"
            )

        generated_at = datetime.now(UTC).isoformat()
        return (
            "<!DOCTYPE html><html lang='tr'><head>"
            f"<meta charset='utf-8'><title>{html.escape(digest.title)}</title>"
            "</head><body>"
            f"<h1>{html.escape(digest.title)}</h1>"
            f"<p>Üretim: {html.escape(generated_at)}</p>"
            f"{''.join(section_blocks)}"
            "</body></html>"
        )


digest_archive_service = DigestArchiveService()
