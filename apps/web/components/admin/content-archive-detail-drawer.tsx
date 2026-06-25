"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ErrorView } from "@/components/common/error-view";
import { LoadingSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import { useContentArchiveDetail } from "@/hooks/use-content-archive-detail";
import {
  formatRelevancePercent,
  getContentCategoryLabel,
  getRelevanceBadgeClass,
  getSchemaCategoryLabel,
} from "@/lib/content-archive-labels";
import { formatNumericDateTime, formatPeriodRange } from "@/lib/date-format";
import { getSafeExternalUrl } from "@/lib/safe-url";
import { SOURCE_TYPE_COLORS, SOURCE_TYPE_LABELS } from "@/lib/source-labels";
import { cn } from "@/lib/utils";
import type { ProcessedItemListItem } from "@/types/api";

interface ContentArchiveDetailDrawerProps {
  item: ProcessedItemListItem | null;
  isOpen: boolean;
  onClose: () => void;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="text-sm text-gray-800">{value}</dd>
    </div>
  );
}

export function ContentArchiveDetailDrawer({
  item,
  isOpen,
  onClose,
}: ContentArchiveDetailDrawerProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [activeLang, setActiveLang] = useState<string>("canonical");

  const detailQuery = useContentArchiveDetail(
    isOpen && item ? item.id : null,
    isOpen && item ? item.schema_category : null,
  );

  const detail = detailQuery.data;

  // Canonical (TR) + her dil varyantı için sekme; varyant yoksa tek görünüm.
  const languageTabs = useMemo(() => {
    if (!detail) return [];
    const canonical = {
      key: "canonical",
      label: `${detail.language.toUpperCase()} (canonical)`,
      title: null as string | null,
      content: detail.clean_content,
    };
    const variants = detail.translations.map((variant) => ({
      key: `${variant.language}${variant.is_original ? "-orig" : ""}`,
      label: `${variant.language.toUpperCase()}${variant.is_original ? " (orijinal)" : ""}`,
      title: variant.title,
      content: variant.content,
    }));
    return [canonical, ...variants];
  }, [detail]);

  // Yeni içerik yüklendiğinde canonical sekmesine dön.
  useEffect(() => {
    setActiveLang("canonical");
  }, [detail?.id]);

  useEffect(() => {
    if (!isOpen) return;

    const previousFocus = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
      previousFocus?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen || !item) return null;

  const safeUrl = getSafeExternalUrl(item.url);
  const activeTab =
    languageTabs.find((tab) => tab.key === activeLang) ?? languageTabs[0];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Kapat"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative z-10 flex h-full w-full max-w-[640px] flex-col bg-white shadow-xl focus:outline-none"
      >
        <div className="flex items-start justify-between gap-4 border-b border-gray-100 px-6 py-4">
          <h2
            id={titleId}
            className="text-lg font-semibold leading-snug text-navy-800"
          >
            {item.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="-mr-2 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-navy-800"
            aria-label="Kapat"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {/* Üst meta — drawer açılır açılmaz liste verisinden gösterilir */}
          <dl className="grid grid-cols-2 gap-4">
            <InfoRow label="Kaynak" value={item.source_name} />
            <InfoRow
              label="Yayın"
              value={
                item.published_at
                  ? formatNumericDateTime(item.published_at)
                  : "—"
              }
            />
            <InfoRow
              label="İşlenme"
              value={formatNumericDateTime(item.processed_at)}
            />
            <div className="flex flex-col">
              <dt className="text-xs uppercase tracking-wide text-gray-400">
                Skor
              </dt>
              <dd>
                <span
                  className={cn(
                    "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold",
                    getRelevanceBadgeClass(item.relevance_score),
                  )}
                >
                  {formatRelevancePercent(item.relevance_score)}
                </span>
              </dd>
            </div>
          </dl>

          <div className="flex flex-wrap gap-2">
            <span className="inline-flex rounded-full bg-navy-100 px-2.5 py-0.5 text-xs font-medium text-navy-800">
              {getContentCategoryLabel(item.content_category)}
            </span>
            <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide text-gray-500">
              {getSchemaCategoryLabel(item.schema_category)}
            </span>
            <span
              className={cn(
                "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                SOURCE_TYPE_COLORS[item.source_type],
              )}
            >
              {SOURCE_TYPE_LABELS[item.source_type]}
            </span>
            <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500">
              {item.language.toUpperCase()}
            </span>
          </div>

          {safeUrl ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-navy-700 hover:underline"
            >
              Haberin kaynağına git
              <span aria-hidden>↗</span>
            </a>
          ) : null}

          {item.topics.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Keyword&apos;ler
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {item.topics.map((topic) => (
                  <span
                    key={topic}
                    className="inline-flex rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {/* Detay yükü — tam metin + bülten kullanım + chunk sayısı */}
          {detailQuery.isLoading ? <LoadingSkeleton lines={6} /> : null}

          {detailQuery.isError ? (
            <ErrorView onRetry={() => void detailQuery.refetch()} />
          ) : null}

          {detail && activeTab ? (
            <>
              <div className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Tam metin
                </h3>

                {languageTabs.length > 1 ? (
                  <div
                    className="flex flex-wrap gap-1 border-b border-gray-100"
                    role="tablist"
                    aria-label="Dil varyantları"
                  >
                    {languageTabs.map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        role="tab"
                        aria-selected={tab.key === activeTab.key}
                        onClick={() => setActiveLang(tab.key)}
                        className={cn(
                          "-mb-px border-b-2 px-3 py-1.5 text-sm font-medium",
                          tab.key === activeTab.key
                            ? "border-navy-600 text-navy-800"
                            : "border-transparent text-gray-500 hover:text-navy-700",
                        )}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                ) : null}

                {activeTab.title ? (
                  <p className="text-sm font-semibold text-navy-800">
                    {activeTab.title}
                  </p>
                ) : null}
                <p className="whitespace-pre-wrap rounded-lg bg-gray-50 p-4 text-sm leading-relaxed text-gray-700">
                  {activeTab.content}
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Bültenlerde kullanım
                </h3>
                {detail.digest_usages.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    Bu içerik henüz bir bültende kullanılmadı.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {detail.digest_usages.map((usage) => (
                      <li
                        key={`${usage.digest_id}:${usage.section_title}`}
                        className="rounded-lg border border-gray-100 p-3"
                      >
                        <Link
                          href={`/digests/${usage.digest_id}`}
                          className="text-sm font-medium text-navy-800 hover:text-navy-600 hover:underline"
                        >
                          {usage.digest_title}
                        </Link>
                        <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-gray-500">
                          <span>
                            {formatPeriodRange(
                              usage.period_start,
                              usage.period_end,
                            )}
                          </span>
                          <span>Bölüm: {usage.section_title}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <p className="text-xs text-gray-400">
                RAG parça sayısı: {detail.chunk_count}
              </p>
            </>
          ) : null}
        </div>

        <div className="flex justify-end border-t border-gray-100 px-6 py-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Kapat
          </Button>
        </div>
      </div>
    </div>
  );
}
