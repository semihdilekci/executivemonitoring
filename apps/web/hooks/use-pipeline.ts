"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import { isActiveRun } from "@/lib/pipeline-labels";
import type {
  CancelPipelineResponse,
  PaginatedResponse,
  PipelineRunListParams,
  PipelineRunSummary,
  TriggerDigestUpdateRequest,
  TriggerPipelineResponse,
} from "@/types/api";

/** Listede aktif (`pending`/`running`) run varken poll aralığı (`Docs/05` §8). */
const LIST_POLL_INTERVAL_MS = 5000;

async function fetchRunsPage(
  params: PipelineRunListParams,
): Promise<PaginatedResponse<PipelineRunSummary>> {
  const response = await apiClient.get<PaginatedResponse<PipelineRunSummary>>(
    "/pipeline/runs",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit ?? 20,
        run_type: params.run_type,
        status: params.status,
        start_date: params.start_date,
        end_date: params.end_date,
      },
    },
  );
  return response.data;
}

export function usePipelineRuns(filters?: {
  run_type?: PipelineRunListParams["run_type"];
  status?: PipelineRunListParams["status"];
  start_date?: string;
  end_date?: string;
  limit?: number;
}) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.pipeline.list({
      run_type: filters?.run_type,
      status: filters?.status,
      start_date: filters?.start_date,
      end_date: filters?.end_date,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchRunsPage({
        cursor: pageParam,
        limit,
        run_type: filters?.run_type,
        status: filters?.status,
        start_date: filters?.start_date,
        end_date: filters?.end_date,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
    // Listede en az bir aktif run varsa 5 sn poll; hepsi terminal ise durur.
    refetchInterval: (query) => {
      const pages = query.state.data?.pages;
      if (!pages) return false;
      const hasActive = pages.some((page) =>
        page.data.some((run) => isActiveRun(run.status)),
      );
      return hasActive ? LIST_POLL_INTERVAL_MS : false;
    },
  });
}

export function flattenRunPages(
  data: InfiniteData<PaginatedResponse<PipelineRunSummary>> | undefined,
): PipelineRunSummary[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}

export function useTriggerPipeline() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sourceTypes: string[]) => {
      const response = await apiClient.post<TriggerPipelineResponse>(
        "/pipeline/runs",
        { run_type: "collect_pipeline", source_types: sourceTypes },
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.all });
    },
  });
}

export function useTriggerDigestUpdate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      body: Omit<TriggerDigestUpdateRequest, "run_type">,
    ) => {
      const response = await apiClient.post<TriggerPipelineResponse>(
        "/pipeline/runs",
        { run_type: "digest_update", ...body },
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.all });
    },
  });
}

export function useCancelPipelineRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (runId: string) => {
      const response = await apiClient.post<CancelPipelineResponse>(
        `/pipeline/runs/${runId}/cancel`,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.all });
    },
  });
}
