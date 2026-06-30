"use client";

import { useState } from "react";
import { useNewsImpact } from "@/hooks/use-news-impact";
import { formatShortDate } from "@/lib/date-format";
import { getSafeExternalUrl } from "@/lib/safe-url";
import { cn } from "@/lib/utils";
import type { SourceReference } from "@/types/api";

interface NewsDrawerCardProps {
  reference: SourceReference;
  defaultExpanded?: boolean;
}

function formatReferenceMeta(reference: SourceReference): string | null {
  const parts: string[] = [];
  const sourceName = reference.source_name?.trim();
  if (sourceName) {
    parts.push(sourceName);
  }
  if (reference.published_at) {
    parts.push(formatShortDate(reference.published_at));
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function ImpactAnalysis({
  processedItemId,
}: {
  processedItemId: string;
}) {
  const { status, analysis, errorMessage, isLoading, requestImpact } =
    useNewsImpact(processedItemId);
  const [open, setOpen] = useState(false);

  const handleClick = () => {
    setOpen((value) => !value);
    if (status === "idle") {
      void requestImpact();
    }
  };

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={handleClick}
        className="inline-flex items-center gap-1.5 rounded-md border border-gold-200 bg-gold-50 px-3 py-1.5 text-xs font-bold text-gold-600 transition-colors hover:bg-gold-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500"
        aria-expanded={open}
      >
        ★ Yıldız&apos;ı nasıl etkiler?
      </button>

      {open ? (
        <div className="mt-3 rounded-lg border border-gold-200 bg-gold-50/60 px-4 py-3">
          {isLoading ? (
            <p
              className="flex items-center gap-1.5 text-sm text-gray-500"
              aria-live="polite"
            >
              <span className="animate-pulse">Yıldız etkisi analiz ediliyor</span>
              <span className="animate-bounce [animation-delay:-0.2s]">·</span>
              <span className="animate-bounce [animation-delay:-0.1s]">·</span>
              <span className="animate-bounce">·</span>
            </p>
          ) : null}

          {status === "error" ? (
            <p className="text-sm text-red-600" role="alert">
              {errorMessage}
            </p>
          ) : null}

          {status === "success" && analysis ? (
            <p className="whitespace-pre-line text-sm leading-relaxed text-gray-700">
              {analysis}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Çekmece haber kartı (Faz 6.5) — accordion başlık + kaynağa git +
 * "Yıldız'ı nasıl etkiler?" anlık etki analizi.
 */
export function NewsDrawerCard({
  reference,
  defaultExpanded = false,
}: NewsDrawerCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const safeUrl = getSafeExternalUrl(reference.url);
  const referenceMeta = formatReferenceMeta(reference);

  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/60">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500"
        aria-expanded={expanded}
      >
        <span
          className={cn(
            "mt-0.5 text-xs text-gray-400 transition-transform",
            expanded && "rotate-90",
          )}
          aria-hidden
        >
          ▶
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-navy-800">
            {reference.title}
          </span>
          {referenceMeta ? (
            <span className="mt-1 block text-xs font-medium text-gray-500">
              {referenceMeta}
            </span>
          ) : null}
          {reference.summary ? (
            <span className="mt-1 block text-xs leading-relaxed text-gray-500">
              {reference.summary}
            </span>
          ) : null}
        </span>
      </button>

      {expanded ? (
        <div className="border-t border-gray-100 px-4 py-3">
          {safeUrl ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-semibold text-blue-700 hover:underline"
            >
              Kaynağa git ↗
            </a>
          ) : (
            <p className="text-sm text-gray-500">
              Bu kaynak için güvenli bir dış bağlantı bulunmuyor.
            </p>
          )}

          <ImpactAnalysis processedItemId={reference.processed_item_id} />
        </div>
      ) : null}
    </div>
  );
}
