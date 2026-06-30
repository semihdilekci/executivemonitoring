"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  findSettingRawValue,
  useSettings,
  useUpdateSetting,
} from "@/hooks/use-notifications";
import { isApiError } from "@/types/api";

const IMPACT_SYSTEM_KEY = "newsletter_impact_system_prompt";
const IMPACT_USER_KEY = "newsletter_impact_user_prompt";

const textareaClass =
  "w-full rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600";

type Status = { kind: "success" | "error"; message: string } | null;

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * Global "Yıldız'ı nasıl etkiler?" (anlık etki analizi) prompt editörü.
 * `newsletter_impact_system_prompt` ve `newsletter_impact_user_prompt`
 * system_settings kayıtlarını `useUpdateSetting` ile günceller (Faz 6.5).
 */
export function NewsletterImpactSettingsForm() {
  const settingsQuery = useSettings();
  const updateSetting = useUpdateSetting();

  const serverSystem = asString(
    findSettingRawValue(settingsQuery.data, IMPACT_SYSTEM_KEY),
  );
  const serverUser = asString(
    findSettingRawValue(settingsQuery.data, IMPACT_USER_KEY),
  );

  const [systemPrompt, setSystemPrompt] = useState<string>("");
  const [userPrompt, setUserPrompt] = useState<string>("");
  const [status, setStatus] = useState<Status>(null);

  // Sunucu değerleri yüklendiğinde alanları senkronla.
  useEffect(() => {
    setSystemPrompt(serverSystem);
  }, [serverSystem]);
  useEffect(() => {
    setUserPrompt(serverUser);
  }, [serverUser]);

  const handleSave = async () => {
    setStatus(null);

    if (!systemPrompt.trim() || !userPrompt.trim()) {
      setStatus({ kind: "error", message: "Her iki prompt da boş olamaz." });
      return;
    }
    if (!userPrompt.includes("{title}") || !userPrompt.includes("{content}")) {
      setStatus({
        kind: "error",
        message:
          "Kullanıcı prompt'u haberin enjekte edilmesi için {title} ve {content} değişkenlerini içermelidir.",
      });
      return;
    }

    const pending: { key: string; value: string }[] = [];
    if (systemPrompt !== serverSystem)
      pending.push({ key: IMPACT_SYSTEM_KEY, value: systemPrompt });
    if (userPrompt !== serverUser)
      pending.push({ key: IMPACT_USER_KEY, value: userPrompt });

    if (pending.length === 0) {
      setStatus({ kind: "success", message: "Değişiklik yok." });
      return;
    }

    try {
      for (const item of pending) {
        await updateSetting.mutateAsync({
          key: item.key,
          body: { value: item.value },
        });
      }
      setStatus({ kind: "success", message: "Etki prompt'ları güncellendi." });
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Prompt'lar kaydedilirken bir hata oluştu.";
      setStatus({ kind: "error", message });
    }
  };

  const handleReset = () => {
    setSystemPrompt(serverSystem);
    setUserPrompt(serverUser);
    setStatus(null);
  };

  const isDirty = systemPrompt !== serverSystem || userPrompt !== serverUser;
  const disabled = settingsQuery.isLoading || updateSetting.isPending;

  return (
    <section className="space-y-4 border-t border-gray-200 pt-8">
      <div>
        <h2 className="text-xl font-bold text-navy-800">
          Yıldız&apos;ı Nasıl Etkiler? Prompt&apos;u
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Bülten haberlerinin altındaki anlık etki analizini üreten global
          prompt. Yanıt düz metin ve kısa olmalı; aşağıdaki metinleri
          değiştirerek davranışı yönetebilirsin.
        </p>
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="impact-system-prompt"
          className="block text-sm font-medium text-gray-700"
        >
          System prompt (modelin rolü ve biçim kuralları)
        </label>
        <textarea
          id="impact-system-prompt"
          rows={5}
          value={systemPrompt}
          disabled={disabled}
          onChange={(event) => setSystemPrompt(event.target.value)}
          className={textareaClass}
        />
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="impact-user-prompt"
          className="block text-sm font-medium text-gray-700"
        >
          User prompt (haber bağlamı + soru)
        </label>
        <textarea
          id="impact-user-prompt"
          rows={6}
          value={userPrompt}
          disabled={disabled}
          onChange={(event) => setUserPrompt(event.target.value)}
          className={textareaClass}
        />
        <p className="text-xs text-gray-500">
          Kullanılabilir değişkenler:{" "}
          <code className="rounded bg-gray-100 px-1">{"{title}"}</code>,{" "}
          <code className="rounded bg-gray-100 px-1">{"{content}"}</code>{" "}
          (haber başlığı ve içeriği bu yerlere yerleştirilir).
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          disabled={disabled || !isDirty}
          onClick={() => void handleSave()}
        >
          {updateSetting.isPending ? "Kaydediliyor…" : "Kaydet"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || !isDirty}
          onClick={handleReset}
        >
          Sıfırla
        </Button>
      </div>

      {status ? (
        <p
          className={
            status.kind === "success"
              ? "text-sm text-emerald-700"
              : "text-sm text-red-700"
          }
          role={status.kind === "error" ? "alert" : "status"}
        >
          {status.message}
        </p>
      ) : null}
    </section>
  );
}
