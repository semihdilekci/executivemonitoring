"""Gemini LLM provider — Google Generative Language API."""

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

logger = logging.getLogger("ygip.ai_engine.gemini")

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _map_http_status(status_code: int) -> None:
    if status_code == 429:
        raise RateLimitError("Gemini rate limit aşıldı.")
    if status_code == 503:
        raise ServiceUnavailableError("Gemini servisi geçici olarak kullanılamıyor.")
    if status_code in {402, 403}:
        raise QuotaExhaustedError("Gemini kota veya yetki hatası.")


class GeminiProvider(LLMProvider):
    """Google Gemini API üzerinden LLM tamamlama."""

    def __init__(
        self,
        *,
        api_key: str,
        key_id: UUID,
        model: str = DEFAULT_GEMINI_MODEL,
        is_active: bool = True,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key.strip():
            msg = "Gemini API key boş"
            raise ValueError(msg)
        self._api_key = api_key
        self._key_id = key_id
        self._model = model
        self._is_active = is_active
        self._timeout = timeout_seconds

    @property
    def provider(self) -> ApiProvider:
        return ApiProvider.GEMINI

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
        url = f"{GEMINI_API_BASE}/{self._model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                params={"key": self._api_key},
                json=payload,
            )

        if response.status_code >= 400:
            _map_http_status(response.status_code)
            response.raise_for_status()

        latency_ms = int((time.perf_counter() - started) * 1000)
        return _parse_gemini_response(
            response.json(),
            default_model=self._model,
            key_id=self._key_id,
            latency_ms=latency_ms,
        )


def _parse_gemini_response(
    body: dict[str, Any],
    *,
    default_model: str,
    key_id: UUID,
    latency_ms: int,
) -> LLMResponse:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        msg = "Gemini yanıtı geçersiz: candidates eksik"
        raise ValueError(msg)

    first = candidates[0]
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        msg = "Gemini yanıtı geçersiz: parts eksik"
        raise ValueError(msg)

    text_part = parts[0]
    text = text_part.get("text") if isinstance(text_part, dict) else None
    if not isinstance(text, str):
        msg = "Gemini yanıtı geçersiz: text eksik"
        raise ValueError(msg)

    usage_value = body.get("usageMetadata")
    usage_raw: dict[str, Any] = usage_value if isinstance(usage_value, dict) else {}
    prompt_tokens = int(usage_raw.get("promptTokenCount", 0))
    completion_tokens = int(usage_raw.get("candidatesTokenCount", 0))
    total_tokens = int(usage_raw.get("totalTokenCount", prompt_tokens + completion_tokens))
    model = str(body.get("modelVersion") or default_model)

    return LLMResponse(
        text=text,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        provider=ApiProvider.GEMINI,
        model=f"gemini/{model}",
        latency_ms=latency_ms,
        api_key_id=key_id,
    )
