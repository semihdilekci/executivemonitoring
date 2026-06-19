const trDateFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const trDateTimeFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  weekday: "long",
  hour: "2-digit",
  minute: "2-digit",
});

const trShortDateFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function formatDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return trDateFormatter.format(date);
}

export function formatDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return trDateTimeFormatter.format(date);
}

export function formatShortDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return trShortDateFormatter.format(date);
}

export function formatPeriodRange(start: string, end: string): string {
  return `${formatShortDate(start)} – ${formatShortDate(end)}`;
}

const trNumericDateFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function formatNumericDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return trNumericDateFormatter.format(date);
}

const trNumericDateTimeFormatter = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatNumericDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return trNumericDateTimeFormatter.format(date);
}

export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "Hiç giriş yapmadı";

  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();

  if (diffMs < 0) return "Az önce";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "Az önce";
  if (minutes < 60) return `${minutes} dakika önce`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} saat önce`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} gün önce`;

  return formatNumericDate(date);
}
