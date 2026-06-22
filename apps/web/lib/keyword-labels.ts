import type { KeywordCategory } from "@/types/api";

/**
 * Keyword kategori TR etiketleri (`Docs/06` S-ADMIN-KEYWORDS).
 * Anahtarlar `keyword_category_enum` = `content_category` ile birebir aynı.
 */
export const KEYWORD_CATEGORY_LABELS: Record<KeywordCategory, string> = {
  macro: "Makroekonomi",
  finance: "Finans",
  fmcg: "FMCG",
  strategy: "Strateji",
  geopolitical: "Jeopolitik",
  regulatory: "Regülasyon",
};

/** Form + tablo için sabit kategori sırası (6 kategori, `Docs/02` §3). */
export const KEYWORD_CATEGORIES: readonly KeywordCategory[] = [
  "macro",
  "finance",
  "fmcg",
  "strategy",
  "geopolitical",
  "regulatory",
] as const;

/** Filtre dropdown'u — boş değer "tüm kategoriler". */
export const KEYWORD_CATEGORY_FILTER_OPTIONS = [
  { value: "", label: "Tüm kategoriler" },
  ...KEYWORD_CATEGORIES.map((category) => ({
    value: category,
    label: KEYWORD_CATEGORY_LABELS[category],
  })),
] as const;

export const KEYWORD_STATUS_FILTER_OPTIONS = [
  { value: "", label: "Tüm durumlar" },
  { value: "true", label: "Aktif" },
  { value: "false", label: "Pasif" },
] as const;

export function getKeywordCategoryLabel(value: string): string {
  return KEYWORD_CATEGORY_LABELS[value as KeywordCategory] ?? value;
}

/** Varsayılan rating — kategori aktifleştirildiğinde başlangıç değeri. */
export const DEFAULT_KEYWORD_RATING = 5;

/**
 * Rating (1–10) yoğunluğuna göre chip renk sınıfı — yüksek rating güçlü
 * temsil (yeşil), orta destekleyici (amber), düşük bağlamsal (gri).
 */
export function getRatingChipClass(rating: number): string {
  if (rating >= 8) return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (rating >= 4) return "bg-amber-100 text-amber-800 border-amber-200";
  return "bg-gray-100 text-gray-700 border-gray-200";
}
