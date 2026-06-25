"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { RequestTypeScopeSelector } from "@/components/admin/request-type-scope-selector";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_PROVIDER_LABELS } from "@/lib/api-labels";
import { PROVIDER_MODELS, defaultModelFor } from "@/lib/llm-models";
import type {
  ApiProvider,
  ApiKeyItem,
  CreateApiKeyRequest,
  LlmRequestType,
} from "@/types/api";
import { isApiError } from "@/types/api";

interface ApiKeyFormModalProps {
  isOpen: boolean;
  existingKeys: ApiKeyItem[];
  isSubmitting?: boolean;
  onClose: () => void;
  onCreate: (values: CreateApiKeyRequest) => Promise<void>;
}

const PROVIDERS: ApiProvider[] = ["groq", "gemini", "anthropic"];

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "API anahtarı eklenirken bir hata oluştu.";
}

export function ApiKeyFormModal({
  isOpen,
  existingKeys,
  isSubmitting = false,
  onClose,
  onCreate,
}: ApiKeyFormModalProps) {
  const [provider, setProvider] = useState<ApiProvider>("groq");
  const [model, setModel] = useState<string>(defaultModelFor("groq"));
  const [keyAlias, setKeyAlias] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [priorityOrder, setPriorityOrder] = useState(1);
  const [scope, setScope] = useState<LlmRequestType[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const nextPriority =
      existingKeys.length > 0
        ? Math.max(...existingKeys.map((item) => item.priority_order)) + 1
        : 1;

    setProvider("groq");
    setModel(defaultModelFor("groq"));
    setKeyAlias("");
    setApiKey("");
    setPriorityOrder(nextPriority);
    setScope([]);
    setFormError(null);
  }, [isOpen, existingKeys]);

  // Sağlayıcı değişince model listesi değişir; o sağlayıcının varsayılanına dön.
  const handleProviderChange = (next: ApiProvider) => {
    setProvider(next);
    setModel(defaultModelFor(next));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);

    const trimmedAlias = keyAlias.trim();
    const trimmedKey = apiKey.trim();

    if (!trimmedAlias) {
      setFormError("Etiket alanı zorunludur.");
      return;
    }

    if (trimmedKey.length < 8) {
      setFormError("API anahtarı en az 8 karakter olmalıdır.");
      return;
    }

    try {
      await onCreate({
        provider,
        key_alias: trimmedAlias,
        api_key: trimmedKey,
        model,
        priority_order: priorityOrder,
        is_active: true,
        request_type_scope: scope,
      });
      setApiKey("");
    } catch (error) {
      setFormError(getFormErrorMessage(error));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="API Anahtarı Ekle">
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
        {formError ? <FormErrorBanner message={formError} /> : null}

        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          API anahtarı yalnızca bir kez girilir ve sunucuda şifrelenerek saklanır.
          Kayıt sonrası tam değer tekrar gösterilmez.
        </div>

        <div className="space-y-1.5">
          <label htmlFor="provider" className="block text-sm font-medium text-gray-700">
            Sağlayıcı
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(event) => handleProviderChange(event.target.value as ApiProvider)}
            className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
          >
            {PROVIDERS.map((item) => (
              <option key={item} value={item}>
                {API_PROVIDER_LABELS[item]}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="model" className="block text-sm font-medium text-gray-700">
            Model
          </label>
          <select
            id="model"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
          >
            {PROVIDER_MODELS[provider].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>

        <Input
          label="Etiket"
          name="key_alias"
          value={keyAlias}
          onChange={(event) => setKeyAlias(event.target.value)}
          placeholder="Groq Primary"
          required
        />

        <Input
          label="API anahtarı"
          name="api_key"
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          required
        />

        <Input
          label="Öncelik sırası"
          name="priority_order"
          type="number"
          min={1}
          max={1000}
          value={String(priorityOrder)}
          onChange={(event) =>
            setPriorityOrder(Number.parseInt(event.target.value, 10) || 1)
          }
        />

        <RequestTypeScopeSelector value={scope} onChange={setScope} />

        <div className="flex justify-end gap-3 border-t border-gray-100 pt-4">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
