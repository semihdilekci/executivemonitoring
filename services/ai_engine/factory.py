"""LLM client factory — provider listesi ile in-memory client oluşturma."""

from __future__ import annotations

from services.ai_engine.llm_client import LLMClient, UsageLogHook
from services.ai_engine.providers.base import LLMProvider


def create_llm_client(
    providers: list[LLMProvider],
    *,
    usage_log_hook: UsageLogHook | None = None,
) -> LLMClient:
    """Verilen provider listesi ile LLM client oluşturur — DB bağımlılığı yok."""
    return LLMClient(providers=providers, usage_log_hook=usage_log_hook)
