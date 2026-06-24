"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/constants";
import type { ProcessedItemDetail, SchemaCategory } from "@/types/api";

/**
 * Tek işlenmiş içerik detayı. Faz 6.4 sonrası tüm haberler `news.processed_items`'da
 * olduğundan `schema_category` varsayılan `"news"` (`Docs/03` §11.6); çağıran liste
 * satırının schema'sını geçebilir ama boşken `news`'e düşer. `id` boşken (drawer kapalı)
 * sorgu devre dışı.
 */
export function useContentArchiveDetail(
  id: string | null,
  schemaCategory: SchemaCategory | null = "news",
) {
  const resolvedSchema: SchemaCategory = schemaCategory ?? "news";
  return useQuery({
    queryKey: queryKeys.contentArchive.detail(id ?? "", resolvedSchema),
    queryFn: async () => {
      const response = await apiClient.get<ProcessedItemDetail>(
        `/admin/processed-items/${id}`,
        { params: { schema_category: resolvedSchema } },
      );
      return response.data;
    },
    enabled: Boolean(id),
  });
}
