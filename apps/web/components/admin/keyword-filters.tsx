"use client";

import { Input } from "@/components/ui/input";
import {
  KEYWORD_CATEGORY_FILTER_OPTIONS,
  KEYWORD_STATUS_FILTER_OPTIONS,
} from "@/lib/keyword-labels";

export interface KeywordFilterState {
  category: string;
  q: string;
  isActive: string;
}

export const EMPTY_KEYWORD_FILTERS: KeywordFilterState = {
  category: "",
  q: "",
  isActive: "",
};

interface KeywordFiltersProps {
  value: KeywordFilterState;
  onChange: (next: KeywordFilterState) => void;
}

const selectClass =
  "flex h-10 w-full min-w-[160px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600";

export function KeywordFilters({ value, onChange }: KeywordFiltersProps) {
  const patch = (partial: Partial<KeywordFilterState>) =>
    onChange({ ...value, ...partial });

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="w-full sm:max-w-xs">
        <Input
          label="Ara"
          name="search"
          type="search"
          placeholder="en az 2 karakter (tr/en)"
          value={value.q}
          onChange={(event) => patch({ q: event.target.value })}
        />
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="keyword-category-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Kategori
        </label>
        <select
          id="keyword-category-filter"
          value={value.category}
          onChange={(event) => patch({ category: event.target.value })}
          className={selectClass}
        >
          {KEYWORD_CATEGORY_FILTER_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="keyword-status-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Durum
        </label>
        <select
          id="keyword-status-filter"
          value={value.isActive}
          onChange={(event) => patch({ isActive: event.target.value })}
          className={selectClass}
        >
          {KEYWORD_STATUS_FILTER_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
