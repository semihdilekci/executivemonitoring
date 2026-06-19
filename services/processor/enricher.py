"""Enricher processor — kategori, schema routing, topics (`Docs/04` §8.4)."""

from __future__ import annotations

import logging
from typing import Any

from services.processor.base_processor import BaseProcessor
from services.processor.gate_processor import SourceConfigResolver, resolve_ingest_mode
from services.processor.keyword_pool import resolve_content_category, resolve_schema_category
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.enricher")


class EnricherProcessor(BaseProcessor):
    """Keyword tabanlı kategori çözümleme ve tag extraction — sıfır LLM."""

    def __init__(self, source_config_resolver: SourceConfigResolver | None = None) -> None:
        self._config_resolver = source_config_resolver

    async def _load_config(self, ctx: ProcessorContext) -> dict[str, Any]:
        if "source_config" in ctx.data.extras:
            raw = ctx.data.extras["source_config"]
            if isinstance(raw, dict):
                return dict(raw)

        if self._config_resolver is not None:
            return await self._config_resolver.get_config(ctx.data.source_id)

        raw_metadata = ctx.data.raw_metadata.get("source_config")
        if isinstance(raw_metadata, dict):
            return dict(raw_metadata)

        return {"ingest_mode": "filtered", "default_category": "macro"}

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        config = await self._load_config(ctx)
        ingest_mode = resolve_ingest_mode(config)
        default_category_raw = config.get("default_category", "macro")
        default_category = (
            default_category_raw.strip()
            if isinstance(default_category_raw, str) and default_category_raw.strip()
            else "macro"
        )

        category, matched_keywords = resolve_content_category(
            ctx.data.title,
            ctx.data.content,
            ingest_mode=ingest_mode,
            default_category=default_category,
        )
        schema_category = resolve_schema_category(category)

        ctx.data.extras["category"] = category
        ctx.data.extras["schema_category"] = schema_category
        ctx.data.extras["topics"] = list(matched_keywords)
        ctx.data.extras["entities"] = []
        ctx.data.extras["matched_keywords"] = list(matched_keywords)

        logger.debug(
            "processor_enrich_success",
            extra={
                "source_id": str(ctx.data.source_id),
                "category": category,
                "schema_category": schema_category,
                "topic_count": len(matched_keywords),
            },
        )
        return ctx.data
