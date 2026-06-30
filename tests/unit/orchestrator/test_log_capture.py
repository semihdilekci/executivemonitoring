"""log_capture unit testleri — geçici handler kayıtları + sınır + sökme (Faz 6.1)."""

from __future__ import annotations

import logging

from services.orchestrator.log_capture import capture_logs


def test_capture_collects_message_level_and_context() -> None:
    logger = logging.getLogger("ygip.ai_engine.section_generator")

    with capture_logs(["ygip.ai_engine"]) as handler:
        logger.info("digest_distribution_summary", extra={"candidate_count": 42})
        logger.warning("section_no_articles_assigned", extra={"section": "E"})

    messages = [record["message"] for record in handler.records]
    assert "digest_distribution_summary" in messages
    assert "section_no_articles_assigned" in messages

    info = next(r for r in handler.records if r["message"] == "digest_distribution_summary")
    assert info["level"] == "INFO"
    assert info["logger"] == "ygip.ai_engine.section_generator"
    assert info["context"] == {"candidate_count": 42}

    # Bağlam sonunda handler sökülür ve logger seviyesi geri yüklenir.
    assert handler not in logging.getLogger("ygip.ai_engine").handlers


def test_capture_respects_limit_and_counts_dropped() -> None:
    logger = logging.getLogger("ygip.ai_engine.editor_selector")

    with capture_logs(["ygip.ai_engine"], limit=2) as handler:
        for index in range(5):
            logger.warning("kayit %d", index)

    assert len(handler.records) == 2
    assert handler.dropped == 3
