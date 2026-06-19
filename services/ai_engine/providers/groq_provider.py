"""Groq LLM provider — OpenAI uyumlu chat completions API."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

import httpx
from packages.shared.enums import ApiProvider

from services.ai_engine.exceptions import (
    QuotaExhaustedError,
    RateLimitError,
    ServiceUnavailableError,
)
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.providers.base import LLMProvider

logger = logging.getLogger("ygip.ai_engine.groq")

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.1-70b-versatile"


def _map_http_status(status_code: int) -> None:
    if status_code == 429:
        raise RateLimitError("Groq rate limit aşıldı.")
    if status_code == 503:
        raise ServiceUnavailableError("Groq servisi geçici olarak kullanılamıyor.")
    if status_code in {402, 403}:
        raise QuotaExhaustedError("Groq kota veya yetki hatası.")


class GroqProvider(LLMProvider):
    """Groq API üzerinden LLM tamamlama."""

    def __init__(
        self,
        *,
        api_key: str,
        key_id: UUID,
        model: str = DEFAULT_GROQ_MODEL,
        is_active: bool = True,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            msg = "Groq API key boş"
            raise ValueError(msg)
        self._api_key = api_key
        self._key_id = key_id
        self._model = model
        self._is_active = is_active
        self._timeout = timeout_seconds

    @property
    def provider(self) -> ApiProvider:
        return ApiProvider.GROQ

    @property
    def key_id(self) -> UUID:
        return self._key_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(GROQ_CHAT_COMPLETIONS_URL, headers=headers, json=payload)

        if response.status_code >= 400:
            _map_http_status(response.status_code)
            response.raise_for_status()

        latency_ms = int((time.perf_counter() - started) * 1000)
        return _parse_groq_response(
            response.json(),
            provider=ApiProvider.GROQ,
            default_model=self._model,
            key_id=self._key_id,
            latency_ms=latency_ms,
        )


def _parse_groq_response(
    body: dict[str, Any],
    *,
    provider: ApiProvider,
    default_model: str,
    key_id: UUID,
    latency_ms: int,
) -> LLMResponse:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        msg = "Groq yanıtı geçersiz: choices eksik"
        raise ValueError(msg)

    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        msg = "Groq yanıtı geçersiz: content eksik"
        raise ValueError(msg)

    usage_value = body.get("usage")
    usage_raw: dict[str, Any] = usage_value if isinstance(usage_value, dict) else {}
    prompt_tokens = int(usage_raw.get("prompt_tokens", 0))
    completion_tokens = int(usage_raw.get("completion_tokens", 0))
    total_tokens = int(usage_raw.get("total_tokens", prompt_tokens + completion_tokens))
    model = str(body.get("model") or default_model)

    return LLMResponse(
        text=content,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        provider=provider,
        model=f"groq/{model}",
        latency_ms=latency_ms,
        api_key_id=key_id,
    )
