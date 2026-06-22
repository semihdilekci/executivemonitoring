"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RoleGate } from "@/components/auth/role-gate";
import { DigestUpdateModal } from "@/components/admin/digest-update-modal";
import { PipelineRunItems } from "@/components/admin/pipeline-run-items";
import { PipelineRunTimeline } from "@/components/admin/pipeline-run-timeline";
import { PipelineStatusBadge } from "@/components/admin/pipeline-run-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { ErrorView } from "@/components/common/error-view";
import { PipelineDetailSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import { useCancelPipelineRun, useTriggerDigestUpdate } from "@/hooks/use-pipeline";
import { usePipelineRun } from "@/hooks/use-pipeline-run";
import { formatNumericDateTime } from "@/lib/date-format";
import {
  PIPELINE_RUN_TYPE_COLORS,
  PIPELINE_RUN_TYPE_LABELS,
  formatPipelineDuration,
  isActiveRun,
} from "@/lib/pipeline-labels";
import { cn } from "@/lib/utils";
import type {
  PipelineRunDetail,
  PipelineStage,
  RunItemsResponse,
} from "@/types/api";

interface PipelineDetailPageProps {
  params: { id: string };
}

const AUDIT_HREF = "/admin/audit-logs";

function stageCount(
  run: PipelineRunDetail,
  stage: PipelineStage,
  field: "items_out",
): number {
  const step = run.steps.find((s) => s.stage === stage);
  return step ? step[field] : 0;
}

function readDigestId(run: PipelineRunDetail): string | null {
  const value = run.stats?.digest_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

function StatTile({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href?: string;
}) {
  const body = (
    <>
      <p className="text-xs text-gray-500">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold tabular-nums",
          href ? "text-navy-700 underline" : "text-navy-800",
        )}
      >
        {value}
      </p>
    </>
  );
  if (href) {
    return (
      <Link
        href={href}
        className="rounded-lg bg-gray-50 px-3 py-2.5 transition hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
      >
        {body}
      </Link>
    );
  }
  return <div className="rounded-lg bg-gray-50 px-3 py-2.5">{body}</div>;
}

export default function PipelineDetailPage({ params }: PipelineDetailPageProps) {
  const runId = params.id;
  const router = useRouter();

  const runQuery = usePipelineRun(runId);
  const cancelRun = useCancelPipelineRun();
  const triggerDigestUpdate = useTriggerDigestUpdate();

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [digestOpen, setDigestOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [itemsSummary, setItemsSummary] = useState<RunItemsResponse | null>(null);

  const run = runQuery.data;
  const active = run ? isActiveRun(run.status) : false;
  const showItems = run?.run_type === "collect_pipeline";

  // İşleme adımı için doğru Elendi/Hatalı ayrımı (DB-türetimli özetten).
  const processCounts = itemsSummary
    ? {
        processed: itemsSummary.processed,
        filtered: itemsSummary.filtered,
        failed: itemsSummary.failed,
      }
    : null;

  // Çalışan run'da süre sayaçlarını canlı tut (1 sn tick); terminal'de durur.
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  const digestId = useMemo(() => (run ? readDigestId(run) : null), [run]);

  const handleCancel = async () => {
    await cancelRun.mutateAsync(runId);
    setConfirmOpen(false);
  };

  const handleDigestUpdate = async (
    payload: Parameters<typeof triggerDigestUpdate.mutateAsync>[0],
  ) => {
    const created = await triggerDigestUpdate.mutateAsync(payload);
    setDigestOpen(false);
    router.push(`/admin/pipeline/${created.id}`);
  };

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <Link
            href="/admin/pipeline"
            className="text-sm text-gray-500 hover:text-navy-700"
          >
            ← Pipeline İzleme
          </Link>
          <h1 className="text-2xl font-bold text-navy-800">Pipeline Run Detayı</h1>
        </div>

        {runQuery.isLoading ? <PipelineDetailSkeleton /> : null}

        {runQuery.isError ? (
          <ErrorView onRetry={() => void runQuery.refetch()} />
        ) : null}

        {run ? (
          <>
            {/* Üst bilgi kartı */}
            <div className="rounded-lg border border-gray-100 bg-surface p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
                        PIPELINE_RUN_TYPE_COLORS[run.run_type],
                      )}
                    >
                      {PIPELINE_RUN_TYPE_LABELS[run.run_type]}
                    </span>
                    <PipelineStatusBadge status={run.status} />
                  </div>
                  <dl className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
                    <div className="flex gap-2">
                      <dt className="text-gray-500">Tetikleyen:</dt>
                      <dd className="font-medium text-gray-800">
                        {run.triggered_by_name ?? "—"}
                      </dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-gray-500">Süre:</dt>
                      <dd className="font-medium text-gray-800">
                        {formatPipelineDuration(
                          run.started_at,
                          run.finished_at,
                          now,
                        )}
                      </dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-gray-500">Başlangıç:</dt>
                      <dd className="font-medium text-gray-800">
                        {run.started_at
                          ? formatNumericDateTime(run.started_at)
                          : "—"}
                      </dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-gray-500">Bitiş:</dt>
                      <dd className="font-medium text-gray-800">
                        {run.finished_at
                          ? formatNumericDateTime(run.finished_at)
                          : "—"}
                      </dd>
                    </div>
                  </dl>
                </div>

                {active ? (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={() => setConfirmOpen(true)}
                  >
                    İptal Et
                  </Button>
                ) : null}
              </div>

              {/* stats özet bandı */}
              <div className="mt-5 grid gap-3 sm:grid-cols-4">
                <StatTile
                  label="Toplanan"
                  value={String(stageCount(run, "collect", "items_out"))}
                />
                <StatTile
                  label="Ingest"
                  value={String(stageCount(run, "ingest", "items_out"))}
                />
                <StatTile
                  label="İşlenen"
                  value={String(stageCount(run, "process", "items_out"))}
                />
                {digestId ? (
                  <StatTile
                    label="Üretilen Bülten"
                    value="Bülteni Aç"
                    href={`/digests/${digestId}`}
                  />
                ) : (
                  <StatTile label="Üretilen Bülten" value="—" />
                )}
              </div>

              {run.error_summary ? (
                <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3">
                  <p className="text-xs font-semibold text-red-800">
                    Çalıştırma hatası
                  </p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm text-red-700">
                    {run.error_summary}
                  </p>
                </div>
              ) : null}
            </div>

            {/* Aşama timeline'ı */}
            <PipelineRunTimeline
              steps={run.steps}
              now={now}
              auditHref={AUDIT_HREF}
              processCounts={processCounts}
            />

            {/* Okunan kaynaklar + elenen içerik drilldown (yalnızca collect run) */}
            {showItems ? (
              <PipelineRunItems runId={runId} onSummary={setItemsSummary} />
            ) : null}

            {/* Bülten güncelleme tetiği detaydan da erişilebilir (`Docs/06`) */}
            <div className="flex justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setDigestOpen(true)}
              >
                Bülten Güncelle
              </Button>
            </div>
          </>
        ) : null}
      </div>

      <ConfirmDialog
        isOpen={confirmOpen}
        title="Pipeline'ı iptal et"
        message="Bu çalıştırmayı iptal etmek istediğinize emin misiniz? Devam eden aşamalar durdurulur."
        confirmLabel="İptal Et"
        cancelLabel="Vazgeç"
        isLoading={cancelRun.isPending}
        onConfirm={() => void handleCancel()}
        onCancel={() => setConfirmOpen(false)}
      />

      <DigestUpdateModal
        isOpen={digestOpen}
        isSubmitting={triggerDigestUpdate.isPending}
        onClose={() => setDigestOpen(false)}
        onSubmit={handleDigestUpdate}
      />
    </RoleGate>
  );
}
