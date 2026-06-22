"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  KeywordCreateRequest,
  KeywordListParams,
  KeywordListResponse,
  KeywordResponse,
  KeywordUpdateRequest,
} from "@/types/api";

const KEYWORDS_PATH = "/admin/keywords";

async function fetchKeywords(
  params: KeywordListParams,
): Promise<KeywordListResponse> {
  const response = await apiClient.get<KeywordListResponse>(KEYWORDS_PATH, {
    params: {
      category: params.category,
      q: params.q,
      is_active: params.is_active,
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  });
  return response.data;
}

export function useKeywords(filters?: KeywordListParams) {
  return useQuery({
    queryKey: queryKeys.keywords.list({
      category: filters?.category,
      q: filters?.q,
      is_active: filters?.is_active,
      page: filters?.page ?? 1,
      page_size: filters?.page_size ?? 50,
    }),
    queryFn: () => fetchKeywords(filters ?? {}),
  });
}

export function useCreateKeyword() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: KeywordCreateRequest) => {
      const response = await apiClient.post<KeywordResponse>(
        KEYWORDS_PATH,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.keywords.all });
    },
  });
}

export function useUpdateKeyword() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      keywordId,
      body,
    }: {
      keywordId: string;
      body: KeywordUpdateRequest;
    }) => {
      const response = await apiClient.put<KeywordResponse>(
        `${KEYWORDS_PATH}/${keywordId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.keywords.all });
    },
  });
}

export function useDeleteKeyword() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keywordId: string) => {
      await apiClient.delete(`${KEYWORDS_PATH}/${keywordId}`);
      return keywordId;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.keywords.all });
    },
  });
}
