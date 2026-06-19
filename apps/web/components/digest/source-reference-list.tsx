"use client";

import { useState } from "react";
import { getSafeExternalUrl } from "@/lib/safe-url";
import { cn } from "@/lib/utils";
import type { SourceReference } from "@/types/api";

interface SourceReferenceListProps {
  references: SourceReference[];
}

function SourceReferenceItem({
  reference,
  defaultExpanded,
}: {
  reference: SourceReference;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const safeUrl = getSafeExternalUrl(reference.url);

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
          {safeUrl ? (
            <span className="mt-1 block truncate text-xs font-semibold text-blue-700">
              Kaynak bağlantısı mevcut
            </span>
          ) : (
            <span className="mt-1 block text-xs text-gray-500">
              Harici bağlantı yok
            </span>
          )}
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
        </div>
      ) : null}
    </div>
  );
}

export function SourceReferenceList({ references }: SourceReferenceListProps) {
  if (references.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500">
        Kaynak haberler
      </h4>
      {references.map((reference, index) => (
        <SourceReferenceItem
          key={reference.processed_item_id}
          reference={reference}
          defaultExpanded={index === 0}
        />
      ))}
    </div>
  );
}
