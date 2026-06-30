import { NewsDrawerCard } from "@/components/digest/news-drawer-card";
import { getSectionAnchorId } from "@/lib/digest-detail-utils";
import type { DigestSection } from "@/types/api";

interface DigestSectionCardProps {
  section: DigestSection;
}

export function DigestSectionCard({ section }: DigestSectionCardProps) {
  const orderLabel = String(section.section_order).padStart(2, "0");
  const hasImpact = Boolean(section.impact_note?.trim());

  return (
    <article
      id={getSectionAnchorId(section)}
      className="scroll-mt-28 rounded-xl border border-gray-100 bg-white p-6 shadow-sm"
    >
      <header className="flex items-start gap-3">
        <span className="text-sm font-bold text-gray-400">{orderLabel}</span>
        <h2 className="text-base font-bold text-navy-800">
          {section.section_title}
        </h2>
      </header>

      <p className="mt-4 text-sm leading-relaxed text-gray-600">
        {section.ai_summary}
      </p>

      {hasImpact ? (
        <div className="mt-4 rounded-lg border border-gold-200 bg-gold-50 px-4 py-4">
          <p className="text-[10px] font-bold uppercase tracking-wide text-gold-500">
            ★ Yıldız Holding için etki
          </p>
          <p className="mt-2 text-sm leading-relaxed text-gray-700">
            {section.impact_note}
          </p>
        </div>
      ) : null}

      {section.source_references.length > 0 ? (
        <div className="mt-5 space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500">
            Kaynak haberler
          </h4>
          {section.source_references.map((reference) => (
            <NewsDrawerCard
              key={reference.processed_item_id}
              reference={reference}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}
