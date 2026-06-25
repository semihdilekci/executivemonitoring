"use client";

import Link from "next/link";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { NewsletterBadge } from "@/components/digest/newsletter-badge";
import { TeaserSkeleton } from "@/components/digest/digest-list-skeleton";
import { useUnreadDigestTeasers } from "@/hooks/use-digests";

export function UnreadTeasers() {
  const { teasers, isLoading, isError, error, refetch } =
    useUnreadDigestTeasers(3);

  if (isLoading) {
    return <TeaserSkeleton count={3} />;
  }

  if (isError) {
    return (
      <ErrorView
        message={
          error instanceof Error
            ? error.message
            : "Okunmamış bültenler yüklenemedi."
        }
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (teasers.length === 0) {
    return (
      <EmptyState
        title="Tüm bültenleri okudunuz"
        description="Yeni bültenler yayınlandığında burada görünecek."
      />
    );
  }

  return (
    <section aria-labelledby="unread-teasers-heading" className="space-y-4">
      <h2
        id="unread-teasers-heading"
        className="text-sm font-semibold uppercase tracking-wide text-gray-500"
      >
        Okunmamış Bültenler
      </h2>

      <ul className="space-y-2">
        {teasers.map((digest) => (
          <li key={digest.id}>
            <Link
              href={`/digests/${digest.id}`}
              className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 bg-white px-4 py-3 shadow-sm transition-colors hover:border-gold-200 hover:bg-gold-50/40"
            >
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-navy-800">
                {digest.title}
              </span>
              <NewsletterBadge newsletterSlug={digest.newsletter_slug} />
            </Link>
          </li>
        ))}
      </ul>

      <div className="pt-1">
        <Link
          href="/digests"
          className="text-sm font-semibold text-navy-800 hover:text-gold-500"
        >
          Tüm bültenleri gör →
        </Link>
      </div>
    </section>
  );
}
