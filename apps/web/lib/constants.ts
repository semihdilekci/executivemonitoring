import type { NavItem } from "@/types/models";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const APP_ENV =
  process.env.NEXT_PUBLIC_APP_ENV ?? process.env.NODE_ENV ?? "production";

export const PUBLIC_PATHS = ["/login", "/reset-password"] as const;

export const ADMIN_PATH_PREFIX = "/admin";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

/** Varsayılan refresh token ömrü (30 gün) — backend ayarıyla uyumlu */
export const REFRESH_TOKEN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

export const VIEWER_NAV_ITEMS: readonly NavItem[] = [
  { label: "Ana Sayfa", href: "/" },
  { label: "Bültenler", href: "/digests" },
  { label: "AI Chatbot", href: "/chatbot" },
] as const;

export const ADMIN_NAV_ITEMS: readonly NavItem[] = [
  { label: "Kullanıcılar", href: "/admin/users" },
  { label: "Kaynaklar", href: "/admin/sources" },
  { label: "Pipeline İzleme", href: "/admin/pipeline" },
  { label: "İçerik Arşivi", href: "/admin/content-archive" },
  { label: "Keyword Takibi", href: "/admin/keywords" },
  { label: "Prompt Şablonları", href: "/admin/prompt-templates" },
  { label: "API Anahtarları", href: "/admin/api-keys" },
  { label: "Bildirimler", href: "/admin/notifications" },
  { label: "Sohbet Geçmişi", href: "/admin/chat-history" },
  { label: "Denetim Kayıtları", href: "/admin/audit-logs" },
] as const;

export const queryKeys = {
  brief: {
    today: ["brief", "today"] as const,
  },
  digests: {
    all: ["digests"] as const,
    list: (params?: {
      cursor?: string;
      digestType?: string;
      limit?: number;
      isRead?: boolean;
    }) => ["digests", "list", params ?? {}] as const,
    detail: (id: string) => ["digests", "detail", id] as const,
    readState: (userId: string) => ["digests", "read-state", userId] as const,
  },
  users: {
    all: ["users"] as const,
    list: (filters?: {
      role?: string;
      is_active?: boolean;
      limit?: number;
    }) => ["users", "list", filters ?? {}] as const,
    detail: (id: string) => ["users", "detail", id] as const,
  },
  sources: {
    all: ["sources"] as const,
    list: (filters?: {
      source_type?: string;
      status?: string;
      category?: string;
      limit?: number;
    }) => ["sources", "list", filters ?? {}] as const,
    detail: (id: string) => ["sources", "detail", id] as const,
  },
  chatbot: {
    all: ["chatbot"] as const,
  },
  chatHistory: {
    all: ["chat-history"] as const,
    list: (filters?: {
      user_id?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
    }) => ["chat-history", "list", filters ?? {}] as const,
  },
  auditLogs: {
    all: ["audit-logs"] as const,
    list: (filters?: {
      event_type?: string;
      actor_user_id?: string;
      target_type?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
    }) => ["audit-logs", "list", filters ?? {}] as const,
  },
  notifications: {
    all: ["notifications"] as const,
    preferences: ["notifications", "preferences"] as const,
    recipients: ["notifications", "recipients"] as const,
  },
  promptTemplates: {
    all: ["prompt-templates"] as const,
    list: (filters?: { digest_type?: string; is_active?: boolean }) =>
      ["prompt-templates", "list", filters ?? {}] as const,
    detail: (id: string) => ["prompt-templates", "detail", id] as const,
  },
  apiKeys: {
    all: ["api-keys"] as const,
    usage: (params?: {
      period?: string;
      provider?: string;
      api_key_id?: string;
      start_date?: string;
      end_date?: string;
    }) => ["api-keys", "usage", params ?? {}] as const,
  },
  settings: {
    all: ["settings"] as const,
  },
  pipeline: {
    all: ["pipeline"] as const,
    list: (filters?: {
      run_type?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
    }) => ["pipeline", "list", filters ?? {}] as const,
    run: (id: string) => ["pipeline", "run", id] as const,
    items: (id: string, params?: { outcome?: string; page?: number }) =>
      ["pipeline", "run", id, "items", params ?? {}] as const,
  },
  contentArchive: {
    all: ["content-archive"] as const,
    list: (filters?: {
      source_id?: string;
      schema_category?: string;
      content_category?: string;
      published_from?: string;
      published_to?: string;
      min_score?: number;
      topic?: string;
      q?: string;
      has_digest?: boolean;
      sort_by?: string;
      sort_dir?: string;
      limit?: number;
    }) => ["content-archive", "list", filters ?? {}] as const,
    detail: (id: string, schemaCategory: string) =>
      ["content-archive", "detail", id, schemaCategory] as const,
  },
  keywords: {
    all: ["keywords"] as const,
    list: (filters?: {
      category?: string;
      q?: string;
      is_active?: boolean;
      page?: number;
      page_size?: number;
    }) => ["keywords", "list", filters ?? {}] as const,
  },
} as const;

export const CHATBOT_EXAMPLE_QUESTIONS = [
  "Kakao fiyatları neden düştü?",
  "Son hafta hangi regülasyon değişiklikleri oldu?",
  "FMCG sektöründe M&A aktivitesi nasıl?",
  "Türk medyasında bu hafta öne çıkan temalar neler?",
] as const;
