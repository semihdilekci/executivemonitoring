"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  CreateSourceRequest,
  DeleteSourceResponse,
  PaginatedResponse,
  PatchSourceStatusRequest,
  SourceListItem,
  SourceListParams,
  UpdateSourceRequest,
} from "@/types/api";

async function fetchSourcePage(
  params: SourceListParams,
): Promise<PaginatedResponse<SourceListItem>> {
  const response = await apiClient.get<PaginatedResponse<SourceListItem>>(
    "/sources",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit ?? 20,
        source_type: params.source_type,
        status: params.status,
        category: params.category,
        q: params.q,
      },
    },
  );
  return response.data;
}

export function useSources(filters?: {
  source_type?: SourceListParams["source_type"];
  status?: SourceListParams["status"];
  category?: SourceListParams["category"];
  q?: string;
  limit?: number;
}) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.sources.list({
      source_type: filters?.source_type,
      status: filters?.status,
      category: filters?.category,
      q: filters?.q,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchSourcePage({
        cursor: pageParam,
        limit,
        source_type: filters?.source_type,
        status: filters?.status,
        category: filters?.category,
        q: filters?.q,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
  });
}

export function flattenSourcePages(
  data: InfiniteData<PaginatedResponse<SourceListItem>> | undefined,
): SourceListItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}

export function useCreateSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreateSourceRequest) => {
      const response = await apiClient.post<SourceListItem>("/sources", body);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources.all });
    },
  });
}

export function useUpdateSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      sourceId,
      body,
    }: {
      sourceId: string;
      body: UpdateSourceRequest;
    }) => {
      const response = await apiClient.put<SourceListItem>(
        `/sources/${sourceId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources.all });
    },
  });
}

export function usePatchSourceStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      sourceId,
      body,
    }: {
      sourceId: string;
      body: PatchSourceStatusRequest;
    }) => {
      const response = await apiClient.patch<SourceListItem>(
        `/sources/${sourceId}/status`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources.all });
    },
  });
}

export function useDeleteSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sourceId: string) => {
      const response = await apiClient.delete<DeleteSourceResponse>(
        `/sources/${sourceId}`,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources.all });
    },
  });
}
