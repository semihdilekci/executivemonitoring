import type { SourceCategory, SourceStatus, SourceType } from "@/types/api";

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  rss: "RSS",
  email: "E-posta",
  rest_api: "REST API",
  websocket: "WebSocket",
  gov: "Resmi Kaynak",
};

export const SOURCE_TYPE_COLORS: Record<SourceType, string> = {
  rss: "bg-blue-100 text-blue-800",
  email: "bg-purple-100 text-purple-800",
  rest_api: "bg-orange-100 text-orange-800",
  websocket: "bg-gray-100 text-gray-700",
  gov: "bg-green-100 text-green-800",
};

export const SOURCE_STATUS_LABELS: Record<SourceStatus, string> = {
  active: "Aktif",
  inactive: "Pasif",
  error: "Hatalı",
};

export const SOURCE_CATEGORY_LABELS: Record<SourceCategory, string> = {
  turkish_media: "Türk Medyası",
  fmcg: "FMCG",
  strategy: "Strateji",
  official: "Resmi",
  market: "Piyasa",
  geo: "Coğrafya",
  transport: "Ulaşım",
};

export const POLLING_INTERVAL_OPTIONS = [
  { value: 5, label: "5 dakika" },
  { value: 15, label: "15 dakika" },
  { value: 30, label: "30 dakika" },
  { value: 60, label: "60 dakika" },
] as const;

export const MVP_SOURCE_TYPES: SourceType[] = ["rss", "email", "gov", "rest_api"];

export const SOURCE_CONFIG_HINTS: Record<SourceType, string> = {
  rss: "Zorunlu: feed_url, ingest_mode (all|filtered), default_category",
  email: "Zorunlu: imap_host, mailbox, sender_allowlist (dizi), ingest_mode, default_category",
  gov: "Zorunlu: endpoint_url, ingest_mode, default_category",
  rest_api: "Zorunlu: endpoint, ingest_mode, default_category",
  websocket: "Zorunlu: endpoint, ingest_mode, default_category",
};
