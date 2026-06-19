"use client";

import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { useMemo } from "react";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import {
  getSessionReadIds,
  resolveDigestIsRead,
} from "@/lib/digest-read-cache";
import type {
  DigestListItem,
  DigestListParams,
  PaginatedResponse,
} from "@/types/api";
import { useAuth } from "./use-auth";

async function fetchDigestPage(
  params: DigestListParams,
): Promise<PaginatedResponse<DigestListItem>> {
  const response = await apiClient.get<PaginatedResponse<DigestListItem>>(
    "/digests",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit,
        digest_type: params.digest_type,
        status: params.status ?? "ready",
        ...(params.is_read !== undefined && { is_read: params.is_read }),
      },
    },
  );
  return response.data;
}

export function useDigests(options?: {
  digestType?: DigestListParams["digest_type"];
  limit?: number;
  isRead?: boolean;
}) {
  const limit = options?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.digests.list({
      digestType: options?.digestType,
      limit,
      isRead: options?.isRead,
    }),
    queryFn: ({ pageParam }) =>
      fetchDigestPage({
        cursor: pageParam,
        limit,
        digest_type: options?.digestType,
        status: "ready",
        is_read: options?.isRead,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
  });
}

export function useDigestReadState() {
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: queryKeys.digests.readState(userId),
    queryFn: () => getSessionReadIds(queryClient, userId),
    enabled: Boolean(userId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function flattenDigestPages(
  data: InfiniteData<PaginatedResponse<DigestListItem>> | undefined,
): DigestListItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}

export function useDigestsWithRead(options?: {
  digestType?: DigestListParams["digest_type"];
  limit?: number;
}) {
  const query = useDigests(options);
  const readStateQuery = useDigestReadState();

  const digests = useMemo(
    () => flattenDigestPages(query.data),
    [query.data],
  );

  const readIds = readStateQuery.data ?? new Set<string>();

  const withReadFlag = useMemo(
    () =>
      digests.map((digest) => ({
        ...digest,
        isRead: resolveDigestIsRead(digest, readIds),
      })),
    [digests, readIds],
  );

  const unread = withReadFlag.filter((item) => !item.isRead);
  const read = withReadFlag.filter((item) => item.isRead);

  return {
    ...query,
    digests: withReadFlag,
    unread,
    read,
    unreadCount: unread.length,
  };
}

export function useUnreadDigestTeasers(limit = 3) {
  const readStateQuery = useDigestReadState();
  const readIds = readStateQuery.data ?? new Set<string>();

  const query = useQuery({
    queryKey: queryKeys.digests.list({ isRead: false, limit }),
    queryFn: () =>
      fetchDigestPage({
        limit,
        status: "ready",
        is_read: false,
      }),
    staleTime: 60_000,
  });

  const teasers = useMemo(() => {
    const items = query.data?.data ?? [];
    return items
      .filter((digest) => !resolveDigestIsRead(digest, readIds))
      .slice(0, limit);
  }, [query.data, readIds, limit]);

  return {
    teasers,
    isLoading: query.isLoading || readStateQuery.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

export type DigestWithRead = DigestListItem & { isRead: boolean };
