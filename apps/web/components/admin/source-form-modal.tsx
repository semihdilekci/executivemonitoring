"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  getDefaultConfigJson,
  maskSensitiveConfigFields,
  parseConfigJson,
  validateSourceConfig,
} from "@/lib/source-config";
import {
  MVP_SOURCE_TYPES,
  POLLING_INTERVAL_OPTIONS,
  SOURCE_CATEGORY_LABELS,
  SOURCE_CONFIG_HINTS,
  SOURCE_TYPE_LABELS,
} from "@/lib/source-labels";
import type {
  CreateSourceRequest,
  SourceCategory,
  SourceListItem,
  SourceType,
  UpdateSourceRequest,
} from "@/types/api";
import { isApiError } from "@/types/api";

type SourceFormMode = "create" | "edit";

interface SourceFormModalProps {
  mode: SourceFormMode;
  source?: SourceListItem;
  isOpen: boolean;
  isSubmitting?: boolean;
  onClose: () => void;
  onCreate: (values: CreateSourceRequest) => Promise<void>;
  onUpdate: (values: UpdateSourceRequest) => Promise<void>;
}

const SOURCE_CATEGORIES = Object.keys(
  SOURCE_CATEGORY_LABELS,
) as SourceCategory[];

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.code === "VALIDATION_ERROR") {
      const fields = error.details?.fields;
      if (Array.isArray(fields) && fields.length > 0) {
        return fields.join(" ");
      }
    }
    return error.message;
  }
  return "İşlem sırasında bir hata oluştu.";
}

export function SourceFormModal({
  mode,
  source,
  isOpen,
  isSubmitting = false,
  onClose,
  onCreate,
  onUpdate,
}: SourceFormModalProps) {
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("rss");
  const [category, setCategory] = useState<SourceCategory>("fmcg");
  const [pollingInterval, setPollingInterval] = useState(15);
  const [targetPhase, setTargetPhase] = useState("mvp-0");
  const [configJson, setConfigJson] = useState(getDefaultConfigJson("rss"));
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!isOpen) return;

    if (mode === "edit" && source) {
      setName(source.name);
      setSourceType(source.source_type);
      setCategory(source.category);
      setPollingInterval(source.polling_interval_minutes);
      setTargetPhase(source.target_phase);
      setConfigJson(
        JSON.stringify(maskSensitiveConfigFields(source.config), null, 2),
      );
    } else {
      setName("");
      setSourceType("rss");
      setCategory("fmcg");
      setPollingInterval(15);
      setTargetPhase("mvp-0");
      setConfigJson(getDefaultConfigJson("rss"));
    }
    setFormError(null);
    setFieldErrors({});
  }, [isOpen, mode, source]);

  const handleTypeChange = (nextType: SourceType) => {
    setSourceType(nextType);
    if (mode === "create") {
      setConfigJson(getDefaultConfigJson(nextType));
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim() || name.trim().length < 2) {
      errors.name = "Kaynak adı en az 2 karakter olmalı.";
    }

    const { config, error: jsonError } = parseConfigJson(configJson);
    if (jsonError || !config) {
      errors.config = jsonError ?? "Geçersiz yapılandırma.";
    } else {
      const configErrors = validateSourceConfig(sourceType, config);
      if (configErrors.length > 0) {
        errors.config = configErrors.join(" ");
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!validate() || isSubmitting) return;

    const { config } = parseConfigJson(configJson);
    if (!config) return;

    try {
      if (mode === "create") {
        await onCreate({
          name: name.trim(),
          source_type: sourceType,
          config,
          polling_interval_minutes: pollingInterval,
          category,
          target_phase: targetPhase.trim(),
        });
      } else {
        await onUpdate({
          name: name.trim(),
          config,
          polling_interval_minutes: pollingInterval,
          category,
          target_phase: targetPhase.trim(),
        });
      }
    } catch (error) {
      setFormError(getFormErrorMessage(error));
    }
  };

  const title = mode === "create" ? "Kaynak Ekle" : "Kaynak Düzenle";
  const submitLabel = mode === "create" ? "Kaydet" : "Güncelle";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        {formError ? <FormErrorBanner message={formError} /> : null}

        <Input
          label="Kaynak Adı"
          name="name"
          type="text"
          value={name}
          disabled={isSubmitting}
          error={fieldErrors.name}
          onChange={(event) => setName(event.target.value)}
        />

        <div className="space-y-1.5">
          <label htmlFor="source-type" className="block text-sm font-medium text-gray-700">
            Kaynak Tipi
          </label>
          <select
            id="source-type"
            name="source_type"
            value={sourceType}
            disabled={isSubmitting || mode === "edit"}
            onChange={(event) =>
              handleTypeChange(event.target.value as SourceType)
            }
            className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:opacity-70"
          >
            {MVP_SOURCE_TYPES.map((type) => (
              <option key={type} value={type}>
                {SOURCE_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
          {mode === "edit" ? (
            <p className="text-xs text-gray-500">Kaynak tipi oluşturulduktan sonra değiştirilemez.</p>
          ) : null}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="category" className="block text-sm font-medium text-gray-700">
              Kategori
            </label>
            <select
              id="category"
              name="category"
              value={category}
              disabled={isSubmitting}
              onChange={(event) =>
                setCategory(event.target.value as SourceCategory)
              }
              className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {SOURCE_CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {SOURCE_CATEGORY_LABELS[item]}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="polling-interval"
              className="block text-sm font-medium text-gray-700"
            >
              Tarama Aralığı
            </label>
            <select
              id="polling-interval"
              name="polling_interval_minutes"
              value={pollingInterval}
              disabled={isSubmitting}
              onChange={(event) =>
                setPollingInterval(Number(event.target.value))
              }
              className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {POLLING_INTERVAL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <Input
          label="Hedef Faz"
          name="target_phase"
          type="text"
          value={targetPhase}
          disabled={isSubmitting}
          onChange={(event) => setTargetPhase(event.target.value)}
        />

        <div className="space-y-1.5">
          <label htmlFor="config-json" className="block text-sm font-medium text-gray-700">
            Yapılandırma (JSON)
          </label>
          <p className="text-xs text-gray-500">{SOURCE_CONFIG_HINTS[sourceType]}</p>
          <textarea
            id="config-json"
            name="config"
            rows={10}
            value={configJson}
            disabled={isSubmitting}
            onChange={(event) => setConfigJson(event.target.value)}
            spellCheck={false}
            className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
          />
          {fieldErrors.config ? (
            <p className="text-sm text-red-500">{fieldErrors.config}</p>
          ) : null}
          <p className="text-xs text-gray-500">
            API anahtarı gibi hassas alanlar sunucuda şifrelenir; yanıtta maskelenir.
          </p>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
          >
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? "Kaydediliyor…" : submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
