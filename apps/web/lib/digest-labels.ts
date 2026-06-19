import type { DigestType } from "@/types/api";

export interface DigestTypeMeta {
  label: string;
  emoji: string;
  badgeClass: string;
}

export const DIGEST_TYPE_META: Record<DigestType, DigestTypeMeta> = {
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

export const DIGEST_TYPE_FILTERS: { value: DigestType | "all"; label: string }[] =
  [
    { value: "all", label: "Tümü" },
    { value: "turkish_media_weekly", label: "Türk Medyası" },
    { value: "fmcg_weekly", label: "FMCG" },
    { value: "strategy_weekly", label: "Strateji" },
  ];

export function getDigestTypeMeta(digestType: DigestType): DigestTypeMeta {
  return DIGEST_TYPE_META[digestType];
}
