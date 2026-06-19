import type { ApiError } from "@/types/api";

const ERROR_MESSAGES: Record<string, string> = {
  AUTH_INVALID_CREDENTIALS: "E-posta veya şifre hatalı.",
  UNAUTHORIZED: "E-posta veya şifre hatalı.",
  AUTH_ACCOUNT_INACTIVE:
    "Hesabınız pasif durumda. Yöneticinize başvurun.",
  RATE_LIMIT_EXCEEDED: "Çok fazla deneme. Lütfen bekleyin.",
  NETWORK_ERROR:
    "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.",
  AUTH_INVALID_RESET_TOKEN:
    "Bu şifre sıfırlama linki geçersiz veya süresi dolmuş. Yöneticinizden yeni bir link talep edin.",
  PASSWORD_POLICY_VIOLATION:
    "Şifre en az 8 karakter, 1 büyük harf ve 1 rakam içermelidir.",
};

export function getAuthErrorMessage(error: ApiError): string {
  return ERROR_MESSAGES[error.code] ?? error.message;
}

export function getRetryAfterSeconds(
  error: ApiError,
  responseHeaders?: { retryAfter?: string | null },
): number | null {
  if (error.code !== "RATE_LIMIT_EXCEEDED") return null;

  const headerValue = responseHeaders?.retryAfter;
  if (headerValue) {
    const parsed = Number.parseInt(headerValue, 10);
    if (!Number.isNaN(parsed) && parsed > 0) return parsed;
  }

  const detailsRetry = error.details.retry_after_seconds;
  if (typeof detailsRetry === "number" && detailsRetry > 0) {
    return detailsRetry;
  }

  return 60;
}
