"use client";

import { formatNumericDateTime } from "@/lib/date-format";
import { type DigestLogEntry, deriveDigestDetail } from "@/lib/pipeline-labels";
import { cn } from "@/lib/utils";
import type { PipelineStep } from "@/types/api";

/** Log seviyesine göre renk — yakalanan LLM/pipeline logları için. */
const LEVEL_TONE: Record<string, string> = {
  CRITICAL: "text-red-700",
  ERROR: "text-red-700",
  WARNING: "text-amber-700",
  INFO: "text-gray-600",
  DEBUG: "text-gray-400",
};

function SummaryPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-baseline gap-1 rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-800">
      <span className="opacity-70">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  );
}

function ContextLine({ context }: { context: Record<string, unknown> }) {
  const parts = Object.entries(context).map(
    ([key, value]) => `${key}=${String(value)}`,
  );
  if (parts.length === 0) return null;
  return (
    <span className="ml-2 text-gray-400">
      {parts.join(" · ")}
    </span>
  );
}

function LogRow({ entry }: { entry: DigestLogEntry }) {
  const tone = LEVEL_TONE[entry.level] ?? "text-gray-600";
  const shortLogger = entry.logger.replace(/^ygip\./, "");
  return (
    <li className="border-b border-gray-100 py-1 last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-2 font-mono text-xs">
        <span className={cn("font-semibold", tone)}>{entry.level}</span>
        <span className="text-gray-400">{shortLogger}</span>
        {entry.time ? (
          <span className="text-gray-300">
            {formatNumericDateTime(entry.time)}
          </span>
        ) : null}
      </div>
      {/* Düz metin render — ham JSONB dangerouslySetInnerHTML olmadan (Faz 6 kuralı). */}
      <p className="break-words font-mono text-xs text-gray-700">
        {entry.message}
        {entry.context ? <ContextLine context={entry.context} /> : null}
      </p>
      {entry.exc ? (
        <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-red-50 p-2 font-mono text-[11px] leading-snug text-red-800">
          {entry.exc}
        </pre>
      ) : null}
    </li>
  );
}

/**
 * Bülten (digest) adımı detayı: editörün kaç adayı hangi bölüme dağıttığı +
 * üretilen/boş kalan bölümler ve bülten üretimi sırasında yakalanan LLM/pipeline
 * logları (`S-ADMIN-PIPELINE-DETAIL`). Boş bölümün sebebi ("haber atanmadı")
 * burada görünür — 5 bölüm tanımlı ama 4'ü üretildiyse 5.'sinin neden boş
 * olduğu anlaşılır.
 */
export function DigestStepDetail({ step }: { step: PipelineStep }) {
  const data = deriveDigestDetail(step.detail);
  if (!data) return null;

  const generatedCount = data.distribution.filter((row) => row.generated).length;
  const hasSummary =
    data.candidateCount !== null ||
    data.droppedCount !== null ||
    data.totalSourcesUsed !== null;

  return (
    <div className="mt-3 space-y-3">
      {hasSummary ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {data.candidateCount !== null ? (
            <SummaryPill label="Kritere uygun aday" value={data.candidateCount} />
          ) : null}
          {data.distribution.length > 0 ? (
            <SummaryPill
              label="Üretilen bölüm"
              value={generatedCount}
            />
          ) : null}
          {data.definedSectionCount !== null ? (
            <SummaryPill label="Tanımlı bölüm" value={data.definedSectionCount} />
          ) : null}
          {data.droppedCount !== null ? (
            <SummaryPill label="Elenen haber" value={data.droppedCount} />
          ) : null}
          {data.totalSourcesUsed !== null ? (
            <SummaryPill
              label="Kullanılan kaynak"
              value={data.totalSourcesUsed}
            />
          ) : null}
        </div>
      ) : null}

      {data.distribution.length > 0 ? (
        <div className="overflow-hidden rounded-md border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-3 py-1.5 font-medium">Bölüm</th>
                <th className="px-3 py-1.5 text-right font-medium">Atanan haber</th>
                <th className="px-3 py-1.5 text-right font-medium">Durum</th>
              </tr>
            </thead>
            <tbody>
              {data.distribution.map((row) => (
                <tr
                  key={row.sortOrder}
                  className="border-t border-gray-100 text-gray-700"
                >
                  <td className="px-3 py-1.5">{row.name}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">
                    {row.assignedCount}
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    {row.generated ? (
                      <span className="inline-flex rounded-full bg-green-50 px-2 py-0.5 font-medium text-green-700">
                        Üretildi
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                        Boş · haber atanmadı
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {data.logs.length > 0 ? (
        <details className="rounded-md border border-gray-200 bg-gray-50/60">
          <summary className="cursor-pointer select-none px-3 py-2 text-xs font-semibold text-gray-700">
            Üretim logları ({data.logs.length}
            {data.logsTruncated > 0 ? `, +${data.logsTruncated} kırpıldı` : ""})
          </summary>
          <ul className="max-h-96 overflow-y-auto px-3 pb-2">
            {data.logs.map((entry, index) => (
              <LogRow key={`${entry.time ?? index}-${index}`} entry={entry} />
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
