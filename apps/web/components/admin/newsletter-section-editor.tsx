"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** Editörde düzenlenen bölüm taslağı (`key` = UI-yerel sabit anahtar). */
export interface SectionDraft {
  key: string;
  id: string | null;
  name: string;
  section_system_prompt: string;
  section_user_prompt: string;
  impact_prompt: string;
  is_active: boolean;
}

const textareaClass =
  "w-full rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600";

/** Kullanılabilir prompt değişkenlerini kopyala butonlarıyla gösterir. */
export function VariableHints({
  title,
  variables,
}: {
  title: string;
  variables: readonly string[];
}) {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      setCopied(null);
    }
  };

  return (
    <div className="rounded-md bg-gray-50 px-3 py-2">
      <p className="mb-1.5 text-xs font-medium text-gray-600">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {variables.map((variable) => (
          <button
            key={variable}
            type="button"
            onClick={() => void copy(variable)}
            className="inline-flex items-center rounded border border-gray-200 bg-white px-2 py-0.5 font-mono text-xs text-navy-700 hover:bg-navy-50"
          >
            {copied === variable ? "Kopyalandı ✓" : variable}
          </button>
        ))}
      </div>
    </div>
  );
}

interface NewsletterSectionEditorProps {
  section: SectionDraft;
  index: number;
  total: number;
  variables: readonly string[];
  onChange: (key: string, patch: Partial<SectionDraft>) => void;
  onRemove: (key: string) => void;
  onMove: (key: string, direction: -1 | 1) => void;
}

export function NewsletterSectionEditor({
  section,
  index,
  total,
  variables,
  onChange,
  onRemove,
  onMove,
}: NewsletterSectionEditorProps) {
  const fieldId = (name: string) => `section-${section.key}-${name}`;

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-navy-100 px-2 text-xs font-semibold text-navy-800">
          {index + 1}
        </span>
        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={index === 0}
            aria-label="Yukarı taşı"
            onClick={() => onMove(section.key, -1)}
          >
            ↑
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={index === total - 1}
            aria-label="Aşağı taşı"
            onClick={() => onMove(section.key, 1)}
          >
            ↓
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-red-500 hover:bg-red-50"
            aria-label="Bölümü sil"
            onClick={() => onRemove(section.key)}
          >
            Sil
          </Button>
        </div>
      </div>

      <Input
        label="Bölüm adı"
        id={fieldId("name")}
        value={section.name}
        onChange={(event) => onChange(section.key, { name: event.target.value })}
        placeholder="Yıldız ve Rakipleri"
      />

      <div className="space-y-1.5">
        <label
          htmlFor={fieldId("system")}
          className="block text-sm font-medium text-gray-700"
        >
          Bölüm özet system prompt
        </label>
        <textarea
          id={fieldId("system")}
          rows={3}
          value={section.section_system_prompt}
          onChange={(event) =>
            onChange(section.key, { section_system_prompt: event.target.value })
          }
          className={textareaClass}
        />
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor={fieldId("user")}
          className="block text-sm font-medium text-gray-700"
        >
          Bölüm özet user prompt
        </label>
        <textarea
          id={fieldId("user")}
          rows={5}
          value={section.section_user_prompt}
          onChange={(event) =>
            onChange(section.key, { section_user_prompt: event.target.value })
          }
          className={textareaClass}
        />
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor={fieldId("impact")}
          className="block text-sm font-medium text-gray-700"
        >
          Yıldız Holding için etki prompt
        </label>
        <textarea
          id={fieldId("impact")}
          rows={3}
          value={section.impact_prompt}
          onChange={(event) =>
            onChange(section.key, { impact_prompt: event.target.value })
          }
          className={textareaClass}
        />
      </div>

      <VariableHints title="Bölüm değişkenleri" variables={variables} />

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={section.is_active}
          onChange={(event) =>
            onChange(section.key, { is_active: event.target.checked })
          }
          className="h-4 w-4 rounded border-gray-300 text-navy-800 focus:ring-navy-600"
        />
        Aktif bölüm
      </label>
    </div>
  );
}
