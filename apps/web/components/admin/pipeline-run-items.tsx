"use client";

import { useEffect, useState } from "react";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import { usePipelineRunItems } from "@/hooks/use-pipeline-run-items";
import { getContentCategoryLabel } from "@/lib/content-archive-labels";
import { cn } from "@/lib/utils";
import type { RunItemOutcome, RunItemsResponse } from "@/types/api";

const PAGE_SIZE = 25;

interface PipelineRunItemsProps {
  runId: string;
  /** Üst seviyeye doğru özet sayaçları bildirir (timeline "Elendi" pill'i için). */
  onSummary?: (summary: RunItemsResponse) => void;
}

type OutcomeTab = RunItemOutcome | "all";

const OUTCOME_TABS: { value: OutcomeTab; label: string }[] = [
  { value: "filtered", label: "Elenenler" },
  { value: "processed", label: "İşlenenler" },
  { value: "failed", label: "Hatalılar" },
  { value: "all", label: "Tümü" },
];

const OUTCOME_BADGE: Record<RunItemOutcome, { label: string; cls: string }> = {
  processed: { label: "İşlendi", cls: "bg-emerald-100 text-emerald-800" },
  filtered: { label: "Elendi", cls: "bg-amber-100 text-amber-800" },
  failed: { label: "Hatalı", cls: "bg-red-100 text-red-800" },
};

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "neutral" | "ok" | "filtered" | "error";
}) {
  const toneClass = {
    neutral: "text-navy-800",
    ok: "text-emerald-700",
    filtered: "text-amber-700",
    error: "text-red-700",
  }[tone];
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2.5">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold tabular-nums", toneClass)}>
        {value}
      </p>
    </div>
  );
}

export function PipelineRunItems({ runId, onSummary }: PipelineRunItemsProps) {
  const [tab, setTab] = useState<OutcomeTab>("filtered");
  const [page, setPage] = useState(1);

  const outcome = tab === "all" ? undefined : tab;
  const itemsQuery = usePipelineRunItems(runId, { outcome, page });
  const data = itemsQuery.data;

  // Özet sayaçlar (collected/processed/filtered/failed) outcome filtresinden
  // bağımsız her zaman döner — üst seviyeye bildir (timeline "Elendi" pill'i için).
  useEffect(() => {
    if (data && onSummary) onSummary(data);
  }, [data, onSummary]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  const handleTab = (next: OutcomeTab) => {
    setTab(next);
    setPage(1);
  };

  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-5">
      <div>
        <h2 className="text-base font-semibold text-navy-800">İçerik Kırılımı</h2>
        <p className="mt-0.5 text-sm text-gray-500">
          Bu çalıştırmada okunan kaynaklar ve içeriklerin akıbeti — elenenler
          gate&apos;te keyword eşleşmediği için düştü (hata değil).
        </p>
      </div>

      {data ? (
        <div className="grid gap-3 sm:grid-cols-4">
          <SummaryTile label="Okunan" value={data.collected} tone="neutral" />
          <SummaryTile label="İşlenen" value={data.processed} tone="ok" />
          <SummaryTile label="Elendi" value={data.filtered} tone="filtered" />
          <SummaryTile label="Hatalı" value={data.failed} tone="error" />
        </div>
      ) : null}

      {/* Okunan Kaynaklar */}
      {data && data.by_source.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">Okunan Kaynaklar</h3>
          <DataTable>
            <table className="min-w-full">
              <DataTableHeader>
                <DataTableHead>Kaynak</DataTableHead>
                <DataTableHead className="w-[90px]">Okunan</DataTableHead>
                <DataTableHead className="w-[90px]">İşlenen</DataTableHead>
                <DataTableHead className="w-[90px]">Elendi</DataTableHead>
                <DataTableHead className="w-[90px]">Hatalı</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {data.by_source.map((src) => (
                  <DataTableRow key={src.source_id}>
                    <DataTableCell>
                      <span className="font-medium text-gray-900">
                        {src.source_name}
                      </span>
                    </DataTableCell>
                    <DataTableCell className="tabular-nums text-gray-700">
                      {src.collected}
                    </DataTableCell>
                    <DataTableCell className="tabular-nums text-emerald-700">
                      {src.processed}
                    </DataTableCell>
                    <DataTableCell className="tabular-nums text-amber-700">
                      {src.filtered}
                    </DataTableCell>
                    <DataTableCell className="tabular-nums text-red-700">
                      {src.failed}
                    </DataTableCell>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </table>
          </DataTable>
        </div>
      ) : null}

      {/* İçerik listesi + outcome sekmeleri */}
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {OUTCOME_TABS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handleTab(option.value)}
              className={cn(
                "rounded-full px-3 py-1 text-sm font-medium transition-colors",
                tab === option.value
                  ? "bg-navy-700 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {itemsQuery.isLoading ? (
          <p className="py-6 text-center text-sm text-gray-500">Yükleniyor…</p>
        ) : null}

        {data && data.items.length === 0 && !itemsQuery.isLoading ? (
          <EmptyState
            title="İçerik yok"
            description="Bu akıbet için bu çalıştırmada içerik bulunmuyor."
          />
        ) : null}

        {data && data.items.length > 0 ? (
          <ul className="space-y-2">
            {data.items.map((item) => {
              const badge = OUTCOME_BADGE[item.outcome];
              return (
                <li
                  key={item.id}
                  className="rounded-lg border border-gray-100 bg-gray-50/50 p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold",
                        badge.cls,
                      )}
                    >
                      {badge.label}
                    </span>
                    <span className="text-xs text-gray-500">
                      {item.source_name}
                    </span>
                    {item.outcome === "processed" && item.content_category ? (
                      <span className="text-xs text-gray-500">
                        · {getContentCategoryLabel(item.content_category)}
                        {item.relevance_score != null
                          ? ` · %${Math.round(item.relevance_score * 100)}`
                          : ""}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-gray-900">
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-navy-700 hover:underline"
                      >
                        {item.title ?? "(başlıksız)"}
                      </a>
                    ) : (
                      (item.title ?? "(başlıksız)")
                    )}
                  </p>
                  {item.snippet ? (
                    <p className="mt-1 line-clamp-2 text-sm text-gray-600">
                      {item.snippet}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}

        {data && totalPages > 1 ? (
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>
              Toplam {data.total} · Sayfa {page}/{totalPages}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={page <= 1 || itemsQuery.isFetching}
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              >
                Önceki
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={page >= totalPages || itemsQuery.isFetching}
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              >
                Sonraki
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
