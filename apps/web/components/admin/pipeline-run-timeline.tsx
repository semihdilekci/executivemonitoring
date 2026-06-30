"use client";

import Link from "next/link";
import { DigestStepDetail } from "@/components/admin/digest-step-detail";
import { formatNumericDateTime } from "@/lib/date-format";
import {
  PIPELINE_STAGE_LABELS,
  PIPELINE_STAGE_ORDER,
  PIPELINE_STEP_STATUS_META,
  deriveCollectBreakdown,
  formatPipelineDuration,
} from "@/lib/pipeline-labels";
import { cn } from "@/lib/utils";
import type { PipelineStep } from "@/types/api";

/** İşleme adımı için doğru içerik kırılımı (DB-türetimli; eski run'larda da net). */
export interface ProcessStepCounts {
  processed: number;
  filtered: number;
  failed: number;
}

interface PipelineRunTimelineProps {
  steps: PipelineStep[];
  /** Çalışan aşama sürelerini canlı tutmak için yeniden render zaman damgası. */
  now: number;
  /** "Denetim loguna git" linki için hedef route. */
  auditHref: string;
  /**
   * İşleme adımının "Elendi" (gate/dedup) vs "Hatalı" (gerçek hata) ayrımı.
   * Verilirse process adımı bu sayaçlarla render edilir — `items_failed`'in
   * filtrelemeyi hata sayan eski davranışını ezer (`Docs/04` §8.3).
   */
  processCounts?: ProcessStepCounts | null;
}

function CounterPill({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "filtered" | "error";
}) {
  const toneClass =
    tone === "error" && value > 0
      ? "bg-red-50 text-red-700"
      : tone === "filtered" && value > 0
        ? "bg-amber-50 text-amber-700"
        : "bg-gray-50 text-gray-800";
  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1 rounded-md px-2 py-1 text-xs",
        toneClass,
      )}
    >
      <span className="opacity-70">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  );
}

/**
 * İşleme adımı sayaçlarını çözer: önce dışarıdan gelen (canlı, DB-türetimli)
 * `processCounts`, yoksa `step.detail.filtered`/`errors` (yeni run'lar), o da
 * yoksa `null` (eski davranışa düş — Elendi gösterilmez).
 */
function resolveProcessCounts(
  step: PipelineStep,
  override: ProcessStepCounts | null | undefined,
): ProcessStepCounts | null {
  if (override) return override;
  const filtered = step.detail?.filtered;
  const errors = step.detail?.errors;
  if (typeof filtered === "number" && typeof errors === "number") {
    return { processed: step.items_out, filtered, failed: errors };
  }
  return null;
}

function CollectBreakdown({ step }: { step: PipelineStep }) {
  const rows = deriveCollectBreakdown(step.detail);
  if (rows.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {rows.map((row) => (
        <span
          key={row.type}
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            row.ok
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700",
          )}
          title={row.error ?? undefined}
        >
          {row.label}: {row.ok ? `${row.published ?? 0} ✓` : "✕"}
          {row.ok && row.sourcesFailed ? (
            <span className="text-amber-600">· {row.sourcesFailed} hata</span>
          ) : null}
        </span>
      ))}
    </div>
  );
}

function StepErrorPanel({
  step,
  auditHref,
}: {
  step: PipelineStep;
  auditHref: string;
}) {
  const requestId =
    typeof step.detail?.request_id === "string"
      ? step.detail.request_id
      : null;
  return (
    <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3">
      <p className="text-xs font-semibold text-red-800">Hata teşhisi</p>
      {/* Düz metin render — JSONB içeriği dangerouslySetInnerHTML olmadan (Faz 6 kuralı). */}
      <p className="mt-1 whitespace-pre-wrap break-words text-sm text-red-700">
        {step.error_message}
      </p>
      {requestId ? (
        <p className="mt-1 font-mono text-xs text-red-600">
          Request ID: {requestId}
        </p>
      ) : null}
      <Link
        href={auditHref}
        className="mt-2 inline-block text-xs font-medium text-red-700 underline hover:text-red-900"
      >
        Denetim loguna git →
      </Link>
    </div>
  );
}

function TimelineStep({
  step,
  isLast,
  now,
  auditHref,
  processCounts,
}: {
  step: PipelineStep;
  isLast: boolean;
  now: number;
  auditHref: string;
  processCounts?: ProcessStepCounts | null;
}) {
  const meta = PIPELINE_STEP_STATUS_META[step.status];
  const isSkipped = step.status === "skipped";
  const processSplit =
    step.stage === "process" ? resolveProcessCounts(step, processCounts) : null;

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {/* Dikey bağlayıcı çizgi (son adımda gizli). */}
      {!isLast ? (
        <span
          className={cn(
            "absolute left-4 top-9 -ml-px h-[calc(100%-1.5rem)] w-0.5",
            meta.connectorClass,
          )}
          aria-hidden
        />
      ) : null}

      <span
        className={cn(
          "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ring-2",
          meta.circleClass,
          meta.pulse && "animate-pulse",
        )}
        aria-hidden
      >
        {meta.icon}
      </span>

      <div className={cn("flex-1", isSkipped && "opacity-60")}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-navy-800">
            {PIPELINE_STAGE_LABELS[step.stage]}
          </h3>
          <span className="text-xs text-gray-500">{meta.label}</span>
          <span className="ml-auto text-xs text-gray-400">
            {formatPipelineDuration(step.started_at, step.finished_at, now)}
          </span>
        </div>

        {!isSkipped ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <CounterPill label="Giren" value={step.items_in} />
            {processSplit ? (
              <>
                <CounterPill label="İşlenen" value={processSplit.processed} />
                <CounterPill
                  label="Elendi"
                  value={processSplit.filtered}
                  tone="filtered"
                />
                <CounterPill
                  label="Hatalı"
                  value={processSplit.failed}
                  tone="error"
                />
              </>
            ) : (
              <>
                <CounterPill label="Çıkan" value={step.items_out} />
                <CounterPill
                  label="Hatalı"
                  value={step.items_failed}
                  tone="error"
                />
              </>
            )}
          </div>
        ) : null}

        {step.stage === "collect" && !isSkipped ? (
          <div className="mt-2">
            <CollectBreakdown step={step} />
          </div>
        ) : null}

        {step.stage === "digest" && !isSkipped ? (
          <DigestStepDetail step={step} />
        ) : null}

        {step.started_at ? (
          <p className="mt-1.5 text-xs text-gray-400">
            {formatNumericDateTime(step.started_at)}
          </p>
        ) : null}

        {step.error_message ? (
          <StepErrorPanel step={step} auditHref={auditHref} />
        ) : null}
      </div>
    </li>
  );
}

export function PipelineRunTimeline({
  steps,
  now,
  auditHref,
  processCounts,
}: PipelineRunTimelineProps) {
  // `sequence` sırasında — backend zaten sıralı döner; FE'de garanti altına al.
  const ordered = [...steps].sort((a, b) => {
    const seq = a.sequence - b.sequence;
    if (seq !== 0) return seq;
    return (
      PIPELINE_STAGE_ORDER.indexOf(a.stage) -
      PIPELINE_STAGE_ORDER.indexOf(b.stage)
    );
  });

  return (
    <ol className="rounded-xl border border-gray-200 bg-white p-5">
      {ordered.map((step, index) => (
        <TimelineStep
          key={step.stage}
          step={step}
          isLast={index === ordered.length - 1}
          now={now}
          auditHref={auditHref}
          processCounts={processCounts}
        />
      ))}
    </ol>
  );
}
