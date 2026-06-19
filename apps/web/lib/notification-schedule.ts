import type { NotificationScheduleConfig } from "@/types/api";

export type ScheduleDigestKey =
  | "strategy_weekly"
  | "turkish_media_weekly"
  | "fmcg_weekly"
  | "daily_brief";

export interface ScheduleRowMeta {
  key: ScheduleDigestKey;
  label: string;
}

export const NOTIFICATION_SCHEDULE_ROWS: ScheduleRowMeta[] = [
  { key: "strategy_weekly", label: "Strateji Haftalık" },
  { key: "turkish_media_weekly", label: "Türk Medyası Haftalık" },
  { key: "fmcg_weekly", label: "FMCG Haftalık" },
  { key: "daily_brief", label: "Günlük Özet" },
];

export const SCHEDULE_DAY_OPTIONS = [
  { value: "monday", label: "Pazartesi" },
  { value: "tuesday", label: "Salı" },
  { value: "wednesday", label: "Çarşamba" },
  { value: "thursday", label: "Perşembe" },
  { value: "friday", label: "Cuma" },
  { value: "saturday", label: "Cumartesi" },
  { value: "sunday", label: "Pazar" },
  { value: "everyday", label: "Her gün" },
] as const;

export const DEFAULT_NOTIFICATION_SCHEDULE: NotificationScheduleConfig = {
  strategy_weekly: { day: "friday", time: "18:00", enabled: true },
  turkish_media_weekly: { day: "saturday", time: "10:00", enabled: true },
  fmcg_weekly: { day: "saturday", time: "12:00", enabled: true },
  daily_brief: { day: "everyday", time: "09:00", enabled: true },
};

export const NOTIFICATION_SCHEDULE_SETTING_KEY = "notification_schedule";

export function parseNotificationSchedule(
  value: unknown,
): NotificationScheduleConfig {
  if (!value || typeof value !== "object") {
    return { ...DEFAULT_NOTIFICATION_SCHEDULE };
  }

  const source = value as Record<string, unknown>;
  const result = { ...DEFAULT_NOTIFICATION_SCHEDULE };

  for (const row of NOTIFICATION_SCHEDULE_ROWS) {
    const entry = source[row.key];
    if (!entry || typeof entry !== "object") continue;
    const record = entry as Record<string, unknown>;
    result[row.key] = {
      day:
        typeof record.day === "string"
          ? record.day
          : result[row.key].day,
      time:
        typeof record.time === "string"
          ? record.time
          : result[row.key].time,
      enabled:
        typeof record.enabled === "boolean"
          ? record.enabled
          : result[row.key].enabled,
    };
  }

  return result;
}

export function scheduleDayLabel(day: string): string {
  return (
    SCHEDULE_DAY_OPTIONS.find((option) => option.value === day)?.label ?? day
  );
}
