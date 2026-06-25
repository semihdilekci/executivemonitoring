"""LLM client factory — DB aktif key'ler + usage log hook (`apps/api` katmanı)."""

from __future__ import annotations

import os

from packages.shared.enums import ApiProvider, LlmRequestType
from services.ai_engine.llm_client import LLMClient, UsageLogHook
from services.ai_engine.models import LLMResponse
from services.ai_engine.providers.anthropic_provider import (
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicProvider,
)
from services.ai_engine.providers.base import LLMProvider
from services.ai_engine.providers.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiProvider
from services.ai_engine.providers.groq_provider import DEFAULT_GROQ_MODEL, GroqProvider
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService


# Anahtarda model seçili değilse (eski kayıt) sağlayıcı bazında fallback; env override
# yalnızca model seçimi olmayan kayıtlar için geriye uyumluluk sağlar.
def _gemini_fallback_model() -> str:
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL


def _anthropic_fallback_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_ANTHROPIC_MODEL


def _groq_fallback_model() -> str:
    return os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL


def _key_in_operation_scope(
    scope: list[str],
    operation_type: LlmRequestType | str | None,
) -> bool:
    """Anahtarın `request_type_scope`'u operasyonu kapsıyor mu (`Docs/04` §9.1).

    `operation_type` None → tüm anahtarlar (filtre yok); boş `scope` `[]` →
    anahtar tüm operasyonlara açık (geriye uyumlu). Aksi halde operasyon
    `scope` içinde olmalı.
    """
    if operation_type is None or not scope:
        return True
    resolved = (
        operation_type.value
        if isinstance(operation_type, LlmRequestType)
        else operation_type
    )
    return resolved in scope


async def list_llm_providers(
    db: AsyncSession,
    api_key_service: ApiKeyService,
    *,
    operation_type: LlmRequestType | str | None = None,
) -> list[LLMProvider]:
    """Aktif API key'lerden provider listesi oluşturur — anahtarın seçili modeliyle.

    `operation_type` verilirse yalnızca `request_type_scope`'u o operasyonu içeren
    veya boş (`[]` = tümü) anahtarlar seçilir (`Docs/04` §9.1). Böylece çeviri
    (§8.45) bülten/chatbot'tan ayrı, daha ucuz bir provider sırasıyla koşar.
    """
    decrypted = await api_key_service.list_active_decrypted(db)
    providers: list[LLMProvider] = []
    for api_key, plaintext in decrypted:
        if not _key_in_operation_scope(api_key.request_type_scope, operation_type):
            continue
        if api_key.provider == ApiProvider.GROQ:
            providers.append(
                GroqProvider(
                    api_key=plaintext,
                    key_id=api_key.id,
                    model=api_key.model or _groq_fallback_model(),
                )
            )
        elif api_key.provider == ApiProvider.GEMINI:
            providers.append(
                GeminiProvider(
                    api_key=plaintext,
                    key_id=api_key.id,
                    model=api_key.model or _gemini_fallback_model(),
                )
            )
        elif api_key.provider == ApiProvider.ANTHROPIC:
            providers.append(
                AnthropicProvider(
                    api_key=plaintext,
                    key_id=api_key.id,
                    model=api_key.model or _anthropic_fallback_model(),
                )
            )
    return providers


def make_llm_usage_hook(
    db: AsyncSession,
    api_usage_service: ApiUsageService,
) -> UsageLogHook:
    """Başarılı LLM çağrısı sonrası usage log hook'u."""

    async def hook(
        provider: LLMProvider,
        response: LLMResponse,
        operation_type: LlmRequestType | str,
    ) -> None:
        await api_usage_service.log_from_llm_response(
            db,
            provider,
            response,
            operation_type=operation_type,
        )

    return hook


async def build_llm_client(
    db: AsyncSession,
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
    *,
    providers: list[LLMProvider] | None = None,
    operation_type: LlmRequestType | str | None = None,
) -> LLMClient:
    """Aktif API key'lerden provider listesi + usage log hook ile LLM client.

    `operation_type` verilirse provider listesi o operasyona göre filtrelenir
    (`list_llm_providers`, `Docs/04` §9.1).
    """
    resolved_providers = providers
    if resolved_providers is None:
        resolved_providers = await list_llm_providers(
            db, api_key_service, operation_type=operation_type
        )
    usage_hook = make_llm_usage_hook(db, api_usage_service)
    return LLMClient(providers=resolved_providers, usage_log_hook=usage_hook)
