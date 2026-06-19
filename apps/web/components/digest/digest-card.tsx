"use client";

import Link from "next/link";
import { DigestTypeBadge } from "@/components/digest/digest-type-badge";
import { ReadToggle } from "@/components/digest/read-toggle";
import { formatPeriodRange, formatShortDate } from "@/lib/date-format";
import { cn } from "@/lib/utils";
import type { DigestWithRead } from "@/hooks/use-digests";

interface DigestCardProps {
  digest: DigestWithRead;
  variant?: "large" | "compact";
  yildizImpactSummary?: string | null;
}

export function DigestCard({
  digest,
  variant = "large",
  yildizImpactSummary,
}: DigestCardProps) {
  const isLarge = variant === "large";
  const publishedAt = digest.completed_at ?? digest.created_at;

  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-xl border bg-white shadow-sm transition-shadow hover:shadow-md",
        !digest.isRead && "border-l-[3px] border-l-gold-500",
        digest.isRead ? "border-gray-100" : "border-gray-200",
      )}
    >
      {!digest.isRead ? (
        <span
          className="absolute right-3 top-3 h-2 w-2 rounded-full bg-gold-500"
          aria-hidden
        />
      ) : null}

      <div className={cn(isLarge ? "p-6" : "p-4")}>
        <Link href={`/digests/${digest.id}`} className="block space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <DigestTypeBadge digestType={digest.digest_type} />
            <span className="text-xs text-gray-500">
              {formatShortDate(publishedAt)}
            </span>
          </div>

          <div>
            <h3
              className={cn(
                "font-bold text-navy-800",
                isLarge ? "text-lg" : "text-base line-clamp-1",
              )}
            >
              {digest.title}
            </h3>
            {isLarge ? (
              <p className="mt-2 line-clamp-2 text-sm text-gray-600">
                {formatPeriodRange(digest.period_start, digest.period_end)} dönemi
                bülteni · {digest.total_sources_used} kaynak
              </p>
            ) : (
              <p className="mt-1 text-xs text-gray-500">
                {formatPeriodRange(digest.period_start, digest.period_end)} ·{" "}
                {digest.total_sources_used} kaynak
              </p>
            )}
          </div>
        </Link>

        {isLarge && yildizImpactSummary ? (
          <div className="mt-4 rounded-lg border border-gold-100 bg-gold-50 px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-500">
              Yıldız Holding için etki
            </p>
            <p className="mt-1 text-sm text-gray-700 line-clamp-3">
              {yildizImpactSummary}
            </p>
          </div>
        ) : null}

        <div className="mt-4 flex justify-end">
          <ReadToggle digestId={digest.id} isRead={digest.isRead} />
        </div>
      </div>
    </article>
  );
}
