"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  findSettingValue,
  useSettings,
  useUpdateSetting,
} from "@/hooks/use-notifications";
import { isApiError } from "@/types/api";

const TRANSLATION_MIN_SCORE_KEY = "translation_min_relevance_score";
const DEFAULT_SCORE = 75;

type Status = { kind: "success" | "error"; message: string } | null;

/**
 * Çeviri eşiği ayarı — İngilizce haberlerin TR'ye çevrilmesi için minimum
 * relevance skoru (0–100, `Docs/03` §11). `useUpdateSetting` ile kaydeder.
 */
export function TranslationSettingsForm() {
  const settingsQuery = useSettings();
  const updateSetting = useUpdateSetting();

  const serverValue = findSettingValue(settingsQuery.data, TRANSLATION_MIN_SCORE_KEY);
  const [value, setValue] = useState<string>(String(DEFAULT_SCORE));
  const [status, setStatus] = useState<Status>(null);

  // Sunucu değeri yüklendiğinde input'u senkronla.
  useEffect(() => {
    if (serverValue !== undefined) setValue(String(serverValue));
  }, [serverValue]);

  const handleSave = async () => {
    setStatus(null);
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 100) {
      setStatus({ kind: "error", message: "Değer 0–100 aralığında tam sayı olmalıdır." });
      return;
    }

    try {
      await updateSetting.mutateAsync({
        key: TRANSLATION_MIN_SCORE_KEY,
        body: { value: parsed },
      });
      setStatus({ kind: "success", message: "Çeviri eşiği güncellendi." });
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Çeviri eşiği kaydedilirken bir hata oluştu.";
      setStatus({ kind: "error", message });
    }
  };

  return (
    <section className="space-y-4 border-t border-gray-200 pt-8">
      <div>
        <h2 className="text-xl font-bold text-navy-800">Çeviri Ayarı</h2>
        <p className="mt-1 text-sm text-gray-500">
          İngilizce haberler bu relevance skorunun üzerindeyse ingest sırasında
          Türkçeye çevrilir.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <Input
            label="Minimum skor (0–100)"
            name="translation_min_relevance_score"
            type="number"
            min={0}
            max={100}
            value={value}
            disabled={settingsQuery.isLoading}
            onChange={(event) => setValue(event.target.value)}
          />
        </div>
        <Button
          type="button"
          disabled={updateSetting.isPending || settingsQuery.isLoading}
          onClick={() => void handleSave()}
        >
          {updateSetting.isPending ? "Kaydediliyor…" : "Kaydet"}
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
