"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import {
  DEFAULT_NOTIFICATION_SCHEDULE,
  NOTIFICATION_SCHEDULE_SETTING_KEY,
  parseNotificationSchedule,
} from "@/lib/notification-schedule";
import type {
  ApiError,
  CreateNotificationRecipientRequest,
  NotificationPreferenceItem,
  NotificationPreferenceListResponse,
  NotificationRecipientItem,
  NotificationRecipientListResponse,
  NotificationScheduleConfig,
  SettingItem,
  SettingListResponse,
  SettingUpdateResponse,
  UpdateNotificationPreferenceRequest,
  UpdateSettingRequest,
} from "@/types/api";

export const JWT_ACCESS_TOKEN_KEY = "jwt_access_token_minutes";
export const JWT_REFRESH_TOKEN_KEY = "jwt_refresh_token_days";
export const CHATBOT_RATE_LIMIT_KEY = "chatbot_rate_limit_per_minute";
export const CHATBOT_TEMPERATURE_KEY = "chatbot_temperature";

export function useNotificationPreferences() {
  return useQuery({
    queryKey: queryKeys.notifications.preferences,
    queryFn: async () => {
      const response = await apiClient.get<NotificationPreferenceListResponse>(
        "/notifications/preferences",
      );
      return response.data.data;
    },
  });
}

export function useUpdateNotificationPreference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string;
      body: UpdateNotificationPreferenceRequest;
    }) => {
      const response = await apiClient.put<NotificationPreferenceItem>(
        `/notifications/preferences/${userId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.all,
      });
    },
  });
}

export function useNotificationRecipients() {
  return useQuery({
    queryKey: queryKeys.notifications.recipients,
    queryFn: async () => {
      try {
        const response = await apiClient.get<NotificationRecipientListResponse>(
          "/notifications/recipients",
        );
        return {
          items: response.data.data,
          apiSupported: true as const,
        };
      } catch (error) {
        const apiError = error as ApiError;
        if (apiError.statusCode === 404 || apiError.statusCode === 405) {
          return {
            items: [] as NotificationRecipientItem[],
            apiSupported: false as const,
          };
        }
        throw error;
      }
    },
  });
}

export function useCreateNotificationRecipient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreateNotificationRecipientRequest) => {
      const response = await apiClient.post<NotificationRecipientItem>(
        "/notifications/recipients",
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.recipients,
      });
    },
  });
}

export function useDeleteNotificationRecipient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recipientId: string) => {
      await apiClient.delete(`/notifications/recipients/${recipientId}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.recipients,
      });
    },
  });
}

export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings.all,
    queryFn: async () => {
      const response = await apiClient.get<SettingListResponse>("/settings");
      return response.data.data;
    },
  });
}

export function useUpdateSetting() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ key, body }: { key: string; body: UpdateSettingRequest }) => {
      const response = await apiClient.put<SettingUpdateResponse>(
        `/settings/${key}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
    },
  });
}

export function findSettingValue(
  settings: SettingItem[] | undefined,
  key: string,
): number | undefined {
  if (!settings) return undefined;
  const item = settings.find((setting) => setting.key === key);
  if (item === undefined) return undefined;
  return typeof item.value === "number" ? item.value : Number(item.value);
}

export function findSettingRawValue(
  settings: SettingItem[] | undefined,
  key: string,
): unknown {
  if (!settings) return undefined;
  return settings.find((setting) => setting.key === key)?.value;
}

export function getNotificationScheduleFromSettings(
  settings: SettingItem[] | undefined,
): NotificationScheduleConfig {
  const raw = findSettingRawValue(settings, NOTIFICATION_SCHEDULE_SETTING_KEY);
  return parseNotificationSchedule(raw);
}

export function getDefaultNotificationSchedule(): NotificationScheduleConfig {
  return { ...DEFAULT_NOTIFICATION_SCHEDULE };
}
