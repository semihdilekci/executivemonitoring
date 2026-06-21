"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import { isActiveRun } from "@/lib/pipeline-labels";
import type { PipelineRunDetail } from "@/types/api";

/** Çalışan run detayında canlı izleme poll aralığı (`Docs/05` §8). */
const RUN_POLL_INTERVAL_MS = 3000;

/**
 * Tek run'ın aşama-bazlı detayını çeker; `running`/`pending` iken 3 sn'de bir
 * poll eder, terminal statüde polling kendini durdurur — sonsuz istek yok
 * (`Docs/05` §8, `S-ADMIN-PIPELINE-DETAIL`).
 */
export function usePipelineRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.pipeline.run(runId),
    queryFn: async () => {
      const response = await apiClient.get<PipelineRunDetail>(
        `/pipeline/runs/${runId}`,
      );
      return response.data;
    },
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isActiveRun(status) ? RUN_POLL_INTERVAL_MS : false;
    },
  });
}
