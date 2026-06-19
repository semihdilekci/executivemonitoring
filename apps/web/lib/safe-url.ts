function isDevLocalhost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

export function isSafeExternalUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:") {
      return true;
    }
    if (
      parsed.protocol === "http:" &&
      process.env.NODE_ENV === "development" &&
      isDevLocalhost(parsed.hostname)
    ) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export function getSafeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return isSafeExternalUrl(url) ? url : null;
}
