"use client";

import { useInfiniteQuery, type InfiniteData } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  AuditLogItem,
  AuditLogListParams,
  PaginatedResponse,
} from "@/types/api";

async function fetchAuditLogPage(
  params: AuditLogListParams,
): Promise<PaginatedResponse<AuditLogItem>> {
  const response = await apiClient.get<PaginatedResponse<AuditLogItem>>(
    "/audit-logs",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit ?? 20,
        event_type: params.event_type || undefined,
        actor_user_id: params.actor_user_id || undefined,
        target_type: params.target_type || undefined,
        start_date: params.start_date || undefined,
        end_date: params.end_date || undefined,
      },
    },
  );
  return response.data;
}

export function useAuditLogs(filters?: {
  event_type?: string;
  actor_user_id?: string;
  target_type?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.auditLogs.list({
      event_type: filters?.event_type,
      actor_user_id: filters?.actor_user_id,
      target_type: filters?.target_type,
      start_date: filters?.start_date,
      end_date: filters?.end_date,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchAuditLogPage({
        cursor: pageParam,
        limit,
        event_type: filters?.event_type,
        actor_user_id: filters?.actor_user_id,
        target_type: filters?.target_type,
        start_date: filters?.start_date,
        end_date: filters?.end_date,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
  });
}

export function flattenAuditLogPages(
  data: InfiniteData<PaginatedResponse<AuditLogItem>> | undefined,
): AuditLogItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}
