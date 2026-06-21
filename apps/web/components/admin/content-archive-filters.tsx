"use client";

import { Input } from "@/components/ui/input";
import {
  CONTENT_CATEGORY_FILTER_OPTIONS,
  HAS_DIGEST_FILTER_OPTIONS,
  SCHEMA_CATEGORY_FILTER_OPTIONS,
} from "@/lib/content-archive-labels";
import type { SourceListItem } from "@/types/api";

export interface ContentArchiveFilterState {
  sourceId: string;
  schemaCategory: string;
  contentCategory: string;
  publishedFrom: string;
  publishedTo: string;
  minScore: string;
  topic: string;
  q: string;
  hasDigest: string;
}

export const EMPTY_CONTENT_ARCHIVE_FILTERS: ContentArchiveFilterState = {
  sourceId: "",
  schemaCategory: "",
  contentCategory: "",
  publishedFrom: "",
  publishedTo: "",
  minScore: "",
  topic: "",
  q: "",
  hasDigest: "",
};

interface ContentArchiveFiltersProps {
  value: ContentArchiveFilterState;
  onChange: (next: ContentArchiveFilterState) => void;
  sources: SourceListItem[];
}

const selectClass =
  "flex h-10 w-full min-w-[160px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600";

export function ContentArchiveFilters({
  value,
  onChange,
  sources,
}: ContentArchiveFiltersProps) {
  const patch = (partial: Partial<ContentArchiveFilterState>) =>
    onChange({ ...value, ...partial });

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
      <div className="space-y-1.5">
        <label
          htmlFor="archive-source-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Kaynak
        </label>
        <select
          id="archive-source-filter"
          value={value.sourceId}
          onChange={(event) => patch({ sourceId: event.target.value })}
          className={selectClass}
        >
          <option value="">Tüm kaynaklar</option>
          {sources.map((source) => (
            <option key={source.id} value={source.id}>
              {source.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="archive-schema-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Şema
        </label>
        <select
          id="archive-schema-filter"
          value={value.schemaCategory}
          onChange={(event) => patch({ schemaCategory: event.target.value })}
          className={selectClass}
        >
          {SCHEMA_CATEGORY_FILTER_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="archive-category-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Kategori
        </label>
        <select
          id="archive-category-filter"
          value={value.contentCategory}
          onChange={(event) => patch({ contentCategory: event.target.value })}
          className={selectClass}
        >
          {CONTENT_CATEGORY_FILTER_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="w-full sm:max-w-[150px]">
        <Input
          label="Yayın (baş.)"
          name="published_from"
          type="date"
          value={value.publishedFrom}
          onChange={(event) => patch({ publishedFrom: event.target.value })}
        />
      </div>

      <div className="w-full sm:max-w-[150px]">
        <Input
          label="Yayın (bitiş)"
          name="published_to"
          type="date"
          value={value.publishedTo}
          onChange={(event) => patch({ publishedTo: event.target.value })}
        />
      </div>

      <div className="w-full sm:max-w-[120px]">
        <Input
          label="Min skor (0–100)"
          name="min_score"
          type="number"
          min={0}
          max={100}
          inputMode="numeric"
          value={value.minScore}
          onChange={(event) => patch({ minScore: event.target.value })}
        />
      </div>

      <div className="w-full sm:max-w-[160px]">
        <Input
          label="Keyword"
          name="topic"
          type="text"
          placeholder="örn. enflasyon"
          value={value.topic}
          onChange={(event) => patch({ topic: event.target.value })}
        />
      </div>

      <div className="w-full sm:max-w-[200px]">
        <Input
          label="Başlık arama"
          name="q"
          type="search"
          placeholder="en az 2 karakter"
          value={value.q}
          onChange={(event) => patch({ q: event.target.value })}
        />
      </div>

      <div className="space-y-1.5">
        <label
          htmlFor="archive-digest-filter"
          className="block text-sm font-medium text-gray-700"
        >
          Bülten kullanımı
        </label>
        <select
          id="archive-digest-filter"
          value={value.hasDigest}
          onChange={(event) => patch({ hasDigest: event.target.value })}
          className={selectClass}
        >
          {HAS_DIGEST_FILTER_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
