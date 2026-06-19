"use client";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  CHATBOT_RATE_LIMIT_KEY,
  CHATBOT_TEMPERATURE_KEY,
  JWT_ACCESS_TOKEN_KEY,
  JWT_REFRESH_TOKEN_KEY,
  findSettingValue,
  getNotificationScheduleFromSettings,
} from "@/hooks/use-notifications";
import {
  NOTIFICATION_SCHEDULE_ROWS,
  SCHEDULE_DAY_OPTIONS,
  type ScheduleDigestKey,
} from "@/lib/notification-schedule";
import { cn } from "@/lib/utils";
import type {
  NotificationPreferenceItem,
  NotificationRecipientItem,
  NotificationRecipientType,
  NotificationScheduleConfig,
  SettingItem,
  UserListItem,
} from "@/types/api";
import { useEffect, useMemo, useState } from "react";

interface NotificationSettingsFormProps {
  recipients: NotificationRecipientItem[];
  recipientsApiSupported: boolean;
  users: UserListItem[];
  preferences: NotificationPreferenceItem[];
  settings: SettingItem[] | undefined;
  isSavingRecipient: boolean;
  isDeletingRecipient: boolean;
  isSavingPreference: boolean;
  isSavingSettings: boolean;
  onAddRecipient: (userId: string, types: NotificationRecipientType[]) => Promise<void>;
  onRemoveRecipient: (recipientId: string) => Promise<void>;
  onTogglePreference: (
    userId: string,
    field: "email_enabled" | "push_enabled",
    value: boolean,
  ) => void;
  onSaveSchedule: (schedule: NotificationScheduleConfig) => Promise<void>;
  onSaveSessionSettings: (values: {
    accessMinutes: number;
    refreshDays: number;
    chatRateLimit: number;
    chatTemperature: number;
  }) => Promise<void>;
}

const RECIPIENT_TYPE_LABELS: Record<NotificationRecipientType, string> = {
  digest: "Digest",
  error_alert: "Hata Bildirimi",
};

function ToggleSwitch({
  id,
  label,
  checked,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label
      htmlFor={id}
      className={cn(
        "inline-flex cursor-pointer items-center gap-2",
        disabled && "cursor-not-allowed opacity-60",
      )}
    >
      <input
        id={id}
        type="checkbox"
        className="sr-only"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors",
          checked ? "bg-navy-700" : "bg-gray-200",
        )}
        aria-hidden
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
            checked ? "translate-x-5" : "translate-x-0.5",
          )}
        />
      </span>
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}

function RecipientTypeChip({
  type,
  active,
  disabled,
  onToggle,
}: {
  type: NotificationRecipientType;
  active: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={active}
      onClick={onToggle}
      className={cn(
        "rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors disabled:opacity-50",
        active
          ? "border-navy-700 bg-navy-700 text-white"
          : "border-gray-200 bg-white text-gray-600 hover:border-gray-300",
      )}
    >
      {RECIPIENT_TYPE_LABELS[type]}
    </button>
  );
}

export function NotificationSettingsForm({
  recipients,
  recipientsApiSupported,
  users,
  preferences,
  settings,
  isSavingRecipient,
  isDeletingRecipient,
  isSavingPreference,
  isSavingSettings,
  onAddRecipient,
  onRemoveRecipient,
  onTogglePreference,
  onSaveSchedule,
  onSaveSessionSettings,
}: NotificationSettingsFormProps) {
  const accessDefault = findSettingValue(settings, JWT_ACCESS_TOKEN_KEY) ?? 60;
  const refreshDefault = findSettingValue(settings, JWT_REFRESH_TOKEN_KEY) ?? 30;
  const chatRateDefault = findSettingValue(settings, CHATBOT_RATE_LIMIT_KEY) ?? 20;
  const chatTempDefault =
    findSettingValue(settings, CHATBOT_TEMPERATURE_KEY) ?? 0.7;

  const [accessMinutes, setAccessMinutes] = useState(String(accessDefault));
  const [refreshDays, setRefreshDays] = useState(String(refreshDefault));
  const [chatRateLimit, setChatRateLimit] = useState(String(chatRateDefault));
  const [chatTemperature, setChatTemperature] = useState(String(chatTempDefault));
  const [schedule, setSchedule] = useState<NotificationScheduleConfig>(() =>
    getNotificationScheduleFromSettings(settings),
  );
  const [showJwtConfirm, setShowJwtConfirm] = useState(false);
  const [showAddRecipient, setShowAddRecipient] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [newRecipientTypes, setNewRecipientTypes] = useState<
    NotificationRecipientType[]
  >(["digest"]);

  useEffect(() => {
    setAccessMinutes(String(accessDefault));
    setRefreshDays(String(refreshDefault));
    setChatRateLimit(String(chatRateDefault));
    setChatTemperature(String(chatTempDefault));
    setSchedule(getNotificationScheduleFromSettings(settings));
  }, [
    accessDefault,
    refreshDefault,
    chatRateDefault,
    chatTempDefault,
    settings,
  ]);

  const parsedAccess = Number.parseInt(accessMinutes, 10);
  const parsedRefresh = Number.parseInt(refreshDays, 10);
  const parsedChatRate = Number.parseInt(chatRateLimit, 10);
  const parsedChatTemp = Number.parseFloat(chatTemperature);

  const sessionFormValid =
    Number.isFinite(parsedAccess) &&
    parsedAccess >= 5 &&
    parsedAccess <= 1440 &&
    Number.isFinite(parsedRefresh) &&
    parsedRefresh >= 1 &&
    parsedRefresh <= 365 &&
    Number.isFinite(parsedChatRate) &&
    parsedChatRate >= 1 &&
    parsedChatRate <= 120 &&
    Number.isFinite(parsedChatTemp) &&
    parsedChatTemp >= 0 &&
    parsedChatTemp <= 2;

  const sessionDirty =
    parsedAccess !== accessDefault ||
    parsedRefresh !== refreshDefault ||
    parsedChatRate !== chatRateDefault ||
    parsedChatTemp !== chatTempDefault;

  const savedSchedule = useMemo(
    () => getNotificationScheduleFromSettings(settings),
    [settings],
  );

  const scheduleDirty = useMemo(
    () => JSON.stringify(schedule) !== JSON.stringify(savedSchedule),
    [schedule, savedSchedule],
  );

  const availableUsers = users.filter(
    (user) => !recipients.some((recipient) => recipient.user_id === user.id),
  );

  const updateScheduleRow = (
    key: ScheduleDigestKey,
    patch: Partial<NotificationScheduleConfig[string]>,
  ) => {
    setSchedule((current) => ({
      ...current,
      [key]: { ...current[key], ...patch },
    }));
  };

  const toggleNewRecipientType = (type: NotificationRecipientType) => {
    setNewRecipientTypes((current) =>
      current.includes(type)
        ? current.filter((item) => item !== type)
        : [...current, type],
    );
  };

  const handleAddRecipient = async () => {
    if (!selectedUserId || newRecipientTypes.length === 0) return;
    await onAddRecipient(selectedUserId, newRecipientTypes);
    setShowAddRecipient(false);
    setSelectedUserId("");
    setNewRecipientTypes(["digest"]);
  };

  const handleSessionSave = async () => {
    if (!sessionFormValid) return;
    await onSaveSessionSettings({
      accessMinutes: parsedAccess,
      refreshDays: parsedRefresh,
      chatRateLimit: parsedChatRate,
      chatTemperature: parsedChatTemp,
    });
    setShowJwtConfirm(false);
  };

  return (
    <div className="space-y-6">
      <Card>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-navy-800">
              Mail Alıcı Listesi
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Digest ve hata bildirimleri için e-posta alıcılarını yönetin.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            disabled={!recipientsApiSupported || isSavingRecipient}
            onClick={() => setShowAddRecipient(true)}
          >
            Alıcı Ekle
          </Button>
        </div>

        {!recipientsApiSupported ? (
          <p className="rounded-lg border border-dashed border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Mail alıcı API&apos;si henüz aktif değil. Backend endpoint merge
            edildiğinde bu bölüm otomatik çalışacaktır.
          </p>
        ) : null}

        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50/80">
              <tr>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Kullanıcı
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  E-posta
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Bildirim Tipleri
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  İşlem
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recipients.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-center text-sm text-gray-500"
                  >
                    Henüz mail alıcısı eklenmemiş.
                  </td>
                </tr>
              ) : (
                recipients.map((recipient) => (
                  <tr key={recipient.id} className="hover:bg-gray-50/60">
                    <td className="px-4 py-3 font-medium text-gray-800">
                      {recipient.user_name}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{recipient.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {recipient.types.map((type) => (
                          <span
                            key={type}
                            className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-xs font-semibold text-gray-700"
                          >
                            {RECIPIENT_TYPE_LABELS[type]}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:bg-red-50 hover:text-red-700"
                        disabled={isDeletingRecipient}
                        onClick={() => void onRemoveRecipient(recipient.id)}
                      >
                        Kaldır
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-navy-800">
            Bildirim Zamanlaması
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Digest tiplerine göre gönderim günü ve saatini yapılandırın.
          </p>
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50/80">
              <tr>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Digest Tipi
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Gün
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Saat
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Durum
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {NOTIFICATION_SCHEDULE_ROWS.map((row) => {
                const entry = schedule[row.key];
                return (
                  <tr key={row.key}>
                    <td className="px-4 py-3 font-medium text-gray-800">
                      {row.label}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        aria-label={`${row.label} günü`}
                        value={entry.day}
                        onChange={(event) =>
                          updateScheduleRow(row.key, { day: event.target.value })
                        }
                        className="w-full min-w-[140px] rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm"
                      >
                        {SCHEDULE_DAY_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="time"
                        aria-label={`${row.label} saati`}
                        value={entry.time}
                        onChange={(event) =>
                          updateScheduleRow(row.key, { time: event.target.value })
                        }
                        className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <ToggleSwitch
                        id={`schedule-${row.key}`}
                        label={entry.enabled ? "Aktif" : "Pasif"}
                        checked={entry.enabled}
                        onChange={(value) =>
                          updateScheduleRow(row.key, { enabled: value })
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            disabled={!scheduleDirty || isSavingSettings}
            onClick={() => void onSaveSchedule(schedule)}
          >
            Değişiklikleri Kaydet
          </Button>
        </div>
      </Card>

      <Card>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-navy-800">
            Oturum ve Chatbot Ayarları
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            JWT token süreleri ve chatbot parametrelerini yapılandırın.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Input
              label="Access token süresi (dakika)"
              name="jwt_access_minutes"
              type="number"
              min={5}
              max={1440}
              value={accessMinutes}
              onChange={(event) => setAccessMinutes(event.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">Min: 5, Max: 1440</p>
          </div>
          <div>
            <Input
              label="Refresh token süresi (gün)"
              name="jwt_refresh_days"
              type="number"
              min={1}
              max={365}
              value={refreshDays}
              onChange={(event) => setRefreshDays(event.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">Min: 1, Max: 365</p>
          </div>
          <div>
            <Input
              label="Chatbot rate limit (istek/dk)"
              name="chatbot_rate_limit"
              type="number"
              min={1}
              max={120}
              value={chatRateLimit}
              onChange={(event) => setChatRateLimit(event.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">Min: 1, Max: 120</p>
          </div>
          <div>
            <Input
              label="Chatbot temperature"
              name="chatbot_temperature"
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={chatTemperature}
              onChange={(event) => setChatTemperature(event.target.value)}
            />
            <p className="mt-1 text-xs text-gray-500">Min: 0, Max: 2</p>
          </div>
        </div>

        <p className="mt-3 text-xs text-amber-700">
          JWT ayarları mevcut oturumları etkilemez. Chatbot ayarları backend
          seed&apos;inde tanımlı değilse kayıt başarısız olabilir.
        </p>

        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            disabled={!sessionDirty || !sessionFormValid || isSavingSettings}
            onClick={() => setShowJwtConfirm(true)}
          >
            Değişiklikleri Kaydet
          </Button>
        </div>
      </Card>

      {preferences.length > 0 ? (
        <Card>
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-navy-800">
              Kullanıcı Bildirim Tercihleri
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Kullanıcıların e-posta ve push bildirim tercihlerini yönetin.
            </p>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50/80">
                <tr>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
                    Kullanıcı
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
                    E-posta
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
                    Push
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
                    FCM
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {preferences.map((pref) => (
                  <tr key={pref.user_id} className="hover:bg-gray-50/60">
                    <td className="px-4 py-3 font-medium text-gray-800">
                      {pref.user_name}
                    </td>
                    <td className="px-4 py-3">
                      <ToggleSwitch
                        id={`email-${pref.user_id}`}
                        label="E-posta"
                        checked={pref.email_enabled}
                        disabled={isSavingPreference}
                        onChange={(value) =>
                          onTogglePreference(pref.user_id, "email_enabled", value)
                        }
                      />
                    </td>
                    <td className="px-4 py-3">
                      <ToggleSwitch
                        id={`push-${pref.user_id}`}
                        label="Push"
                        checked={pref.push_enabled}
                        disabled={isSavingPreference}
                        onChange={(value) =>
                          onTogglePreference(pref.user_id, "push_enabled", value)
                        }
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold",
                          pref.has_fcm_token
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-gray-100 text-gray-500",
                        )}
                      >
                        {pref.has_fcm_token ? "Kayıtlı" : "Yok"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {showAddRecipient ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-navy-800">Alıcı Ekle</h3>
            <div className="mt-4 space-y-4">
              <div>
                <label
                  htmlFor="recipient-user"
                  className="mb-1 block text-sm font-medium text-gray-700"
                >
                  Kullanıcı
                </label>
                <select
                  id="recipient-user"
                  value={selectedUserId}
                  onChange={(event) => setSelectedUserId(event.target.value)}
                  className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm"
                >
                  <option value="">Kullanıcı seçin…</option>
                  {availableUsers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name} ({user.email})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-gray-700">
                  Bildirim tipleri
                </p>
                <div className="flex flex-wrap gap-2">
                  {(Object.keys(RECIPIENT_TYPE_LABELS) as NotificationRecipientType[]).map(
                    (type) => (
                      <RecipientTypeChip
                        key={type}
                        type={type}
                        active={newRecipientTypes.includes(type)}
                        onToggle={() => toggleNewRecipientType(type)}
                      />
                    ),
                  )}
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowAddRecipient(false)}
              >
                İptal
              </Button>
              <Button
                type="button"
                disabled={
                  !selectedUserId ||
                  newRecipientTypes.length === 0 ||
                  isSavingRecipient
                }
                onClick={() => void handleAddRecipient()}
              >
                Ekle
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        isOpen={showJwtConfirm}
        title="Oturum ayarlarını değiştir"
        message="JWT ve chatbot ayarlarını değiştirmek üzeresiniz. Devam etmek istiyor musunuz?"
        confirmLabel="Kaydet"
        variant="primary"
        isLoading={isSavingSettings}
        onConfirm={() => void handleSessionSave()}
        onCancel={() => setShowJwtConfirm(false)}
      />
    </div>
  );
}
