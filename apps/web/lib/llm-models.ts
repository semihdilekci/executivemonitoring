import type { ApiProvider } from "@/types/api";

/**
 * Sağlayıcı başına seçilebilir LLM modelleri (ilk eleman = önerilen varsayılan).
 * Backend `packages/shared/llm_models.py` ile senkron tutulur.
 */
export const PROVIDER_MODELS: Record<ApiProvider, readonly string[]> = {
  groq: ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant"],
  gemini: ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
  anthropic: [
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-opus-4-7",
  ],
};

/** Sağlayıcının önerilen varsayılan modeli. */
export function defaultModelFor(provider: ApiProvider): string {
  return PROVIDER_MODELS[provider][0];
}
