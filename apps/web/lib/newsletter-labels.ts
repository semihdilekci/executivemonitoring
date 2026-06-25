/**
 * Bülten şablonu ekranı (S-ADMIN-NEWSLETTERS) TR etiketleri ve prompt değişken
 * yardımı (`Docs/06` S-ADMIN-NEWSLETTERS · `Docs/03` §5).
 */

/** Model tercihi seçenekleri — boş değer "varsayılan (otomatik)" anlamına gelir. */
export const NEWSLETTER_MODEL_OPTIONS: readonly {
  value: string;
  label: string;
}[] = [
  { value: "", label: "Varsayılan (otomatik)" },
  { value: "groq", label: "Groq" },
  { value: "gemini", label: "Gemini" },
] as const;

/** Editör (bülten özeti) prompt'unda kullanılabilir placeholder'lar. */
export const NEWSLETTER_SUMMARY_VARIABLES: readonly string[] = [
  "{newsletter_name}",
  "{newsletter_description}",
  "{date_range}",
  "{sections}",
  "{articles}",
] as const;

/** Bölüm özet/etki prompt'unda kullanılabilir placeholder'lar. */
export const NEWSLETTER_SECTION_VARIABLES: readonly string[] = [
  "{section_name}",
  "{newsletter_name}",
  "{date_range}",
  "{articles}",
] as const;

export const NEWSLETTER_DEFAULTS = {
  dateRangeDays: 7,
  minContentScore: 50,
} as const;
