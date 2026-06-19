"use client";

import { useInfiniteQuery, type InfiniteData } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  ChatHistoryItem,
  ChatHistoryListParams,
  PaginatedResponse,
} from "@/types/api";

async function fetchChatHistoryPage(
  params: ChatHistoryListParams,
): Promise<PaginatedResponse<ChatHistoryItem>> {
  const response = await apiClient.get<PaginatedResponse<ChatHistoryItem>>(
    "/chat/history",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit ?? 20,
        user_id: params.user_id || undefined,
        start_date: params.start_date || undefined,
        end_date: params.end_date || undefined,
      },
    },
  );
  return response.data;
}

export function useChatHistory(filters?: {
  user_id?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.chatHistory.list({
      user_id: filters?.user_id,
      start_date: filters?.start_date,
      end_date: filters?.end_date,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchChatHistoryPage({
        cursor: pageParam,
        limit,
        user_id: filters?.user_id,
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

export function flattenChatHistoryPages(
  data: InfiniteData<PaginatedResponse<ChatHistoryItem>> | undefined,
): ChatHistoryItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}
