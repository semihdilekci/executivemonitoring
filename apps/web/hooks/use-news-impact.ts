"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import { isApiError, type NewsImpactResponse } from "@/types/api";

export type NewsImpactStatus = "idle" | "loading" | "success" | "error";

interface NewsImpactState {
  status: NewsImpactStatus;
  analysis: string | null;
  errorMessage: string | null;
}

const INITIAL_STATE: NewsImpactState = {
  status: "idle",
  analysis: null,
  errorMessage: null,
};

function resolveErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.statusCode === 429) {
      return "Çok fazla istek gönderildi. Lütfen biraz bekleyin.";
    }
    return error.message;
  }
  return "Analiz alınamadı. Lütfen tekrar deneyin.";
}

/**
 * "Yıldız'ı nasıl etkiler?" anlık etki analizi (Faz 6.5).
 *
 * Sonuç `processed_item_id` anahtarıyla React Query cache'ine yazılır;
 * aynı haber için ikinci tıklamada LLM yeniden çağrılmaz — sonuç cache'ten döner.
 */
export function useNewsImpact(processedItemId: string) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<NewsImpactState>(INITIAL_STATE);

  const requestImpact = useCallback(async () => {
    if (state.status === "loading" || state.status === "success") {
      return;
    }

    setState({ status: "loading", analysis: null, errorMessage: null });

    try {
      const analysis = await queryClient.fetchQuery({
        queryKey: queryKeys.newsImpact.detail(processedItemId),
        queryFn: async () => {
          const response = await apiClient.post<NewsImpactResponse>(
            "/digests/news-impact",
            { processed_item_id: processedItemId },
          );
          return response.data.analysis;
        },
        staleTime: Number.POSITIVE_INFINITY,
      });

      setState({ status: "success", analysis, errorMessage: null });
    } catch (error) {
      setState({
        status: "error",
        analysis: null,
        errorMessage: resolveErrorMessage(error),
      });
    }
  }, [processedItemId, queryClient, state.status]);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  return {
    status: state.status,
    analysis: state.analysis,
    errorMessage: state.errorMessage,
    isLoading: state.status === "loading",
    requestImpact,
    reset,
  };
}
