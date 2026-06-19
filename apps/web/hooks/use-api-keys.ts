"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  ApiKeyItem,
  ApiKeyListResponse,
  ApiUsageStatsParams,
  ApiUsageStatsResponse,
  CreateApiKeyRequest,
  DeleteApiKeyResponse,
  PatchApiKeyStatusRequest,
} from "@/types/api";

export function useApiKeys() {
  return useQuery({
    queryKey: queryKeys.apiKeys.all,
    queryFn: async () => {
      const response = await apiClient.get<ApiKeyListResponse>("/api-keys");
      return response.data.data;
    },
  });
}

export function useApiKeyUsageStats(params?: ApiUsageStatsParams) {
  return useQuery({
    queryKey: queryKeys.apiKeys.usage(params),
    queryFn: async () => {
      const response = await apiClient.get<ApiUsageStatsResponse>(
        "/api-keys/usage-stats",
        { params },
      );
      return response.data;
    },
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreateApiKeyRequest) => {
      const response = await apiClient.post<ApiKeyItem>("/api-keys", body);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys.all });
      void queryClient.invalidateQueries({
        queryKey: ["api-keys", "usage"],
      });
    },
  });
}

export function usePatchApiKeyStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      keyId,
      body,
    }: {
      keyId: string;
      body: PatchApiKeyStatusRequest;
    }) => {
      const response = await apiClient.patch<ApiKeyItem>(
        `/api-keys/${keyId}/status`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys.all });
    },
  });
}

export function useDeleteApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (keyId: string) => {
      const response = await apiClient.delete<DeleteApiKeyResponse>(
        `/api-keys/${keyId}`,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys.all });
      void queryClient.invalidateQueries({
        queryKey: ["api-keys", "usage"],
      });
    },
  });
}
