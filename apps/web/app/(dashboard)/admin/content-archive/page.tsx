"use client";

import { useMemo, useState } from "react";
import {
  ContentArchiveFilters,
  EMPTY_CONTENT_ARCHIVE_FILTERS,
  type ContentArchiveFilterState,
} from "@/components/admin/content-archive-filters";
import { ContentArchiveDetailDrawer } from "@/components/admin/content-archive-detail-drawer";
import { ContentArchiveTable } from "@/components/admin/content-archive-table";
import { RoleGate } from "@/components/auth/role-gate";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { ContentArchiveTableSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import {
  flattenContentArchivePages,
  useContentArchive,
} from "@/hooks/use-content-archive";
import { flattenSourcePages, useSources } from "@/hooks/use-sources";
import type {
  ContentCategory,
  ProcessedItemListItem,
  ProcessedItemListParams,
  ProcessedItemSortField,
  SchemaCategory,
  SortDirection,
} from "@/types/api";

const DEFAULT_SORT_FIELD: ProcessedItemSortField = "processed_at";
const DEFAULT_SORT_DIR: SortDirection = "desc";

/** Filtre formu state'ini API query parametrelerine çevirir (UI 0–100 → API 0–1). */
function toApiFilters(
  state: ContentArchiveFilterState,
): Omit<ProcessedItemListParams, "cursor"> {
  const trimmedQuery = state.q.trim();
  const parsedScore = Number.parseInt(state.minScore, 10);
  const minScore =
    state.minScore !== "" && Number.isFinite(parsedScore)
      ? Math.min(Math.max(parsedScore, 0), 100) / 100
      : undefined;

  return {
    source_id: state.sourceId || undefined,
    schema_category: (state.schemaCategory || undefined) as
      | SchemaCategory
      | undefined,
    content_category: (state.contentCategory || undefined) as
      | ContentCategory
      | undefined,
    published_from: state.publishedFrom || undefined,
    published_to: state.publishedTo || undefined,
    min_score: minScore,
    topic: state.topic.trim() || undefined,
    // Backend `q` min 2 karakter ister — kısa girişte filtreyi gönderme (422 önle).
    q: trimmedQuery.length >= 2 ? trimmedQuery : undefined,
    has_digest:
      state.hasDigest === "" ? undefined : state.hasDigest === "true",
    limit: 20,
  };
}

export default function AdminContentArchivePage() {
  const [filters, setFilters] = useState<ContentArchiveFilterState>(
    EMPTY_CONTENT_ARCHIVE_FILTERS,
  );
  const [selectedItem, setSelectedItem] =
    useState<ProcessedItemListItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [sortBy, setSortBy] =
    useState<ProcessedItemSortField>(DEFAULT_SORT_FIELD);
  const [sortDir, setSortDir] = useState<SortDirection>(DEFAULT_SORT_DIR);

  const apiFilters = useMemo(
    () => ({ ...toApiFilters(filters), sort_by: sortBy, sort_dir: sortDir }),
    [filters, sortBy, sortDir],
  );

  const sourcesQuery = useSources({ limit: 100 });
  const archiveQuery = useContentArchive(apiFilters);

  // Aynı sütuna tıklayınca yön değişir; farklı sütunda yeni alan + azalan başlar.
  const handleSortChange = (field: ProcessedItemSortField) => {
    if (field === sortBy) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  const sources = useMemo(
    () => flattenSourcePages(sourcesQuery.data),
    [sourcesQuery.data],
  );

  const items = useMemo(
    () => flattenContentArchivePages(archiveQuery.data),
    [archiveQuery.data],
  );

  const hasNoFilters = useMemo(
    () =>
      Object.values(filters).every((value) => value === ""),
    [filters],
  );

  const isEmpty =
    !archiveQuery.isLoading && !archiveQuery.isError && items.length === 0;

  const openDrawer = (item: ProcessedItemListItem) => {
    setSelectedItem(item);
    setIsDrawerOpen(true);
  };

  return (
    <RoleGate>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">İçerik Arşivi</h1>
          <p className="mt-1 text-sm text-gray-500">
            Processor&apos;dan geçmiş haber içeriklerini filtreleyin ve
            inceleyin.
          </p>
        </div>

        <ContentArchiveFilters
          value={filters}
          onChange={setFilters}
          sources={sources}
        />

        {archiveQuery.isLoading ? <ContentArchiveTableSkeleton /> : null}

        {archiveQuery.isError ? (
          <ErrorView onRetry={() => void archiveQuery.refetch()} />
        ) : null}

        {isEmpty ? (
          <EmptyState
            title={
              hasNoFilters
                ? "Henüz işlenmiş içerik yok"
                : "Filtrelere uygun içerik bulunamadı"
            }
            description={
              hasNoFilters
                ? "Pipeline tamamlandığında processor'dan geçen haberler burada listelenecek."
                : "Farklı filtre kombinasyonu deneyin veya filtreleri temizleyin."
            }
            action={
              hasNoFilters ? undefined : (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setFilters(EMPTY_CONTENT_ARCHIVE_FILTERS)}
                >
                  Filtreleri temizle
                </Button>
              )
            }
          />
        ) : null}

        {!archiveQuery.isLoading && !archiveQuery.isError && items.length > 0 ? (
          <>
            <ContentArchiveTable
              items={items}
              onSelect={openDrawer}
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={handleSortChange}
            />

            {archiveQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void archiveQuery.fetchNextPage()}
                  disabled={archiveQuery.isFetchingNextPage}
                >
                  {archiveQuery.isFetchingNextPage
                    ? "Yükleniyor…"
                    : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <ContentArchiveDetailDrawer
        item={selectedItem}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />
    </RoleGate>
  );
}
