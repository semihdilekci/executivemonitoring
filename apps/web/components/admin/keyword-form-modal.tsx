"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DEFAULT_KEYWORD_RATING,
  KEYWORD_CATEGORIES,
  KEYWORD_CATEGORY_LABELS,
} from "@/lib/keyword-labels";
import type {
  KeywordCategory,
  KeywordCategoryRating,
  KeywordCreateRequest,
  KeywordResponse,
  KeywordUpdateRequest,
} from "@/types/api";
import { isApiError } from "@/types/api";

type KeywordFormMode = "create" | "edit";

interface KeywordFormModalProps {
  mode: KeywordFormMode;
  keyword?: KeywordResponse;
  isOpen: boolean;
  isSubmitting?: boolean;
  onClose: () => void;
  onCreate: (values: KeywordCreateRequest) => Promise<void>;
  onUpdate: (values: KeywordUpdateRequest) => Promise<void>;
}

/** Seçili kategori → rating (1–10). Kategori yoksa havuzda değildir. */
type RatingMap = Partial<Record<KeywordCategory, number>>;

function toRatingMap(categories: KeywordCategoryRating[]): RatingMap {
  const map: RatingMap = {};
  for (const item of categories) {
    map[item.category] = item.rating;
  }
  return map;
}

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.code === "KEYWORD_DUPLICATE") {
      return "Bu terim zaten kayıtlı.";
    }
    return error.message;
  }
  return "İşlem sırasında bir hata oluştu.";
}

export function KeywordFormModal({
  mode,
  keyword,
  isOpen,
  isSubmitting = false,
  onClose,
  onCreate,
  onUpdate,
}: KeywordFormModalProps) {
  const [termTr, setTermTr] = useState("");
  const [termEn, setTermEn] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [ratings, setRatings] = useState<RatingMap>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!isOpen) return;

    if (mode === "edit" && keyword) {
      setTermTr(keyword.term_tr);
      setTermEn(keyword.term_en);
      setIsActive(keyword.is_active);
      setRatings(toRatingMap(keyword.categories));
    } else {
      setTermTr("");
      setTermEn("");
      setIsActive(true);
      setRatings({});
    }
    setFormError(null);
    setFieldErrors({});
  }, [isOpen, mode, keyword]);

  const toggleCategory = (category: KeywordCategory, checked: boolean) => {
    setRatings((prev) => {
      const next = { ...prev };
      if (checked) {
        next[category] = DEFAULT_KEYWORD_RATING;
      } else {
        delete next[category];
      }
      return next;
    });
  };

  const setRating = (category: KeywordCategory, value: number) => {
    setRatings((prev) => ({ ...prev, [category]: value }));
  };

  const buildCategories = (): KeywordCategoryRating[] =>
    KEYWORD_CATEGORIES.filter(
      (category) => ratings[category] !== undefined,
    ).map((category) => ({
      category,
      rating: ratings[category] as number,
    }));

  const validate = (categories: KeywordCategoryRating[]): boolean => {
    const errors: Record<string, string> = {};

    if (!termTr.trim()) {
      errors.term_tr = "Türkçe terim zorunludur.";
    }
    if (!termEn.trim()) {
      errors.term_en = "İngilizce terim zorunludur.";
    }
    if (categories.length === 0) {
      errors.categories = "En az bir kategori seçin.";
    } else if (
      categories.some((item) => item.rating < 1 || item.rating > 10)
    ) {
      errors.categories = "Rating 1 ile 10 arasında olmalı.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (isSubmitting) return;

    const categories = buildCategories();
    if (!validate(categories)) return;

    try {
      if (mode === "create") {
        await onCreate({
          term_tr: termTr.trim(),
          term_en: termEn.trim(),
          is_active: isActive,
          categories,
        });
      } else {
        await onUpdate({
          term_tr: termTr.trim(),
          term_en: termEn.trim(),
          is_active: isActive,
          categories,
        });
      }
    } catch (error) {
      const message = getFormErrorMessage(error);
      // Duplicate → terim alanı altında uyarı (`Docs/03` §11.7).
      if (isApiError(error) && error.code === "KEYWORD_DUPLICATE") {
        setFieldErrors((prev) => ({ ...prev, term_tr: message }));
      } else {
        setFormError(message);
      }
    }
  };

  const title = mode === "create" ? "Keyword Ekle" : "Keyword Düzenle";
  const submitLabel = mode === "create" ? "Kaydet" : "Güncelle";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="space-y-4"
        noValidate
      >
        {formError ? <FormErrorBanner message={formError} /> : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Terim (TR)"
            name="term_tr"
            type="text"
            maxLength={120}
            value={termTr}
            disabled={isSubmitting}
            error={fieldErrors.term_tr}
            onChange={(event) => setTermTr(event.target.value)}
          />
          <Input
            label="Terim (EN)"
            name="term_en"
            type="text"
            maxLength={120}
            value={termEn}
            disabled={isSubmitting}
            error={fieldErrors.term_en}
            onChange={(event) => setTermEn(event.target.value)}
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            name="is_active"
            checked={isActive}
            disabled={isSubmitting}
            onChange={(event) => setIsActive(event.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-navy-600 focus:ring-navy-600"
          />
          Aktif (pasif keyword&apos;ler processor havuzuna girmez)
        </label>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-gray-700">
            Kategoriler &amp; Rating (1–10)
          </legend>
          {fieldErrors.categories ? (
            <p className="text-sm text-red-500">{fieldErrors.categories}</p>
          ) : null}
          <div className="space-y-2">
            {KEYWORD_CATEGORIES.map((category) => {
              const selected = ratings[category] !== undefined;
              return (
                <div
                  key={category}
                  className="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2"
                >
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={isSubmitting}
                      onChange={(event) =>
                        toggleCategory(category, event.target.checked)
                      }
                      className="h-4 w-4 rounded border-gray-300 text-navy-600 focus:ring-navy-600"
                    />
                    {KEYWORD_CATEGORY_LABELS[category]}
                  </label>
                  {selected ? (
                    <input
                      type="number"
                      aria-label={`${KEYWORD_CATEGORY_LABELS[category]} rating`}
                      min={1}
                      max={10}
                      value={ratings[category] ?? DEFAULT_KEYWORD_RATING}
                      disabled={isSubmitting}
                      onChange={(event) => {
                        const parsed = Number.parseInt(event.target.value, 10);
                        const clamped = Number.isFinite(parsed)
                          ? Math.min(Math.max(parsed, 1), 10)
                          : DEFAULT_KEYWORD_RATING;
                        setRating(category, clamped);
                      }}
                      className="h-9 w-16 rounded-md border border-gray-200 bg-white px-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
                    />
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
                  )}
                </div>
              );
            })}
          </div>
        </fieldset>

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
