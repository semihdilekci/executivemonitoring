"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { ProcessedItemDetail, SchemaCategory } from "@/types/api";

/**
 * Tek işlenmiş içerik detayı — `schema_category` zorunlu (cross-schema lookup,
 * `Docs/03` §11.6). `id`/`schema` boşken sorgu devre dışı (drawer kapalı).
 */
export function useContentArchiveDetail(
  id: string | null,
  schemaCategory: SchemaCategory | null,
) {
  return useQuery({
    queryKey: queryKeys.contentArchive.detail(id ?? "", schemaCategory ?? ""),
    queryFn: async () => {
      const response = await apiClient.get<ProcessedItemDetail>(
        `/admin/processed-items/${id}`,
        { params: { schema_category: schemaCategory } },
      );
      return response.data;
    },
    enabled: Boolean(id) && Boolean(schemaCategory),
  });
}
