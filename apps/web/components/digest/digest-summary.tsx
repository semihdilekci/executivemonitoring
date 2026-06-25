import { buildDigestTldr, sortSections } from "@/lib/digest-detail-utils";
import type { DigestDetail } from "@/types/api";

interface DigestSummaryProps {
  digest: DigestDetail;
}

/**
 * Haftalık bülten özeti bloğu (Faz 6.5).
 *
 * Editör LLM'in ürettiği `digest.summary` gösterilir; özet henüz yoksa
 * bölüm özetlerinden türetilen kısa metne düşer.
 */
export function DigestSummary({ digest }: DigestSummaryProps) {
  const summary = digest.summary?.trim();
  const fallback = !summary
    ? buildDigestTldr(sortSections(digest.sections))
    : null;
  const body = summary ?? fallback;

  if (!body) {
    return null;
  }

  return (
    <section
      aria-label="Bülten özeti"
      className="rounded-xl border border-gray-100 border-l-[3px] border-l-gold-500 bg-white p-6 shadow-sm"
    >
      <p className="text-[10px] font-bold uppercase tracking-wider text-gold-500">
        ★ Bülten Özeti
      </p>
      <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-gray-700">
        {body}
      </p>
    </section>
  );
}
