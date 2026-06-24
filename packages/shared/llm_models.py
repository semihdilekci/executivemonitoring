"""Sağlayıcı başına seçilebilir LLM modelleri — admin form + doğrulama tek kaynağı.

`api_keys.model` bu listelerden biriyle doldurulur; her tuple'ın ilk elemanı o
sağlayıcının önerilen varsayılanıdır (model seçilmeyen/eski kayıtlarda fallback).
Frontend `apps/web/lib/llm-models.ts` ile senkron tutulur.
"""

from __future__ import annotations

from packages.shared.enums import ApiProvider

# Sağlayıcı -> seçilebilir model id'leri (ilk eleman = önerilen varsayılan).
PROVIDER_MODELS: dict[ApiProvider, tuple[str, ...]] = {
    ApiProvider.GROQ: (
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
    ),
    ApiProvider.GEMINI: (
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ),
    ApiProvider.ANTHROPIC: (
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "claude-opus-4-7",
    ),
}


def models_for(provider: ApiProvider) -> tuple[str, ...]:
    """Sağlayıcının seçilebilir modelleri."""
    return PROVIDER_MODELS.get(provider, ())


def default_model(provider: ApiProvider) -> str:
    """Sağlayıcının önerilen varsayılan modeli (model seçilmeyen kayıtlar için)."""
    models = PROVIDER_MODELS.get(provider)
    if not models:
        msg = f"Bilinmeyen sağlayıcı: {provider}"
        raise ValueError(msg)
    return models[0]


def is_valid_model(provider: ApiProvider, model: str) -> bool:
    """`model` verilen sağlayıcı için geçerli mi."""
    return model in PROVIDER_MODELS.get(provider, ())
