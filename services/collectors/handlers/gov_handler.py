"""Gov collector Lambda handler."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from packages.shared.enums import SourceType
from packages.shared.models.source import Source

from services.collectors.handler import run_collector_batch

GOV_SOURCE_TYPE = SourceType.GOV.value


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge → gov collector Lambda giriş noktası."""
    import asyncio

    sources_loader: Callable[[str], Awaitable[list[Source]]] | None = event.get("_sources_loader")
    if sources_loader is None:
        return {"statusCode": 500, "body": "sources loader not configured"}

    async def _run() -> dict[str, int]:
        sources = await sources_loader(GOV_SOURCE_TYPE)
        return await run_collector_batch(GOV_SOURCE_TYPE, sources)

    results = asyncio.run(_run())
    return {"statusCode": 200, "body": results}
