import type { LlmRequestType } from "@/types/api";

/** Atanabilir LLM operasyon tipleri — `request_type_scope` çoklu seçim sırası. */
export const LLM_REQUEST_TYPES: LlmRequestType[] = [
  "digest_generation",
  "chatbot",
  "article_translation",
];

/** TR operasyon etiketleri (`Docs/03` §6). */
export const LLM_REQUEST_TYPE_LABELS: Record<LlmRequestType, string> = {
  digest_generation: "Bülten Üretimi",
  chatbot: "Chatbot",
  article_translation: "Çeviri",
};

/** Kapsam özeti — boş dizi `[]` tüm operasyonlar anlamına gelir. */
export function formatScopeSummary(scope: LlmRequestType[]): string {
  if (scope.length === 0) return "Tüm operasyonlar";
  return scope.map((type) => LLM_REQUEST_TYPE_LABELS[type]).join(", ");
}
