"use client";

import { useId } from "react";
import {
  LLM_REQUEST_TYPES,
  LLM_REQUEST_TYPE_LABELS,
} from "@/lib/llm-request-type-labels";
import type { LlmRequestType } from "@/types/api";

interface RequestTypeScopeSelectorProps {
  value: LlmRequestType[];
  onChange: (scope: LlmRequestType[]) => void;
  disabled?: boolean;
}

/**
 * `request_type_scope` çoklu seçimi. Hiçbiri seçili değilse `[]` = tüm
 * operasyonlar (`Docs/03` §6); bu durum kullanıcıya açıkça gösterilir.
 */
export function RequestTypeScopeSelector({
  value,
  onChange,
  disabled = false,
}: RequestTypeScopeSelectorProps) {
  const groupId = useId();

  const toggle = (type: LlmRequestType) => {
    if (value.includes(type)) {
      onChange(value.filter((item) => item !== type));
    } else {
      onChange([...value, type]);
    }
  };

  return (
    <fieldset className="space-y-2" disabled={disabled}>
      <legend className="block text-sm font-medium text-gray-700">
        Operasyon kapsamı
      </legend>
      <div className="flex flex-wrap gap-3">
        {LLM_REQUEST_TYPES.map((type) => {
          const inputId = `${groupId}-${type}`;
          return (
            <label
              key={type}
              htmlFor={inputId}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:border-navy-300"
            >
              <input
                id={inputId}
                type="checkbox"
                checked={value.includes(type)}
                onChange={() => toggle(type)}
                disabled={disabled}
                className="h-4 w-4 cursor-pointer rounded border-gray-300 text-navy-600 focus-visible:ring-2 focus-visible:ring-navy-600 disabled:cursor-not-allowed"
              />
              {LLM_REQUEST_TYPE_LABELS[type]}
            </label>
          );
        })}
      </div>
      <p className="text-xs text-gray-500">
        {value.length === 0
          ? "Hiçbiri seçili değil — anahtar tüm operasyonlarda kullanılır."
          : "Yalnızca seçili operasyonlarda kullanılır."}
      </p>
    </fieldset>
  );
}
