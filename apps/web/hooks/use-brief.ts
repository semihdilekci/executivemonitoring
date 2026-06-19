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
    if (isEmptyBrief(response.data)) {
      return { status: "empty" };
    }
    return { status: "ready", brief: response.data };
  } catch (error) {
    const apiError = error as ApiError;
    if (
      apiError.statusCode === 404 ||
      apiError.code === "NOT_FOUND" ||
      apiError.code === "BRIEF_PENDING"
    ) {
      return { status: "pending" };
    }
    if (apiError.code === "NO_BRIEF" || apiError.statusCode === 204) {
      return { status: "empty" };
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
