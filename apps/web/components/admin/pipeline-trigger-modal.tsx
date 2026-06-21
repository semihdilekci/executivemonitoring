"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { isApiError } from "@/types/api";

interface PipelineTriggerModalProps {
  isOpen: boolean;
  isSubmitting?: boolean;
  onClose: () => void;
  /** Seçili kaynak tipleriyle tetikler; hata fırlatırsa banner gösterilir. */
  onSubmit: (sourceTypes: string[]) => Promise<void>;
}

/** Seçilebilir somut kaynak tipleri (`Docs/06` S-ADMIN-PIPELINE-TRIGGER). */
const SELECTABLE_SOURCES: { value: string; label: string }[] = [
  { value: "gov", label: "Resmi Kaynaklar" },
  { value: "rss", label: "RSS" },
  { value: "email", label: "E-posta" },
];

function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.code === "PIPELINE_ALREADY_RUNNING") {
      return "Halihazırda çalışan bir pipeline var. Bitmesini bekleyin.";
    }
    return error.message;
  }
  return "Pipeline başlatılırken bir hata oluştu.";
}

export function PipelineTriggerModal({
  isOpen,
  isSubmitting = false,
  onClose,
  onSubmit,
}: PipelineTriggerModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [allSelected, setAllSelected] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setSelected(new Set());
    setAllSelected(false);
    setFormError(null);
    setValidationError(null);
  }, [isOpen]);

  const toggleSource = (value: string) => {
    setValidationError(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setValidationError(null);
    setAllSelected((prev) => {
      const next = !prev;
      if (next) setSelected(new Set());
      return next;
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    const sourceTypes = allSelected ? ["all"] : Array.from(selected);
    if (sourceTypes.length === 0) {
      setValidationError("En az bir kaynak seçmelisiniz.");
      return;
    }
    if (isSubmitting) return;

    try {
      await onSubmit(sourceTypes);
    } catch (error) {
      setFormError(getErrorMessage(error));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Yeni Pipeline Başlat">
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        {formError ? <FormErrorBanner message={formError} /> : null}

        <p className="text-sm text-gray-600">
          Seçilen kaynaklardan veri toplama → işleme → bülten üretim süreci
          başlatılır. İşlem birkaç dakika sürebilir.
        </p>

        <fieldset className="space-y-2" disabled={isSubmitting}>
          <legend className="text-sm font-medium text-gray-700">Kaynaklar</legend>
          {SELECTABLE_SOURCES.map((source) => (
            <label
              key={source.value}
              className="flex items-center gap-2.5 rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-800 has-[:disabled]:opacity-50"
            >
              <input
                type="checkbox"
                checked={selected.has(source.value)}
                disabled={allSelected || isSubmitting}
                onChange={() => toggleSource(source.value)}
                className="h-4 w-4 rounded border-gray-300 text-navy-600 focus-visible:ring-navy-600"
              />
              {source.label}
            </label>
          ))}
          <label className="flex items-center gap-2.5 rounded-md border border-gray-200 px-3 py-2 text-sm font-medium text-gray-900">
            <input
              type="checkbox"
              checked={allSelected}
              disabled={isSubmitting}
              onChange={toggleAll}
              className="h-4 w-4 rounded border-gray-300 text-navy-600 focus-visible:ring-navy-600"
            />
            Tümü (tüm aktif kaynaklar)
          </label>
        </fieldset>

        {validationError ? (
          <p className="text-sm text-red-500">{validationError}</p>
        ) : null}

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
