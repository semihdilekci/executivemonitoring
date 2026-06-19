type EventBadgeVariant = "success" | "info" | "warning" | "error" | "neutral";

interface EventTypeMeta {
  label: string;
  variant: EventBadgeVariant;
}

const EVENT_TYPE_META: Record<string, EventTypeMeta> = {
  "user.login": { label: "Giriş", variant: "success" },
  "user.logout": { label: "Çıkış", variant: "info" },
  "user.login_failed": { label: "Başarısız giriş", variant: "error" },
  "user.created": { label: "Kullanıcı oluşturuldu", variant: "success" },
  "user.updated": { label: "Kullanıcı güncellendi", variant: "info" },
  "user.role_changed": { label: "Rol değişti", variant: "warning" },
  "user.deactivated": { label: "Kullanıcı pasif", variant: "warning" },
  "password.reset_initiated": { label: "Şifre sıfırlama", variant: "info" },
  "password.reset_completed": { label: "Şifre sıfırlandı", variant: "success" },
  "source.created": { label: "Kaynak oluşturuldu", variant: "success" },
  "source.deleted": { label: "Kaynak silindi", variant: "error" },
  "source.status_changed": { label: "Kaynak durumu", variant: "info" },
  "prompt_template.created": { label: "Prompt oluşturuldu", variant: "success" },
  "prompt_template.updated": { label: "Prompt güncellendi", variant: "info" },
  "api_key.created": { label: "API anahtarı eklendi", variant: "success" },
  "api_key.deleted": { label: "API anahtarı silindi", variant: "error" },
  "api_key.status_changed": { label: "API anahtarı durumu", variant: "info" },
  "digest.generated": { label: "Bülten üretildi", variant: "success" },
  "system.error": { label: "Sistem hatası", variant: "error" },
  "notification.preference_updated": {
    label: "Bildirim tercihi",
    variant: "info",
  },
};

export const AUDIT_EVENT_FILTER_OPTIONS = [
  { value: "", label: "Tüm olaylar" },
  { value: "user.login", label: "Giriş" },
  { value: "user.logout", label: "Çıkış" },
  { value: "user.created", label: "Kullanıcı oluşturuldu" },
  { value: "user.role_changed", label: "Rol değişti" },
  { value: "user.deactivated", label: "Kullanıcı pasif" },
  { value: "source.created", label: "Kaynak oluşturuldu" },
  { value: "source.deleted", label: "Kaynak silindi" },
  { value: "source.status_changed", label: "Kaynak durumu" },
  { value: "prompt_template.updated", label: "Prompt güncellendi" },
  { value: "api_key.created", label: "API anahtarı eklendi" },
  { value: "digest.generated", label: "Bülten üretildi" },
  { value: "system.error", label: "Sistem hatası" },
] as const;

export const AUDIT_TARGET_TYPE_OPTIONS = [
  { value: "", label: "Tüm hedefler" },
  { value: "user", label: "Kullanıcı" },
  { value: "source", label: "Kaynak" },
  { value: "digest", label: "Bülten" },
  { value: "api_key", label: "API anahtarı" },
  { value: "prompt_template", label: "Prompt şablonu" },
] as const;

export const EVENT_BADGE_CLASS: Record<EventBadgeVariant, string> = {
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  info: "bg-sky-100 text-sky-800 border-sky-200",
  warning: "bg-amber-100 text-amber-800 border-amber-200",
  error: "bg-red-100 text-red-800 border-red-200",
  neutral: "bg-gray-100 text-gray-700 border-gray-200",
};

export function getAuditEventMeta(eventType: string): EventTypeMeta {
  return (
    EVENT_TYPE_META[eventType] ?? {
      label: eventType.replaceAll(".", " ").replaceAll("_", " "),
      variant: "neutral",
    }
  );
}

const SENSITIVE_PAYLOAD_KEYS = new Set([
  "password",
  "api_key",
  "token",
  "fcm_token",
  "encrypted_key",
  "refresh_token",
  "access_token",
]);

export function maskAuditPayload(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  const masked: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(payload)) {
    if (SENSITIVE_PAYLOAD_KEYS.has(key.toLowerCase())) {
      masked[key] = "••••••••";
      continue;
    }

    if (value && typeof value === "object" && !Array.isArray(value)) {
      masked[key] = maskAuditPayload(value as Record<string, unknown>);
      continue;
    }

    masked[key] = value;
  }

  return masked;
}

export function formatAuditTarget(
  targetType: string | null,
  targetId: string | null,
  payload: Record<string, unknown>,
): string {
  if (!targetType) return "—";

  const name =
    (typeof payload.name === "string" && payload.name) ||
    (typeof payload.email === "string" && payload.email) ||
    (typeof payload.source_name === "string" && payload.source_name);

  if (name) {
    return `${targetType}: ${name}`;
  }

  if (targetId) {
    return `${targetType}: ${targetId.slice(0, 8)}…`;
  }

  return targetType;
}
