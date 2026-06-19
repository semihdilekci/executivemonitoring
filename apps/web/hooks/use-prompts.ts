"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  CreatePromptTemplateRequest,
  PromptTemplateItem,
  PromptTemplateListResponse,
  UpdatePromptTemplateRequest,
} from "@/types/api";
import type { DigestType } from "@/types/api";

export function usePromptTemplates(filters?: {
  digest_type?: DigestType;
  is_active?: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.promptTemplates.list({
      digest_type: filters?.digest_type,
      is_active: filters?.is_active,
    }),
    queryFn: async () => {
      const response = await apiClient.get<PromptTemplateListResponse>(
        "/prompt-templates",
        {
          params: {
            digest_type: filters?.digest_type,
            is_active: filters?.is_active,
          },
        },
      );
      return response.data.data;
    },
  });
}

export function useCreatePromptTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreatePromptTemplateRequest) => {
      const response = await apiClient.post<PromptTemplateItem>(
        "/prompt-templates",
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.promptTemplates.all,
      });
    },
  });
}

export function useUpdatePromptTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      body,
    }: {
      templateId: string;
      body: UpdatePromptTemplateRequest;
    }) => {
      const response = await apiClient.put<PromptTemplateItem>(
        `/prompt-templates/${templateId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.promptTemplates.all,
      });
    },
  });
}
