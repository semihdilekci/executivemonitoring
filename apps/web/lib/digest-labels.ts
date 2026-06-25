export interface NewsletterBadgeMeta {
  label: string;
  emoji: string;
  badgeClass: string;
}

/**
 * Bilinen seed bültenleri için renkli rozet metası (Faz 6.5).
 *
 * Bülten slug'ları artık serbest olduğundan bu harita yalnızca tanıdık
 * bültenlere özel görsel kimlik verir; bilinmeyen slug'lar `humanizeSlug`
 * ile nötr rozete düşer (asla hata fırlatmaz).
 */
const KNOWN_NEWSLETTERS: Record<string, NewsletterBadgeMeta> = {
  fmcg_weekly: {
    label: "FMCG",
    emoji: "🛒",
    badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
  strategy_weekly: {
    label: "Strateji",
    emoji: "🎯",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-200",
  },
  turkish_media_weekly: {
    label: "Türk Medyası",
    emoji: "📰",
    badgeClass: "bg-blue-100 text-blue-800 border-blue-200",
  },
};

const FALLBACK_BADGE_CLASS = "bg-gray-100 text-gray-700 border-gray-200";

function humanizeSlug(slug: string): string {
  if (!slug) return "Bülten";
  return slug
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function getNewsletterBadgeMeta(slug: string): NewsletterBadgeMeta {
  return (
    KNOWN_NEWSLETTERS[slug] ?? {
      label: humanizeSlug(slug),
      emoji: "🗞️",
      badgeClass: FALLBACK_BADGE_CLASS,
    }
  );
}
