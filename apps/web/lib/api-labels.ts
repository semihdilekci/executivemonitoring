import type { ApiProvider } from "@/types/api";

export const API_PROVIDER_LABELS: Record<ApiProvider, string> = {
  groq: "Groq",
  gemini: "Gemini",
};

export const API_PROVIDER_BADGE_CLASS: Record<ApiProvider, string> = {
  groq: "bg-sky-100 text-sky-800 border-sky-200",
  gemini: "bg-violet-100 text-violet-800 border-violet-200",
};

/** Docs/06 S-ADMIN-API-KEYS: `••••••••••a4Bf` — yalnızca son 4 karakter görünür. */
const MASK_PREFIX = "•".repeat(10);

function resolveKeySuffix(alias: string, keySuffix?: string | null): string {
  if (keySuffix && keySuffix.length >= 4) {
    return keySuffix.slice(-4);
  }
  const normalized = alias.replace(/\s/g, "");
  if (normalized.length >= 4) {
    return normalized.slice(-4);
  }
  return normalized.padEnd(4, "•");
}

export function formatMaskedApiKey(
  alias: string,
  keySuffix?: string | null,
): string {
  return `${MASK_PREFIX}${resolveKeySuffix(alias, keySuffix)}`;
}
