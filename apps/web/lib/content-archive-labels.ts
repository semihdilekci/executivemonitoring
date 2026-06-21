import type { ContentCategory, SchemaCategory } from "@/types/api";

/** `schema_category` (domain tablosu) TR etiketleri — `Docs/06` S-ADMIN-CONTENT-ARCHIVE. */
export const SCHEMA_CATEGORY_LABELS: Record<SchemaCategory, string> = {
  news: "Haber",
  market: "Piyasa",
  geo: "Jeopolitik",
  transport: "Lojistik",
  fmcg: "FMCG",
};

/** Enricher içerik kategorisi TR etiketleri — `Docs/04` §8.4 anahtarları. */
export const CONTENT_CATEGORY_LABELS: Record<ContentCategory, string> = {
  macro: "Makroekonomi",
  fmcg: "FMCG",
  finance: "Finans",
  geopolitical: "Jeopolitik",
  strategy: "Strateji",
  regulatory: "Regülasyon",
};

export const SCHEMA_CATEGORY_FILTER_OPTIONS = [
  { value: "", label: "Tüm şemalar" },
  { value: "news", label: "Haber" },
  { value: "market", label: "Piyasa" },
  { value: "geo", label: "Jeopolitik" },
  { value: "transport", label: "Lojistik" },
  { value: "fmcg", label: "FMCG" },
] as const;

export const CONTENT_CATEGORY_FILTER_OPTIONS = [
  { value: "", label: "Tüm kategoriler" },
  { value: "macro", label: "Makroekonomi" },
  { value: "fmcg", label: "FMCG" },
  { value: "finance", label: "Finans" },
  { value: "geopolitical", label: "Jeopolitik" },
  { value: "strategy", label: "Strateji" },
  { value: "regulatory", label: "Regülasyon" },
] as const;

export const HAS_DIGEST_FILTER_OPTIONS = [
  { value: "", label: "Tümü" },
  { value: "true", label: "Kullanıldı" },
  { value: "false", label: "Kullanılmadı" },
] as const;

/** `relevance_score` (0–1) → yüzde rozet metni (örn. 0.82 → "%82"). */
export function formatRelevancePercent(score: number): string {
  return `%${Math.round(score * 100)}`;
}

/** Skora göre rozet renk sınıfı — yüksek alaka yeşil, düşük gri. */
export function getRelevanceBadgeClass(score: number): string {
  if (score >= 0.75) return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (score >= 0.5) return "bg-amber-100 text-amber-800 border-amber-200";
  return "bg-gray-100 text-gray-700 border-gray-200";
}

export function getSchemaCategoryLabel(value: string): string {
  return SCHEMA_CATEGORY_LABELS[value as SchemaCategory] ?? value;
}

export function getContentCategoryLabel(value: string | null): string {
  if (!value) return "—";
  return CONTENT_CATEGORY_LABELS[value as ContentCategory] ?? value;
}
