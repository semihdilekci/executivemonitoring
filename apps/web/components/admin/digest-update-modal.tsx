"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DIGEST_TYPE_META } from "@/lib/digest-labels";
import { isApiError } from "@/types/api";
import type { DigestType } from "@/types/api";

interface DigestUpdateModalProps {
  isOpen: boolean;
  isSubmitting?: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    digest_type: DigestType;
    period_start: string;
    period_end: string;
    send_notification: boolean;
  }) => Promise<void>;
}

const DIGEST_TYPES = Object.keys(DIGEST_TYPE_META) as DigestType[];

function toISODate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function defaultPeriod(): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 6);
  return { start: toISODate(start), end: toISODate(end) };
}

function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.code === "PIPELINE_ALREADY_RUNNING") {
      return "Halihazırda çalışan bir bülten güncellemesi var. Bitmesini bekleyin.";
    }
    return error.message;
  }
  return "Bülten güncelleme başlatılırken bir hata oluştu.";
}

export function DigestUpdateModal({
  isOpen,
  isSubmitting = false,
  onClose,
  onSubmit,
}: DigestUpdateModalProps) {
  const [digestType, setDigestType] = useState<DigestType>("turkish_media_weekly");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [sendNotification, setSendNotification] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const period = defaultPeriod();
    setDigestType("turkish_media_weekly");
    setPeriodStart(period.start);
    setPeriodEnd(period.end);
    setSendNotification(true);
    setFormError(null);
    setFieldError(null);
  }, [isOpen]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!periodStart || !periodEnd) {
      setFieldError("Başlangıç ve bitiş tarihi zorunludur.");
      return;
    }
    if (periodEnd < periodStart) {
      setFieldError("Bitiş tarihi başlangıçtan önce olamaz.");
      return;
    }
    if (isSubmitting) return;

    try {
      await onSubmit({
        digest_type: digestType,
        period_start: periodStart,
        period_end: periodEnd,
        send_notification: sendNotification,
      });
    } catch (error) {
      setFormError(getErrorMessage(error));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Bülten Güncelle">
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        {formError ? <FormErrorBanner message={formError} /> : null}

        <p className="text-sm text-gray-600">
          Seçili dönem için bülten yeniden üretilir. Bildirim gönderimi
          isteğe bağlıdır.
        </p>

        <div className="space-y-1.5">
          <label htmlFor="digest-type" className="block text-sm font-medium text-gray-700">
            Bülten Tipi
          </label>
          <select
            id="digest-type"
            value={digestType}
            disabled={isSubmitting}
            onChange={(event) => setDigestType(event.target.value as DigestType)}
            className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
          >
            {DIGEST_TYPES.map((type) => (
              <option key={type} value={type}>
                {DIGEST_TYPE_META[type].label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Dönem Başlangıcı"
            name="period_start"
            type="date"
            value={periodStart}
            disabled={isSubmitting}
            onChange={(event) => {
              setFieldError(null);
              setPeriodStart(event.target.value);
            }}
          />
          <Input
            label="Dönem Bitişi"
            name="period_end"
            type="date"
            value={periodEnd}
            disabled={isSubmitting}
            onChange={(event) => {
              setFieldError(null);
              setPeriodEnd(event.target.value);
            }}
          />
        </div>

        {fieldError ? <p className="text-sm text-red-500">{fieldError}</p> : null}

        <label className="flex items-center gap-2.5 text-sm text-gray-800">
          <input
            type="checkbox"
            checked={sendNotification}
            disabled={isSubmitting}
            onChange={(event) => setSendNotification(event.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-navy-600 focus-visible:ring-navy-600"
          />
          Hazır olunca bildirim gönder
        </label>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? "Başlatılıyor…" : "Başlat"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
