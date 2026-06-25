"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  NewsletterSectionEditor,
  VariableHints,
  type SectionDraft,
} from "@/components/admin/newsletter-section-editor";
import {
  NEWSLETTER_DEFAULTS,
  NEWSLETTER_MODEL_OPTIONS,
  NEWSLETTER_SECTION_VARIABLES,
  NEWSLETTER_SUMMARY_VARIABLES,
} from "@/lib/newsletter-labels";
import { CONTENT_CATEGORY_LABELS } from "@/lib/content-archive-labels";
import type {
  ContentCategory,
  CreateNewsletterTemplateRequest,
  NewsletterTemplate,
  UpdateNewsletterTemplateRequest,
} from "@/types/api";
import { isApiError } from "@/types/api";

interface NewsletterEditorProps {
  mode: "create" | "edit";
  template?: NewsletterTemplate;
  isSubmitting: boolean;
  onCancel: () => void;
  onCreate: (body: CreateNewsletterTemplateRequest) => Promise<void>;
  onUpdate: (body: UpdateNewsletterTemplateRequest) => Promise<void>;
}

const SLUG_PATTERN = /^[a-z0-9_]+$/;

const CONTENT_CATEGORY_OPTIONS = Object.keys(
  CONTENT_CATEGORY_LABELS,
) as ContentCategory[];

const textareaClass =
  "w-full rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600";

function emptySection(key: string): SectionDraft {
  return {
    key,
    id: null,
    name: "",
    section_system_prompt: "",
    section_user_prompt: "",
    impact_prompt: "",
    is_active: true,
  };
}

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "İşlem sırasında bir hata oluştu.";
}

export function NewsletterEditor({
  mode,
  template,
  isSubmitting,
  onCancel,
  onCreate,
  onUpdate,
}: NewsletterEditorProps) {
  const keyCounter = useRef(0);
  const nextKey = () => {
    keyCounter.current += 1;
    return `section-${keyCounter.current}`;
  };

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [dateRangeDays, setDateRangeDays] = useState<number>(
    NEWSLETTER_DEFAULTS.dateRangeDays,
  );
  const [minContentScore, setMinContentScore] = useState<number>(
    NEWSLETTER_DEFAULTS.minContentScore,
  );
  const [summarySystem, setSummarySystem] = useState("");
  const [summaryUser, setSummaryUser] = useState("");
  const [modelPreference, setModelPreference] = useState("");
  const [contentCategories, setContentCategories] = useState<ContentCategory[]>(
    [],
  );
  const [isActive, setIsActive] = useState(true);
  const [sections, setSections] = useState<SectionDraft[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    if (mode === "edit" && template) {
      setName(template.name);
      setSlug(template.slug);
      setDescription(template.description);
      setDateRangeDays(template.date_range_days);
      setMinContentScore(template.min_content_score);
      setSummarySystem(template.summary_system_prompt);
      setSummaryUser(template.summary_user_prompt);
      setModelPreference(template.model_preference ?? "");
      setContentCategories(template.content_categories ?? []);
      setIsActive(template.is_active);
      setSections(
        [...template.sections]
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((section) => ({
            key: nextKey(),
            id: section.id,
            name: section.name,
            section_system_prompt: section.section_system_prompt,
            section_user_prompt: section.section_user_prompt,
            impact_prompt: section.impact_prompt,
            is_active: section.is_active,
          })),
      );
    } else {
      setName("");
      setSlug("");
      setDescription("");
      setDateRangeDays(NEWSLETTER_DEFAULTS.dateRangeDays);
      setMinContentScore(NEWSLETTER_DEFAULTS.minContentScore);
      setSummarySystem("");
      setSummaryUser("");
      setModelPreference("");
      setContentCategories([]);
      setIsActive(true);
      setSections([emptySection(nextKey())]);
    }
    setFormError(null);
    setConfirmOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, template]);

  const updateSection = (key: string, patch: Partial<SectionDraft>) => {
    setSections((prev) =>
      prev.map((section) =>
        section.key === key ? { ...section, ...patch } : section,
      ),
    );
  };

  const removeSection = (key: string) => {
    setSections((prev) => prev.filter((section) => section.key !== key));
  };

  const moveSection = (key: string, direction: -1 | 1) => {
    setSections((prev) => {
      const index = prev.findIndex((section) => section.key === key);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const addSection = () => {
    setSections((prev) => [...prev, emptySection(nextKey())]);
  };

  const toggleContentCategory = (category: ContentCategory) => {
    setContentCategories((prev) =>
      prev.includes(category)
        ? prev.filter((item) => item !== category)
        : [...prev, category],
    );
  };

  const validate = (): string | null => {
    if (!name.trim()) return "Bülten adı zorunludur.";
    if (mode === "create") {
      if (!slug.trim()) return "Slug zorunludur.";
      if (!SLUG_PATTERN.test(slug.trim()))
        return "Slug yalnızca küçük harf, rakam ve alt çizgi içerebilir.";
    }
    if (dateRangeDays < 1 || dateRangeDays > 365)
      return "İçerik tarih aralığı 1–365 gün arasında olmalıdır.";
    if (minContentScore < 0 || minContentScore > 100)
      return "Min içerik skoru 0–100 arasında olmalıdır.";
    if (!summarySystem.trim()) return "Bülten özet system prompt zorunludur.";
    if (!summaryUser.trim()) return "Bülten özet user prompt zorunludur.";
    if (sections.length === 0) return "En az bir bölüm tanımlamalısınız.";
    for (const [index, section] of sections.entries()) {
      const order = index + 1;
      if (!section.name.trim()) return `${order}. bölümün adı zorunludur.`;
      if (!section.section_system_prompt.trim())
        return `${order}. bölümün system prompt'u zorunludur.`;
      if (!section.section_user_prompt.trim())
        return `${order}. bölümün user prompt'u zorunludur.`;
      if (!section.impact_prompt.trim())
        return `${order}. bölümün etki prompt'u zorunludur.`;
    }
    return null;
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const error = validate();
    if (error) {
      setFormError(error);
      return;
    }
    setFormError(null);
    setConfirmOpen(true);
  };

  const buildPayload = () => ({
    name: name.trim(),
    description: description.trim(),
    date_range_days: dateRangeDays,
    summary_system_prompt: summarySystem.trim(),
    summary_user_prompt: summaryUser.trim(),
    min_content_score: minContentScore,
    content_categories: contentCategories,
    model_preference: modelPreference === "" ? null : modelPreference,
    is_active: isActive,
    sections: sections.map((section, index) => ({
      ...(section.id ? { id: section.id } : {}),
      name: section.name.trim(),
      sort_order: index,
      section_system_prompt: section.section_system_prompt.trim(),
      section_user_prompt: section.section_user_prompt.trim(),
      impact_prompt: section.impact_prompt.trim(),
      is_active: section.is_active,
    })),
  });

  const handleConfirm = async () => {
    try {
      if (mode === "create") {
        await onCreate({ slug: slug.trim(), ...buildPayload() });
      } else {
        await onUpdate(buildPayload());
      }
      setConfirmOpen(false);
    } catch (error) {
      setConfirmOpen(false);
      setFormError(getFormErrorMessage(error));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-bold text-navy-800">
          {mode === "create" ? "Yeni Bülten" : `Bülten Düzenle — ${template?.name ?? ""}`}
        </h2>
        <Button type="button" variant="ghost" onClick={onCancel}>
          ← Listeye dön
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {formError ? <FormErrorBanner message={formError} /> : null}

        <section className="space-y-4 rounded-lg border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Bülten alanları
          </h3>

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Bülten adı"
              name="newsletter-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
            <Input
              label="Slug"
              name="newsletter-slug"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              placeholder="fmcg_haftalik"
              readOnly={mode === "edit"}
              disabled={mode === "edit"}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="newsletter-description"
              className="block text-sm font-medium text-gray-700"
            >
              Bülten açıklaması
            </label>
            <textarea
              id="newsletter-description"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="İçerik tarih aralığı (gün)"
              name="date-range-days"
              type="number"
              min={1}
              max={365}
              value={dateRangeDays}
              onChange={(event) => setDateRangeDays(Number(event.target.value))}
            />
            <Input
              label="Min içerik skoru (0–100)"
              name="min-content-score"
              type="number"
              min={0}
              max={100}
              value={minContentScore}
              onChange={(event) => setMinContentScore(Number(event.target.value))}
            />
            <div className="space-y-1.5">
              <label
                htmlFor="model-preference"
                className="block text-sm font-medium text-gray-700"
              >
                Model tercihi
              </label>
              <select
                id="model-preference"
                value={modelPreference}
                onChange={(event) => setModelPreference(event.target.value)}
                className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
              >
                {NEWSLETTER_MODEL_OPTIONS.map((option) => (
                  <option key={option.value || "default"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <span className="block text-sm font-medium text-gray-700">
              İçerik kategorileri
            </span>
            <p className="text-xs text-gray-500">
              Seçilen kategorilerdeki haberler bültene alınır. Boş bırakılırsa tüm
              kategoriler değerlendirilir.
            </p>
            <div className="flex flex-wrap gap-2 rounded-md border border-gray-200 px-3 py-2.5">
              {CONTENT_CATEGORY_OPTIONS.map((category) => {
                const checked = contentCategories.includes(category);
                return (
                  <label
                    key={category}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                      checked
                        ? "border-navy-600 bg-navy-50 text-navy-800"
                        : "border-gray-200 bg-white text-gray-700 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleContentCategory(category)}
                      className="h-4 w-4 rounded border-gray-300 text-navy-800 focus:ring-navy-600"
                    />
                    {CONTENT_CATEGORY_LABELS[category]}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="summary-system"
              className="block text-sm font-medium text-gray-700"
            >
              Bülten özet system prompt
            </label>
            <textarea
              id="summary-system"
              rows={4}
              value={summarySystem}
              onChange={(event) => setSummarySystem(event.target.value)}
              className={textareaClass}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="summary-user"
              className="block text-sm font-medium text-gray-700"
            >
              Bülten özet user prompt
            </label>
            <textarea
              id="summary-user"
              rows={6}
              value={summaryUser}
              onChange={(event) => setSummaryUser(event.target.value)}
              className={textareaClass}
            />
          </div>

          <VariableHints
            title="Editör (bülten özeti) değişkenleri"
            variables={NEWSLETTER_SUMMARY_VARIABLES}
          />

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-navy-800 focus:ring-navy-600"
            />
            Aktif bülten
          </label>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Bölümler ({sections.length})
            </h3>
            <Button type="button" variant="secondary" size="sm" onClick={addSection}>
              + Bölüm Ekle
            </Button>
          </div>

          {sections.length === 0 ? (
            <p className="rounded-md border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500">
              Henüz bölüm yok. En az bir bölüm ekleyin.
            </p>
          ) : (
            <div className="space-y-4">
              {sections.map((section, index) => (
                <NewsletterSectionEditor
                  key={section.key}
                  section={section}
                  index={index}
                  total={sections.length}
                  variables={NEWSLETTER_SECTION_VARIABLES}
                  onChange={updateSection}
                  onRemove={removeSection}
                  onMove={moveSection}
                />
              ))}
            </div>
          )}
        </section>

        <div className="flex justify-end gap-3 border-t border-gray-100 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            Kaydet
          </Button>
        </div>
      </form>

      <ConfirmDialog
        isOpen={confirmOpen}
        title="Bülteni kaydet"
        message="Bu bülten ve prompt'ları production'a alınacak. Kaydetmek istediğinize emin misiniz?"
        confirmLabel="Kaydet"
        variant="primary"
        isLoading={isSubmitting}
        onConfirm={() => void handleConfirm()}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
