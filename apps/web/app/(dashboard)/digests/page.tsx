"use client";

import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { DigestCard } from "@/components/digest/digest-card";
import { DigestListSkeleton } from "@/components/digest/digest-list-skeleton";
import { Button } from "@/components/ui/button";
import { getNewsletterBadgeMeta } from "@/lib/digest-labels";
import { cn } from "@/lib/utils";
import { useDigestsWithRead } from "@/hooks/use-digests";

interface NewsletterFilterOption {
  value: string;
  label: string;
}

export default function DigestsPage() {
  const [newsletterFilter, setNewsletterFilter] = useState<string>("all");
  const [knownSlugs, setKnownSlugs] = useState<string[]>([]);

  const {
    digests,
    unread,
    read,
    unreadCount,
    isLoading,
    isError,
    error,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useDigestsWithRead({
    newsletterSlug: newsletterFilter === "all" ? undefined : newsletterFilter,
    limit: 20,
  });

  // Görülen bülten slug'larını biriktir; bir filtre seçilince diğer
  // seçenekler kaybolmasın (serbest slug — sabit liste yok).
  useEffect(() => {
    if (digests.length === 0) return;
    setKnownSlugs((prev) => {
      const next = new Set(prev);
      for (const digest of digests) {
        next.add(digest.newsletter_slug);
      }
      return next.size === prev.length ? prev : Array.from(next);
    });
  }, [digests]);

  const filters = useMemo<NewsletterFilterOption[]>(
    () => [
      { value: "all", label: "Tümü" },
      ...knownSlugs.map((slug) => ({
        value: slug,
        label: getNewsletterBadgeMeta(slug).label,
      })),
    ],
    [knownSlugs],
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader />
        <DigestListSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <PageHeader />
        <ErrorView
          message={
            error instanceof Error ? error.message : "Bültenler yüklenemedi."
          }
          onRetry={() => {
            void refetch();
          }}
        />
      </div>
    );
  }

  const hasAnyDigest = unread.length > 0 || read.length > 0;

  return (
    <div className="space-y-8">
      <PageHeader
        filters={filters}
        activeFilter={newsletterFilter}
        onFilterChange={setNewsletterFilter}
      />

      {!hasAnyDigest ? (
        <EmptyState
          title="Henüz bülten yok"
          description="İlk bültenler üretildiğinde burada listelenecek."
        />
      ) : (
        <>
          {unread.length > 0 ? (
            <section aria-labelledby="new-digests-heading" className="space-y-4">
              <div className="flex items-center gap-3 border-b border-gray-200 pb-3">
                <h2
                  id="new-digests-heading"
                  className="text-lg font-bold text-navy-800"
                >
                  Yeni Bültenler
                </h2>
                <span className="rounded-full bg-gold-100 px-2.5 py-0.5 text-xs font-semibold text-gold-500">
                  {unreadCount}
                </span>
              </div>
              <div className="space-y-4">
                {unread.map((digest) => (
                  <DigestCard key={digest.id} digest={digest} variant="large" />
                ))}
              </div>
            </section>
          ) : null}

          {read.length > 0 ? (
            <section
              aria-labelledby="previous-digests-heading"
              className="space-y-4"
            >
              <div className="border-b border-gray-200 pb-3">
                <h2
                  id="previous-digests-heading"
                  className="text-lg font-bold text-navy-800"
                >
                  Önceki Bültenler
                </h2>
              </div>
              <div className="space-y-3">
                {read.map((digest) => (
                  <DigestCard
                    key={digest.id}
                    digest={digest}
                    variant="compact"
                  />
                ))}
              </div>
            </section>
          ) : null}

          {hasNextPage ? (
            <div className="flex justify-center pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  void fetchNextPage();
                }}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Yükleniyor…" : "Daha fazla yükle"}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function PageHeader({
  filters = [],
  activeFilter = "all",
  onFilterChange,
}: {
  filters?: NewsletterFilterOption[];
  activeFilter?: string;
  onFilterChange?: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Bültenler</h1>
        <p className="mt-1 text-sm text-gray-500">
          Haftalık bültenleri okuyun ve okundu olarak işaretleyin.
        </p>
      </div>

      {onFilterChange && filters.length > 1 ? (
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label="Bülten filtresi"
        >
          {filters.map((filter) => {
            const isActive = activeFilter === filter.value;
            return (
              <button
                key={filter.value}
                type="button"
                aria-pressed={isActive}
                onClick={() => onFilterChange(filter.value)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500 focus-visible:ring-offset-2",
                  isActive
                    ? "border-navy-800 bg-navy-800 text-white"
                    : "border-gray-200 bg-white text-gray-600 hover:border-gray-300",
                )}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
