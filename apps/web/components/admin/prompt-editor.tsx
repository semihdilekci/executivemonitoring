"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DIGEST_TYPE_FILTERS } from "@/lib/digest-labels";
import type {
  ApiProvider,
  CreatePromptTemplateRequest,
  DigestType,
  PromptTemplateItem,
  UpdatePromptTemplateRequest,
} from "@/types/api";
import { isApiError } from "@/types/api";

type PromptEditorMode = "create" | "edit";

interface PromptEditorProps {
  mode: PromptEditorMode;
  template?: PromptTemplateItem;
  isOpen: boolean;
  isSubmitting?: boolean;
  onClose: () => void;
  onCreate: (values: CreatePromptTemplateRequest) => Promise<void>;
  onUpdate: (values: UpdatePromptTemplateRequest) => Promise<void>;
}

const DIGEST_TYPE_OPTIONS = DIGEST_TYPE_FILTERS.filter(
  (item) => item.value !== "all",
) as { value: DigestType; label: string }[];

const MODEL_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Varsayılan (otomatik)" },
  { value: "groq", label: "Groq" },
  { value: "gemini", label: "Gemini" },
];

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "İşlem sırasında bir hata oluştu.";
}

export function PromptEditor({
  mode,
  template,
  isOpen,
  isSubmitting = false,
  onClose,
  onCreate,
  onUpdate,
}: PromptEditorProps) {
  const [name, setName] = useState("");
  const [digestType, setDigestType] = useState<DigestType>("fmcg_weekly");
  const [sectionKey, setSectionKey] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPromptTemplate, setUserPromptTemplate] = useState("");
  const [modelPreference, setModelPreference] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    if (mode === "edit" && template) {
      setName(template.name);
      setDigestType(template.digest_type);
      setSectionKey(template.section_key);
      setSystemPrompt(template.system_prompt);
      setUserPromptTemplate(template.user_prompt_template);
      setModelPreference(template.model_preference ?? "");
      setIsActive(template.is_active);
    } else {
      setName("");
      setDigestType("fmcg_weekly");
      setSectionKey("");
      setSystemPrompt("");
      setUserPromptTemplate("");
      setModelPreference("");
      setIsActive(true);
    }
    setFormError(null);
  }, [isOpen, mode, template]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);

    const trimmedName = name.trim();
    const trimmedSectionKey = sectionKey.trim();
    const trimmedSystem = systemPrompt.trim();
    const trimmedUser = userPromptTemplate.trim();

    if (!trimmedName || !trimmedSectionKey || !trimmedSystem || !trimmedUser) {
      setFormError("Lütfen zorunlu alanları doldurun.");
      return;
    }

    const modelPref: ApiProvider | null =
      modelPreference === "groq" || modelPreference === "gemini"
        ? modelPreference
        : null;

    try {
      if (mode === "create") {
        await onCreate({
          name: trimmedName,
          digest_type: digestType,
          section_key: trimmedSectionKey,
          system_prompt: trimmedSystem,
          user_prompt_template: trimmedUser,
          model_preference: modelPref,
          is_active: isActive,
        });
      } else {
        await onUpdate({
          name: trimmedName,
          digest_type: digestType,
          section_key: trimmedSectionKey,
          system_prompt: trimmedSystem,
          user_prompt_template: trimmedUser,
          model_preference: modelPref,
          is_active: isActive,
        });
      }
    } catch (error) {
      setFormError(getFormErrorMessage(error));
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === "create" ? "Yeni Prompt Şablonu" : "Prompt Şablonu Düzenle"}
      className="max-w-3xl"
    >
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
        {formError ? <FormErrorBanner message={formError} /> : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Şablon adı"
            name="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />

          <div className="space-y-1.5">
            <label htmlFor="digest-type" className="block text-sm font-medium text-gray-700">
              Bülten tipi
            </label>
            <select
              id="digest-type"
              value={digestType}
              onChange={(event) =>
                setDigestType(event.target.value as DigestType)
              }
              className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {DIGEST_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Bölüm anahtarı (section_key)"
            name="section_key"
            value={sectionKey}
            onChange={(event) => setSectionKey(event.target.value)}
            placeholder="global_trends"
            required
          />

          <div className="space-y-1.5">
            <label htmlFor="model-preference" className="block text-sm font-medium text-gray-700">
              Model tercihi
            </label>
            <select
              id="model-preference"
              value={modelPreference}
              onChange={(event) => setModelPreference(event.target.value)}
              className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {MODEL_OPTIONS.map((option) => (
                <option key={option.value || "default"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="system-prompt" className="block text-sm font-medium text-gray-700">
            System prompt
          </label>
          <textarea
            id="system-prompt"
            name="system_prompt"
            rows={5}
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            required
          />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="user-prompt-template"
            className="block text-sm font-medium text-gray-700"
          >
            User prompt şablonu
          </label>
          <textarea
            id="user-prompt-template"
            name="user_prompt_template"
            rows={10}
            value={userPromptTemplate}
            onChange={(event) => setUserPromptTemplate(event.target.value)}
            className="min-h-[200px] w-full resize-y rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            placeholder="Aşağıdaki haberleri analiz et:&#10;{context}"
            required
          />
          <p className="text-xs text-gray-500">
            Kullanılabilir değişkenler: {"{context}"}, {"{date_range}"}, {"{section_name}"}
          </p>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(event) => setIsActive(event.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-navy-800 focus:ring-navy-600"
          />
          Aktif şablon
        </label>

        {mode === "edit" && template ? (
          <p className="text-xs text-gray-500">
            Mevcut versiyon: v{template.version} · Son güncelleme:{" "}
            {new Date(template.updated_at).toLocaleString("tr-TR")}
          </p>
        ) : null}

        <div className="flex justify-end gap-3 border-t border-gray-100 pt-4">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
