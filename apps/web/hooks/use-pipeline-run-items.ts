"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { RunItemsParams, RunItemsResponse } from "@/types/api";

const ITEMS_PAGE_SIZE = 25;

/**
 * Run penceresindeki okunan/işlenen/elenen içerik kırılımını çeker
 * (`GET /pipeline/runs/{id}/items`). `outcome` ile elenen/hatalı/işlenen
 * süzülür; özet sayaçlar (collected/processed/filtered/failed) + kaynak
 * kırılımı her zaman döner (`Docs/03` §11.5). Terminal run'larda statik —
 * tek sefer çekilir; sayfa değişiminde önceki veri korunur (titremesiz).
 */
export function usePipelineRunItems(runId: string, params?: RunItemsParams) {
  const outcome = params?.outcome;
  const page = params?.page ?? 1;

  return useQuery({
    queryKey: queryKeys.pipeline.items(runId, { outcome, page }),
    queryFn: async () => {
      const response = await apiClient.get<RunItemsResponse>(
        `/pipeline/runs/${runId}/items`,
        {
          params: {
            outcome,
            page,
            page_size: params?.page_size ?? ITEMS_PAGE_SIZE,
          },
        },
      );
      return response.data;
    },
    enabled: Boolean(runId),
    placeholderData: keepPreviousData,
  });
}
