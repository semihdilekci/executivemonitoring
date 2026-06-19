"""Multi-provider LLM client — Groq + Gemini round-robin fallback."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from packages.shared.enums import LlmRequestType

from services.ai_engine.exceptions import (
    AllProvidersFailedError,
    NoActiveLLMProviderError,
    QuotaExhaustedError,
    RateLimitError,
    ServiceUnavailableError,
)
from services.ai_engine.models import LLMResponse
from services.ai_engine.providers.base import LLMProvider

logger = logging.getLogger("ygip.ai_engine.llm_client")

UsageLogHook = Callable[[LLMProvider, LLMResponse, str], Awaitable[None]]


class LLMClient:
    """Aktif provider listesi üzerinde round-robin LLM tamamlama."""

    def __init__(
        self,
        providers: list[LLMProvider] | None = None,
        *,
        usage_log_hook: UsageLogHook | None = None,
    ) -> None:
        self._providers: list[LLMProvider] = list(providers or [])
        self._current_index = 0
        self._usage_log_hook = usage_log_hook

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        operation_type: LlmRequestType | str = LlmRequestType.CHATBOT,
    ) -> LLMResponse:
        active = [provider for provider in self._providers if provider.is_active]
        if not active:
            raise NoActiveLLMProviderError()

        resolved_operation = (
            operation_type.value
            if isinstance(operation_type, LlmRequestType)
            else operation_type
        )

        for attempt in range(len(active)):
            provider = active[(self._current_index + attempt) % len(active)]
            try:
                response = await provider.complete(
                    prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
            except (RateLimitError, QuotaExhaustedError, ServiceUnavailableError) as exc:
                logger.warning(
                    "LLM provider fallback",
                    extra={
                        "provider": provider.provider.value,
                        "key_id": str(provider.key_id),
                        "error": type(exc).__name__,
                    },
                )
                continue

            self._current_index = (self._current_index + attempt + 1) % len(active)
            await self._log_usage(provider, response, resolved_operation)
            return response

        raise AllProvidersFailedError()

    async def _log_usage(
        self,
        provider: LLMProvider,
        response: LLMResponse,
        operation_type: str,
    ) -> None:
        """Başarılı çağrı sonrası token kullanımı hook'u."""
        if self._usage_log_hook is not None:
            await self._usage_log_hook(provider, response, operation_type)
