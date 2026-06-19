"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { DigestDetail } from "@/types/api";
import { isApiError } from "@/types/api";

async function fetchDigestDetail(id: string): Promise<DigestDetail> {
  const response = await apiClient.get<DigestDetail>(`/digests/${id}`);
  return response.data;
}

export function useDigestDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.digests.detail(id),
    queryFn: () => fetchDigestDetail(id),
    enabled: Boolean(id),
    retry: (failureCount, error) => {
      if (isApiError(error) && error.statusCode === 404) return false;
      return failureCount < 2;
    },
  });
}
