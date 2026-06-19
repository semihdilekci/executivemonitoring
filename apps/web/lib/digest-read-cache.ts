import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/constants";

/** Backend read endpoint henüz yoksa session-only mod; null = henüz test edilmedi. */
let digestReadApiSupported: boolean | null = null;

export function isDigestReadApiSupported(): boolean | null {
  return digestReadApiSupported;
}

export function markDigestReadApiSupported(supported: boolean): void {
  digestReadApiSupported = supported;
}

export function getSessionReadIds(
  queryClient: QueryClient,
  userId: string,
): Set<string> {
  return (
    queryClient.getQueryData<Set<string>>(
      queryKeys.digests.readState(userId),
    ) ?? new Set()
  );
}

export function updateSessionReadState(
  queryClient: QueryClient,
  userId: string,
  digestId: string,
  read: boolean,
): Set<string> {
  const current = getSessionReadIds(queryClient, userId);
  const next = new Set(current);
  if (read) {
    next.add(digestId);
  } else {
    next.delete(digestId);
  }
  queryClient.setQueryData(queryKeys.digests.readState(userId), next);
  return next;
}

export function resolveDigestIsRead(
  digest: { id: string; is_read?: boolean },
  sessionReadIds: Set<string>,
): boolean {
  if (typeof digest.is_read === "boolean") {
    return digest.is_read;
  }
  return sessionReadIds.has(digest.id);
}
