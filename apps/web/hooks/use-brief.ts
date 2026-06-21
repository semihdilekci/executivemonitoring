"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { ApiError, TodayBrief } from "@/types/api";

export type BriefQueryState =
  | { status: "ready"; brief: TodayBrief }
  | { status: "pending" }
  | { status: "empty" };

function isEmptyBrief(brief: TodayBrief): boolean {
  return !brief.summary?.trim();
}

async function fetchTodayBrief(): Promise<BriefQueryState> {
  try {
    const response = await apiClient.get<TodayBrief>("/briefs/today");
    // Boş summary → henüz `ready` bülten yok (Docs/03 §7 briefs/today).
    if (isEmptyBrief(response.data)) {
      return { status: "empty" };
    }
    return { status: "ready", brief: response.data };
  } catch (error) {
    const apiError = error as ApiError;
    // Sözleşme (Docs/03 §7): 404 BRIEF_NOT_READY → özet henüz hazırlanmadı.
    // 204 → veri yok. Backend route henüz yokken (Faz 4 bağımlılığı) ham 404
    // de pending'e düşer; ana sayfa "hazırlanıyor" gösterir, ErrorView değil.
    if (apiError.statusCode === 204) {
      return { status: "empty" };
    }
    if (apiError.statusCode === 404 || apiError.code === "BRIEF_NOT_READY") {
      return { status: "pending" };
    }
    throw error;
  }
}

export function useBrief() {
  return useQuery({
    queryKey: queryKeys.brief.today,
    queryFn: fetchTodayBrief,
    staleTime: 60_000,
  });
}
