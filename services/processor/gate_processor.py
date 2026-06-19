"""Gate processor — ingest_mode + master keyword filtresi (`Docs/04` §8.3)."""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from services.processor.base_processor import BaseProcessor
from services.processor.keyword_pool import has_master_keyword_match
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.gate")

INGEST_MODE_ALL = "all"
INGEST_MODE_FILTERED = "filtered"
_VALID_INGEST_MODES = frozenset({INGEST_MODE_ALL, INGEST_MODE_FILTERED})


class SourceConfigResolver(Protocol):
    """Kaynak config sağlayıcı — iter 7'de DB implementasyonu."""

    async def get_config(self, source_id: UUID) -> dict[str, Any]: ...


class StaticSourceConfigResolver:
    """Test/dev için sabit kaynak config haritası."""

    def __init__(
        self,
        configs: dict[UUID, dict[str, Any]] | None = None,
        *,
        default: dict[str, Any] | None = None,
    ) -> None:
        self._configs = configs or {}
        self._default = default or {
            "ingest_mode": INGEST_MODE_FILTERED,
            "default_category": "macro",
        }

    async def get_config(self, source_id: UUID) -> dict[str, Any]:
        return dict(self._configs.get(source_id, self._default))


def resolve_ingest_mode(config: dict[str, Any]) -> str:
    """Geçersiz değer → filtered (strict gate)."""
    ingest_mode = config.get("ingest_mode")
    if ingest_mode in _VALID_INGEST_MODES:
        return str(ingest_mode)
    return INGEST_MODE_FILTERED


class GateProcessor(BaseProcessor):
    """ingest_mode gate — filtered kaynaklarda master keyword eşleşmesi zorunlu."""

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

        return {"ingest_mode": INGEST_MODE_FILTERED, "default_category": "macro"}

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        config = await self._load_config(ctx)
        ingest_mode = resolve_ingest_mode(config)

        if ingest_mode == INGEST_MODE_ALL:
            logger.debug(
                "processor_gate_pass_all",
                extra={"source_id": str(ctx.data.source_id)},
            )
            return ctx.data

        if has_master_keyword_match(ctx.data.title, ctx.data.content):
            logger.debug(
                "processor_gate_pass_filtered",
                extra={"source_id": str(ctx.data.source_id)},
            )
            return ctx.data

        logger.info(
            "processor_gate_dropped",
            extra={
                "source_id": str(ctx.data.source_id),
                "ingest_mode": ingest_mode,
                "metric": "processor.gate.dropped",
            },
        )
        return None
