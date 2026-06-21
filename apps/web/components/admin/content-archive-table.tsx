"use client";

import Link from "next/link";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import {
  formatRelevancePercent,
  getContentCategoryLabel,
  getRelevanceBadgeClass,
  getSchemaCategoryLabel,
} from "@/lib/content-archive-labels";
import { formatNumericDate } from "@/lib/date-format";
import { getSafeExternalUrl } from "@/lib/safe-url";
import { SOURCE_TYPE_COLORS, SOURCE_TYPE_LABELS } from "@/lib/source-labels";
import { cn } from "@/lib/utils";
import type {
  ProcessedItemListItem,
  ProcessedItemSortField,
  SortDirection,
} from "@/types/api";

interface ContentArchiveTableProps {
  items: ProcessedItemListItem[];
  onSelect: (item: ProcessedItemListItem) => void;
  sortBy: ProcessedItemSortField;
  sortDir: SortDirection;
  onSortChange: (field: ProcessedItemSortField) => void;
}

function SortIndicator({ state }: { state: SortDirection | null }) {
  return (
    <span
      aria-hidden
      className={cn(
        "text-[10px]",
        state ? "text-navy-700" : "text-gray-300",
      )}
    >
      {state === "asc" ? "▲" : state === "desc" ? "▼" : "↕"}
    </span>
  );
}

function SortableHead({
  field,
  label,
  activeField,
  activeDir,
  onSortChange,
  className,
}: {
  field: ProcessedItemSortField;
  label: string;
  activeField: ProcessedItemSortField;
  activeDir: SortDirection;
  onSortChange: (field: ProcessedItemSortField) => void;
  className?: string;
}) {
  const isActive = activeField === field;
  return (
    <DataTableHead className={className}>
      <button
        type="button"
        onClick={() => onSortChange(field)}
        className="inline-flex items-center gap-1 font-semibold uppercase tracking-wide text-gray-500 hover:text-navy-800"
        aria-label={`${label} sütununa göre sırala`}
      >
        {label}
        <SortIndicator state={isActive ? activeDir : null} />
      </button>
    </DataTableHead>
  );
}

const MAX_TOPIC_CHIPS = 3;
const MAX_DIGEST_CHIPS = 2;

function TopicChips({ topics }: { topics: string[] }) {
  if (topics.length === 0) {
    return <span className="text-gray-300">—</span>;
  }

  const visible = topics.slice(0, MAX_TOPIC_CHIPS);
  const overflow = topics.length - visible.length;

  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((topic) => (
        <span
          key={topic}
          className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
        >
          {topic}
        </span>
      ))}
      {overflow > 0 ? (
        <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
          +{overflow}
        </span>
      ) : null}
    </div>
  );
}

function DigestChips({
  usages,
}: {
  usages: ProcessedItemListItem["digest_usages"];
}) {
  if (usages.length === 0) {
    return <span className="text-gray-300">—</span>;
  }

  const visible = usages.slice(0, MAX_DIGEST_CHIPS);
  const overflow = usages.length - visible.length;

  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((usage) => (
        <Link
          key={usage.digest_id}
          href={`/digests/${usage.digest_id}`}
          className="inline-flex max-w-[150px] truncate rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800 hover:bg-sky-100"
          title={usage.digest_title}
        >
          {usage.digest_title}
        </Link>
      ))}
      {overflow > 0 ? (
        <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
          +{overflow}
        </span>
      ) : null}
    </div>
  );
}

export function ContentArchiveTable({
  items,
  onSelect,
  sortBy,
  sortDir,
  onSortChange,
}: ContentArchiveTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <SortableHead
            field="title"
            label="Başlık"
            activeField={sortBy}
            activeDir={sortDir}
            onSortChange={onSortChange}
          />
          <DataTableHead className="w-[140px]">Kaynak</DataTableHead>
          <SortableHead
            field="published_at"
            label="Yayın"
            activeField={sortBy}
            activeDir={sortDir}
            onSortChange={onSortChange}
            className="w-[110px]"
          />
          <SortableHead
            field="relevance_score"
            label="Skor"
            activeField={sortBy}
            activeDir={sortDir}
            onSortChange={onSortChange}
            className="w-[80px]"
          />
          <DataTableHead className="w-[180px]">Keyword&apos;ler</DataTableHead>
          <DataTableHead className="w-[140px]">Kategori</DataTableHead>
          <DataTableHead className="w-[170px]">Bültenler</DataTableHead>
          <DataTableHead className="w-[80px]">
            <span className="sr-only">İşlem</span>
          </DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {items.map((item) => {
            const safeUrl = getSafeExternalUrl(item.url);
            return (
            <DataTableRow key={`${item.schema_category}:${item.id}`}>
              <DataTableCell className="max-w-[320px]">
                <button
                  type="button"
                  onClick={() => onSelect(item)}
                  className="line-clamp-2 text-left font-medium text-navy-800 hover:text-navy-600 hover:underline"
                  title={item.title}
                >
                  {item.title}
                </button>
                {safeUrl ? (
                  <a
                    href={safeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-xs text-navy-600 hover:underline"
                  >
                    Habere git
                    <span aria-hidden>↗</span>
                  </a>
                ) : null}
              </DataTableCell>
              <DataTableCell className="text-gray-600">
                <div className="flex flex-col gap-1">
                  <span>{item.source_name}</span>
                  <span
                    className={cn(
                      "inline-flex w-fit rounded-full px-2 py-0.5 text-[11px] font-medium",
                      SOURCE_TYPE_COLORS[item.source_type],
                    )}
                  >
                    {SOURCE_TYPE_LABELS[item.source_type]}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell className="whitespace-nowrap text-gray-600">
                {item.published_at
                  ? formatNumericDate(item.published_at)
                  : "—"}
              </DataTableCell>
              <DataTableCell>
                <span
                  className={cn(
                    "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                    getRelevanceBadgeClass(item.relevance_score),
                  )}
                >
                  {formatRelevancePercent(item.relevance_score)}
                </span>
              </DataTableCell>
              <DataTableCell>
                <TopicChips topics={item.topics} />
              </DataTableCell>
              <DataTableCell>
                <div className="flex flex-col gap-1">
                  <span className="text-gray-700">
                    {getContentCategoryLabel(item.content_category)}
                  </span>
                  <span className="inline-flex w-fit rounded bg-gray-100 px-1.5 py-0.5 text-[11px] uppercase tracking-wide text-gray-500">
                    {getSchemaCategoryLabel(item.schema_category)}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell>
                <DigestChips usages={item.digest_usages} />
              </DataTableCell>
              <DataTableCell>
                <button
                  type="button"
                  onClick={() => onSelect(item)}
                  className="inline-flex h-8 items-center rounded-md px-2.5 text-sm font-medium text-navy-700 hover:bg-gray-100"
                >
                  Detay
                </button>
              </DataTableCell>
            </DataTableRow>
            );
          })}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
