"use client";

import { getSafeExternalUrl } from "@/lib/safe-url";
import type { ChatSource } from "@/types/api";

interface SourceCardProps {
  source: ChatSource;
}

function formatRelevanceScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function SourceCard({ source }: SourceCardProps) {
  const safeUrl = getSafeExternalUrl(source.url);

  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {safeUrl ? (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="line-clamp-2 text-sm font-semibold text-blue-700 hover:underline"
            >
              {source.title}
            </a>
          ) : (
            <p className="line-clamp-2 text-sm font-semibold text-navy-800">
              {source.title}
            </p>
          )}
        </div>
        <span className="shrink-0 rounded-full bg-navy-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-navy-700">
          {formatRelevanceScore(source.score)}
        </span>
      </div>
    </div>
  );
}
