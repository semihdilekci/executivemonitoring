"use client";

import { useCallback, useState } from "react";
import { NotificationSettingsForm } from "@/components/admin/notification-settings-form";
import { RoleGate } from "@/components/auth/role-gate";
import { ErrorView } from "@/components/common/error-view";
import { NotificationSettingsSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import {
  CHATBOT_RATE_LIMIT_KEY,
  CHATBOT_TEMPERATURE_KEY,
  JWT_ACCESS_TOKEN_KEY,
  JWT_REFRESH_TOKEN_KEY,
  useCreateNotificationRecipient,
  useDeleteNotificationRecipient,
  useNotificationPreferences,
  useNotificationRecipients,
  useSettings,
  useUpdateNotificationPreference,
  useUpdateSetting,
} from "@/hooks/use-notifications";
import { flattenUserPages, useUsers } from "@/hooks/use-users";
import { NOTIFICATION_SCHEDULE_SETTING_KEY } from "@/lib/notification-schedule";
import type { NotificationScheduleConfig } from "@/types/api";
import { isApiError } from "@/types/api";

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminNotificationsPage() {
  const [toast, setToast] = useState<ToastState | null>(null);

  const preferencesQuery = useNotificationPreferences();
  const recipientsQuery = useNotificationRecipients();
  const settingsQuery = useSettings();
  const usersQuery = useUsers({ is_active: true, limit: 100 });
  const updatePreference = useUpdateNotificationPreference();
  const createRecipient = useCreateNotificationRecipient();
  const deleteRecipient = useDeleteNotificationRecipient();
  const updateSetting = useUpdateSetting();

  const isLoading =
    preferencesQuery.isLoading ||
    recipientsQuery.isLoading ||
    settingsQuery.isLoading ||
    usersQuery.isLoading;

  const isError =
    preferencesQuery.isError ||
    recipientsQuery.isError ||
    settingsQuery.isError ||
    usersQuery.isError;

  const showToast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      setToast({ message, variant });
    },
    [],
  );

  const handleTogglePreference = async (
    userId: string,
    field: "email_enabled" | "push_enabled",
    value: boolean,
  ) => {
    const current = preferencesQuery.data?.find((item) => item.user_id === userId);
    if (!current) return;

    try {
      await updatePreference.mutateAsync({
        userId,
        body: {
          email_enabled:
            field === "email_enabled" ? value : current.email_enabled,
          push_enabled: field === "push_enabled" ? value : current.push_enabled,
        },
      });
      showToast("Bildirim tercihi güncellendi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Bildirim tercihi güncellenemedi.";
      showToast(message, "error");
    }
  };

  const handleAddRecipient = async (
    userId: string,
    types: ("digest" | "error_alert")[],
  ) => {
    try {
      await createRecipient.mutateAsync({ user_id: userId, types });
      showToast("Mail alıcısı eklendi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Mail alıcısı eklenemedi.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleRemoveRecipient = async (recipientId: string) => {
    try {
      await deleteRecipient.mutateAsync(recipientId);
      showToast("Mail alıcısı kaldırıldı.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Mail alıcısı kaldırılamadı.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleSaveSchedule = async (schedule: NotificationScheduleConfig) => {
    try {
      await updateSetting.mutateAsync({
        key: NOTIFICATION_SCHEDULE_SETTING_KEY,
        body: { value: schedule },
      });
      showToast("Bildirim zamanlaması kaydedildi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Bildirim zamanlaması kaydedilemedi.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleSaveSessionSettings = async (values: {
    accessMinutes: number;
    refreshDays: number;
    chatRateLimit: number;
    chatTemperature: number;
  }) => {
    try {
      await updateSetting.mutateAsync({
        key: JWT_ACCESS_TOKEN_KEY,
        body: { value: values.accessMinutes },
      });
      const refreshResult = await updateSetting.mutateAsync({
        key: JWT_REFRESH_TOKEN_KEY,
        body: { value: values.refreshDays },
      });

      const chatSettings: Array<{ key: string; value: number }> = [
        { key: CHATBOT_RATE_LIMIT_KEY, value: values.chatRateLimit },
        { key: CHATBOT_TEMPERATURE_KEY, value: values.chatTemperature },
      ];

      for (const setting of chatSettings) {
        try {
          await updateSetting.mutateAsync({
            key: setting.key,
            body: { value: setting.value },
          });
        } catch (innerError) {
          if (isApiError(innerError) && innerError.statusCode === 404) {
            continue;
          }
          throw innerError;
        }
      }

      if (refreshResult.warning) {
        showToast(refreshResult.warning);
      } else {
        showToast("Oturum ve chatbot ayarları kaydedildi.");
      }
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Ayarlar kaydedilemedi.";
      showToast(message, "error");
      throw error;
    }
  };

  const preferences = preferencesQuery.data ?? [];
  const recipients = recipientsQuery.data?.items ?? [];
  const recipientsApiSupported = recipientsQuery.data?.apiSupported ?? false;
  const users = flattenUserPages(usersQuery.data);

  return (
    <RoleGate>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">Bildirim Yönetimi</h1>
          <p className="mt-1 text-sm text-gray-500">
            Mail alıcıları, bildirim zamanlaması ve oturum ayarlarını yönetin.
          </p>
        </div>

        {isLoading ? <NotificationSettingsSkeleton /> : null}

        {isError ? (
          <ErrorView
            onRetry={() => {
              void preferencesQuery.refetch();
              void recipientsQuery.refetch();
              void settingsQuery.refetch();
              void usersQuery.refetch();
            }}
          />
        ) : null}

        {!isLoading && !isError ? (
          <NotificationSettingsForm
            recipients={recipients}
            recipientsApiSupported={recipientsApiSupported}
            users={users}
            preferences={preferences}
            settings={settingsQuery.data}
            isSavingRecipient={createRecipient.isPending}
            isDeletingRecipient={deleteRecipient.isPending}
            isSavingPreference={updatePreference.isPending}
            isSavingSettings={updateSetting.isPending}
            onAddRecipient={handleAddRecipient}
            onRemoveRecipient={handleRemoveRecipient}
            onTogglePreference={(userId, field, value) =>
              void handleTogglePreference(userId, field, value)
            }
            onSaveSchedule={handleSaveSchedule}
            onSaveSessionSettings={handleSaveSessionSettings}
          />
        ) : null}
      </div>

      {toast ? (
        <Toast
          message={toast.message}
          variant={toast.variant}
          onDismiss={() => setToast(null)}
        />
      ) : null}
    </RoleGate>
  );
}
