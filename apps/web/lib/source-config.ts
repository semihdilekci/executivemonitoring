import type { SourceType } from "@/types/api";

const INGEST_MODES = new Set(["all", "filtered"]);

const TYPE_REQUIRED_FIELDS: Record<SourceType, string[]> = {
  rss: ["feed_url"],
  email: ["imap_host", "mailbox", "sender_allowlist"],
  gov: ["endpoint_url"],
  rest_api: ["endpoint"],
  websocket: ["endpoint"],
};

export const DEFAULT_CONFIG_TEMPLATES: Record<SourceType, Record<string, unknown>> = {
  rss: {
    feed_url: "",
    ingest_mode: "all",
    default_category: "fmcg",
    language: "tr",
  },
  email: {
    imap_host: "",
    mailbox: "INBOX",
    sender_allowlist: [],
    ingest_mode: "filtered",
    default_category: "strategy",
  },
  gov: {
    endpoint_url: "",
    parse_format: "html",
    ingest_mode: "all",
    default_category: "regulatory",
  },
  rest_api: {
    endpoint: "",
    ingest_mode: "all",
    default_category: "finance",
  },
  websocket: {
    endpoint: "",
    ingest_mode: "all",
    default_category: "finance",
  },
};

export function getDefaultConfigJson(sourceType: SourceType): string {
  return JSON.stringify(DEFAULT_CONFIG_TEMPLATES[sourceType], null, 2);
}

export function parseConfigJson(raw: string): {
  config: Record<string, unknown> | null;
  error: string | null;
} {
  const trimmed = raw.trim();
  if (!trimmed) {
    return { config: null, error: "Yapılandırma JSON boş olamaz." };
  }

  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return { config: null, error: "Yapılandırma bir JSON nesnesi olmalıdır." };
    }
    return { config: parsed as Record<string, unknown>, error: null };
  } catch {
    return { config: null, error: "Geçersiz JSON formatı." };
  }
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

export function validateSourceConfig(
  sourceType: SourceType,
  config: Record<string, unknown>,
): string[] {
  const errors: string[] = [];

  const ingestMode = config.ingest_mode;
  if (typeof ingestMode !== "string" || !INGEST_MODES.has(ingestMode)) {
    errors.push("ingest_mode zorunludur ('all' veya 'filtered').");
  }

  const defaultCategory = config.default_category;
  if (typeof defaultCategory !== "string" || !defaultCategory.trim()) {
    errors.push("default_category zorunludur.");
  }

  for (const field of TYPE_REQUIRED_FIELDS[sourceType]) {
    if (isEmptyValue(config[field])) {
      errors.push(`${field} zorunludur.`);
    }
  }

  if (sourceType === "email") {
    const allowlist = config.sender_allowlist;
    if (allowlist !== undefined && !Array.isArray(allowlist)) {
      errors.push("sender_allowlist bir dizi olmalıdır.");
    }
  }

  return errors;
}

export function getSourceEndpointLabel(sourceType: SourceType, config: Record<string, unknown>): string {
  switch (sourceType) {
    case "rss":
      return typeof config.feed_url === "string" ? config.feed_url : "—";
    case "email":
      return typeof config.imap_host === "string" ? config.imap_host : "—";
    case "gov":
      return typeof config.endpoint_url === "string" ? config.endpoint_url : "—";
    case "rest_api":
    case "websocket":
      return typeof config.endpoint === "string" ? config.endpoint : "—";
    default:
      return "—";
  }
}

export function maskSensitiveConfigFields(
  config: Record<string, unknown>,
): Record<string, unknown> {
  const masked = { ...config };
  for (const key of Object.keys(masked)) {
    if (/api[_-]?key|password|secret|token/i.test(key)) {
      const value = masked[key];
      if (typeof value === "string" && value.length > 4) {
        masked[key] = `${value.slice(0, 4)}…`;
      }
    }
  }
  return masked;
}
