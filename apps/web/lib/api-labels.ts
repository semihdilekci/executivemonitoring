import type { ApiProvider } from "@/types/api";

export const API_PROVIDER_LABELS: Record<ApiProvider, string> = {
  groq: "Groq",
  gemini: "Gemini",
};

export const API_PROVIDER_BADGE_CLASS: Record<ApiProvider, string> = {
  groq: "bg-sky-100 text-sky-800 border-sky-200",
  gemini: "bg-violet-100 text-violet-800 border-violet-200",
};

const PROVIDER_KEY_PREFIX: Record<ApiProvider, string> = {
  groq: "gsk",
  gemini: "AI",
};

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
  provider: ApiProvider = "groq",
  keySuffix?: string | null,
): string {
  const prefix = PROVIDER_KEY_PREFIX[provider];
  const suffix = resolveKeySuffix(alias, keySuffix);
  return `${prefix}-...${suffix}`;
}
