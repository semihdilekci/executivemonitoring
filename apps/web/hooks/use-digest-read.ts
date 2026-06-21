"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import {
  getSessionReadIds,
  isDigestReadApiSupported,
  markDigestReadApiSupported,
  updateSessionReadState,
} from "@/lib/digest-read-cache";
import type { ApiError } from "@/types/api";
import { useAuth } from "./use-auth";

function isReadEndpointUnavailable(error: ApiError): boolean {
  return error.statusCode === 404 || error.statusCode === 405;
}

async function syncReadToApi(digestId: string, read: boolean): Promise<void> {
  if (isDigestReadApiSupported() === false) {
    return;
  }

  try {
    if (read) {
      await apiClient.post(`/digests/${digestId}/read`);
    } else {
      await apiClient.delete(`/digests/${digestId}/read`);
    }
    markDigestReadApiSupported(true);
  } catch (error) {
    const apiError = error as ApiError;
    if (isDigestReadApiSupported() === null && isReadEndpointUnavailable(apiError)) {
      markDigestReadApiSupported(false);
      return;
    }
    throw error;
  }
}

export function useDigestReadToggle() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userId = user?.id ?? "";

  return useMutation({
    mutationFn: async ({
      digestId,
      read,
    }: {
      digestId: string;
      read: boolean;
    }) => {
      if (!userId) {
        throw new Error("Oturum bulunamadı.");
      }

      await syncReadToApi(digestId, read);
      return { digestId, read };
    },
    onMutate: async ({ digestId, read }) => {
      if (!userId) return undefined;

      await queryClient.cancelQueries({
        queryKey: queryKeys.digests.readState(userId),
      });
      const previous = getSessionReadIds(queryClient, userId);
      updateSessionReadState(queryClient, userId, digestId, read);
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (!userId || !context?.previous) return;
      queryClient.setQueryData(
        queryKeys.digests.readState(userId),
        context.previous,
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.digests.all });
    },
  });
}
