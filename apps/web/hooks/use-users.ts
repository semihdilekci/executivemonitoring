"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type {
  CreateUserRequest,
  PaginatedResponse,
  PasswordResetInitiateRequest,
  PasswordResetInitiateResponse,
  UpdateUserRequest,
  UserListItem,
  UserListParams,
} from "@/types/api";

async function fetchUserPage(
  params: UserListParams,
): Promise<PaginatedResponse<UserListItem>> {
  const response = await apiClient.get<PaginatedResponse<UserListItem>>(
    "/users",
    {
      params: {
        cursor: params.cursor,
        limit: params.limit ?? 20,
        role: params.role,
        is_active: params.is_active,
      },
    },
  );
  return response.data;
}

export function useUsers(filters?: {
  role?: UserListParams["role"];
  is_active?: boolean;
  limit?: number;
}) {
  const limit = filters?.limit ?? 20;

  return useInfiniteQuery({
    queryKey: queryKeys.users.list({
      role: filters?.role,
      is_active: filters?.is_active,
      limit,
    }),
    queryFn: ({ pageParam }) =>
      fetchUserPage({
        cursor: pageParam,
        limit,
        role: filters?.role,
        is_active: filters?.is_active,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? (lastPage.pagination.next_cursor ?? undefined)
        : undefined,
  });
}

export function flattenUserPages(
  data: InfiniteData<PaginatedResponse<UserListItem>> | undefined,
): UserListItem[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.data);
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CreateUserRequest) => {
      const response = await apiClient.post<UserListItem>("/users", body);
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string;
      body: UpdateUserRequest;
    }) => {
      const response = await apiClient.put<UserListItem>(
        `/users/${userId}`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

export function useInitiatePasswordReset() {
  return useMutation({
    mutationFn: async (body: PasswordResetInitiateRequest) => {
      const response = await apiClient.post<PasswordResetInitiateResponse>(
        "/auth/password-reset/initiate",
        body,
      );
      return response.data;
    },
  });
}
