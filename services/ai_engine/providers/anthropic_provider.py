"""Anthropic (Claude) LLM provider — Messages API (`POST /v1/messages`)."""

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

logger = logging.getLogger("ygip.ai_engine.anthropic")

# Varsayılan model — `ANTHROPIC_MODEL` env ile override edilebilir (`llm_client_factory`).
# Opus 4.8 en yetenekli Opus modeli; digest gibi uzun yapılandırılmış çıktıda güvenilir.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
# Messages API sürüm başlığı (stabil; tarih sabiti olarak gönderilir).
ANTHROPIC_API_VERSION = "2023-06-01"


def _map_http_status(status_code: int) -> None:
    if status_code == 429:
        raise RateLimitError("Anthropic rate limit aşıldı.")
    if status_code in {500, 529}:
        raise ServiceUnavailableError("Anthropic servisi geçici olarak kullanılamıyor.")
    if status_code in {402, 403}:
        raise QuotaExhaustedError("Anthropic kota veya yetki hatası.")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API üzerinden LLM tamamlama."""

    def __init__(
        self,
        *,
        api_key: str,
        key_id: UUID,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        is_active: bool = True,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not api_key.strip():
            msg = "Anthropic API key boş"
            raise ValueError(msg)
        self._api_key = api_key
        self._key_id = key_id
        self._model = model
        self._is_active = is_active
        self._timeout = timeout_seconds

    @property
    def provider(self) -> ApiProvider:
        return ApiProvider.ANTHROPIC

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
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                ANTHROPIC_MESSAGES_URL, headers=headers, json=payload
            )

        if response.status_code >= 400:
            _map_http_status(response.status_code)
            response.raise_for_status()

        latency_ms = int((time.perf_counter() - started) * 1000)
        return _parse_anthropic_response(
            response.json(),
            default_model=self._model,
            key_id=self._key_id,
            latency_ms=latency_ms,
        )


def _parse_anthropic_response(
    body: dict[str, Any],
    *,
    default_model: str,
    key_id: UUID,
    latency_ms: int,
) -> LLMResponse:
    # Messages API `content` bloklarının ilk `text` bloğunu metin olarak al.
    content = body.get("content")
    if not isinstance(content, list) or not content:
        msg = "Anthropic yanıtı geçersiz: content eksik"
        raise ValueError(msg)

    text: str | None = None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            block_text = block.get("text")
            if isinstance(block_text, str):
                text = block_text
                break
    if text is None:
        msg = "Anthropic yanıtı geçersiz: text bloğu eksik"
        raise ValueError(msg)

    usage_value = body.get("usage")
    usage_raw: dict[str, Any] = usage_value if isinstance(usage_value, dict) else {}
    prompt_tokens = int(usage_raw.get("input_tokens", 0))
    completion_tokens = int(usage_raw.get("output_tokens", 0))
    total_tokens = prompt_tokens + completion_tokens
    model = str(body.get("model") or default_model)

    return LLMResponse(
        text=text,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        provider=ApiProvider.ANTHROPIC,
        model=f"anthropic/{model}",
        latency_ms=latency_ms,
        api_key_id=key_id,
    )
