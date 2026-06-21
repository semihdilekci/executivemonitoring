// Docs/05 §13.3 (XSS Koruması): `<a href>` protokol whitelist'i = `https:` veya
// `http:`. `javascript:`, `data:`, `file:` vb. yasak. Haber kaynak linkleri
// gerçek dünyada `http://` olabilir; bunları düşürmek kaynak referansını bozar.
const ALLOWED_PROTOCOLS = new Set(["https:", "http:"]);

export function isSafeExternalUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return ALLOWED_PROTOCOLS.has(parsed.protocol);
  } catch {
    return false;
  }
}

export function getSafeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return isSafeExternalUrl(url) ? url : null;
}
