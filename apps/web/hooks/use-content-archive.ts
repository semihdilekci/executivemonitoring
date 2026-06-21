"use client";

import { useInfiniteQuery, type InfiniteData } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  PaginatedResponse,
  ProcessedItemListItem,
  ProcessedItemListParams,
} from "@/types/api";

async function fetchContentArchivePage(
  params: ProcessedItemListParams,
): Promise<PaginatedResponse<ProcessedItemListItem>> {
  const response = await apiClient.get<
    PaginatedResponse<ProcessedItemListItem>
  >("/admin/processed-items", {
    params: {
      cursor: params.cursor,
      limit: params.limit ?? 20,
      source_id: params.source_id || undefined,
      schema_category: params.schema_category || undefined,
      content_category: params.content_category || undefined,
      published_from: params.published_from || undefined,
      published_to: params.published_to || undefined,
      min_score: params.min_score ?? undefined,
      topic: params.topic || undefined,
      q: params.q || undefined,
      has_digest: params.has_digest,
      sort_by: params.sort_by,
      sort_dir: params.sort_dir,
    },
  });
  return response.data;
}

export function useContentArchive(filters?: Omit<ProcessedItemListParams, "cursor">) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.contentArchive.list({
      source_id: filters?.source_id,
      schema_category: filters?.schema_category,
      content_category: filters?.content_category,
      published_from: filters?.published_from,
      published_to: filters?.published_to,
      min_score: filters?.min_score,
      topic: filters?.topic,
      q: filters?.q,
      has_digest: filters?.has_digest,
      sort_by: filters?.sort_by,
      sort_dir: filters?.sort_dir,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchContentArchivePage({
        cursor: pageParam,
        limit,
        source_id: filters?.source_id,
        schema_category: filters?.schema_category,
        content_category: filters?.content_category,
        published_from: filters?.published_from,
        published_to: filters?.published_to,
        min_score: filters?.min_score,
        topic: filters?.topic,
        q: filters?.q,
        has_digest: filters?.has_digest,
        sort_by: filters?.sort_by,
        sort_dir: filters?.sort_dir,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
  });
}

export function flattenContentArchivePages(
  data: InfiniteData<PaginatedResponse<ProcessedItemListItem>> | undefined,
): ProcessedItemListItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}
