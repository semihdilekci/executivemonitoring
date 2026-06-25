"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  CreateNewsletterTemplateRequest,
  NewsletterTemplate,
  NewsletterTemplateListResponse,
  UpdateNewsletterTemplateRequest,
} from "@/types/api";

export function useNewsletterTemplates(filters?: { is_active?: boolean }) {
  return useQuery({
    queryKey: queryKeys.newsletterTemplates.list({
      is_active: filters?.is_active,
    }),
    queryFn: async () => {
      const response = await apiClient.get<NewsletterTemplateListResponse>(
        "/newsletter-templates",
        { params: { is_active: filters?.is_active } },
      );
      return response.data.data;
    },
  });
}

export function useCreateNewsletterTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreateNewsletterTemplateRequest) => {
      const response = await apiClient.post<NewsletterTemplate>(
        "/newsletter-templates",
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.newsletterTemplates.all,
      });
    },
  });
}

export function useUpdateNewsletterTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      body,
    }: {
      templateId: string;
      body: UpdateNewsletterTemplateRequest;
    }) => {
      const response = await apiClient.put<NewsletterTemplate>(
        `/newsletter-templates/${templateId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.newsletterTemplates.all,
      });
    },
  });
}

export function useDeleteNewsletterTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (templateId: string) => {
      await apiClient.delete(`/newsletter-templates/${templateId}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.newsletterTemplates.all,
      });
    },
  });
}
