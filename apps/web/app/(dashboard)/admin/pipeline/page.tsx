"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { RoleGate } from "@/components/auth/role-gate";
import { DigestUpdateModal } from "@/components/admin/digest-update-modal";
import { PipelineRunTable } from "@/components/admin/pipeline-run-table";
import { PipelineTriggerModal } from "@/components/admin/pipeline-trigger-modal";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { PipelineTableSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import {
  flattenRunPages,
  usePipelineRuns,
  useTriggerDigestUpdate,
  useTriggerPipeline,
} from "@/hooks/use-pipeline";
import {
  PIPELINE_RUN_TYPE_FILTERS,
  PIPELINE_STATUS_FILTERS,
  isActiveRun,
} from "@/lib/pipeline-labels";
import type { PipelineRunStatus, PipelineRunType } from "@/types/api";

type RunTypeFilter = "all" | PipelineRunType;
type StatusFilter = "all" | PipelineRunStatus;

export default function AdminPipelinePage() {
  const router = useRouter();

  const [runTypeFilter, setRunTypeFilter] = useState<RunTypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [triggerOpen, setTriggerOpen] = useState(false);
  const [digestOpen, setDigestOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const runsQuery = usePipelineRuns({
    run_type: runTypeFilter === "all" ? undefined : runTypeFilter,
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 20,
  });

  const triggerPipeline = useTriggerPipeline();
  const triggerDigestUpdate = useTriggerDigestUpdate();

  const runs = useMemo(() => flattenRunPages(runsQuery.data), [runsQuery.data]);

  const hasActiveRun = useMemo(
    () => runs.some((run) => isActiveRun(run.status)),
    [runs],
  );

  // Çalışan run varken süre sayaçlarını canlı tut (1 sn tick); aksi halde durur.
  useEffect(() => {
    if (!hasActiveRun) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasActiveRun]);

  const handleTrigger = async (sourceTypes: string[]) => {
    const run = await triggerPipeline.mutateAsync(sourceTypes);
    setTriggerOpen(false);
    router.push(`/admin/pipeline/${run.id}`);
  };

  const handleDigestUpdate = async (
    payload: Parameters<typeof triggerDigestUpdate.mutateAsync>[0],
  ) => {
    const run = await triggerDigestUpdate.mutateAsync(payload);
    setDigestOpen(false);
    router.push(`/admin/pipeline/${run.id}`);
  };

  const isEmpty =
    !runsQuery.isLoading && !runsQuery.isError && runs.length === 0;
  const hasNoFilters = runTypeFilter === "all" && statusFilter === "all";

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">Pipeline İzleme</h1>
            <p className="mt-1 text-sm text-gray-500">
              Veri toplama ve bülten üretim süreçlerini tetikleyin, canlı izleyin.
            </p>
          </div>
          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={() => setDigestOpen(true)}>
              Bülten Güncelle
            </Button>
            <Button type="button" onClick={() => setTriggerOpen(true)}>
              Yeni Pipeline Başlat
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="space-y-1.5">
            <label htmlFor="run-type-filter" className="block text-sm font-medium text-gray-700">
              Tip
            </label>
            <select
              id="run-type-filter"
              value={runTypeFilter}
              onChange={(event) => setRunTypeFilter(event.target.value as RunTypeFilter)}
              className="flex h-10 w-full min-w-[180px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {PIPELINE_RUN_TYPE_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700">
              Durum
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              className="flex h-10 w-full min-w-[160px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {PIPELINE_STATUS_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {runsQuery.isLoading ? <PipelineTableSkeleton /> : null}

        {runsQuery.isError ? (
          <ErrorView onRetry={() => void runsQuery.refetch()} />
        ) : null}

        {isEmpty ? (
          <EmptyState
            title="Henüz pipeline çalıştırması yok"
            description={
              hasNoFilters
                ? "İlk veri toplama sürecini başlatarak pipeline'ı izlemeye başlayın."
                : "Filtrelere uygun çalıştırma bulunamadı."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={() => setTriggerOpen(true)}>
                  Yeni Pipeline Başlat
                </Button>
              ) : undefined
            }
          />
        ) : null}

        {!runsQuery.isLoading && !runsQuery.isError && runs.length > 0 ? (
          <>
            <PipelineRunTable
              runs={runs}
              now={now}
              onRowClick={(run) => router.push(`/admin/pipeline/${run.id}`)}
            />

            {runsQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void runsQuery.fetchNextPage()}
                  disabled={runsQuery.isFetchingNextPage}
                >
                  {runsQuery.isFetchingNextPage ? "Yükleniyor…" : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <PipelineTriggerModal
        isOpen={triggerOpen}
        isSubmitting={triggerPipeline.isPending}
        onClose={() => setTriggerOpen(false)}
        onSubmit={handleTrigger}
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
