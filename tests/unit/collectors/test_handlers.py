"""Per-type Lambda handler entry point testleri."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.handlers import email_handler, gov_handler, rss_handler


def _make_source(source_type: SourceType) -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Test Source",
        source_type=source_type,
        config={},
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        error_count=0,
        category=SourceCategory.TURKISH_MEDIA,
        target_phase="mvp-0",
    )


@pytest.mark.parametrize(
    ("module", "expected_type"),
    [
        (rss_handler, "rss"),
        (email_handler, "email"),
        (gov_handler, "gov"),
    ],
)
def test_type_handler_requires_sources_loader(module: object, expected_type: str) -> None:
    result = module.lambda_handler({}, None)  # type: ignore[attr-defined]

    assert result["statusCode"] == 500
    assert result["body"] == "sources loader not configured"


@pytest.mark.parametrize(
    ("module", "expected_type"),
    [
        (rss_handler, "rss"),
        (email_handler, "email"),
        (gov_handler, "gov"),
    ],
)
def test_type_handler_runs_batch_with_loader(module: object, expected_type: str) -> None:
    source = _make_source(SourceType(expected_type))

    async def _loader(source_type: str) -> list[Source]:
        assert source_type == expected_type
        return [source]

    with patch(
        f"services.collectors.handlers.{expected_type}_handler.run_collector_batch",
        new_callable=AsyncMock,
        return_value={"published": 0, "sources_processed": 1, "sources_failed": 0},
    ) as batch_mock:
        result = module.lambda_handler({"_sources_loader": _loader}, None)  # type: ignore[attr-defined]

    assert result["statusCode"] == 200
    assert result["body"]["sources_processed"] == 1
    batch_mock.assert_awaited_once_with(expected_type, [source])
