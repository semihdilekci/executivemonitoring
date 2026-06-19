import type { DigestDetail, DigestSection } from "@/types/api";

export interface DigestDetailStats {
  sectionCount: number;
  newsCount: number;
  yildizImpactCount: number;
}

export function computeDigestStats(digest: DigestDetail): DigestDetailStats {
  const sections = digest.sections ?? [];
  return {
    sectionCount: sections.length,
    newsCount: sections.reduce(
      (total, section) => total + section.source_references.length,
      0,
    ),
    yildizImpactCount: sections.filter((section) =>
      Boolean(section.impact_note?.trim()),
    ).length,
  };
}

export function buildDigestTldr(
  sections: DigestSection[],
  maxLength = 480,
): string {
  if (sections.length === 0) {
    return "Bu bülten için henüz özet metni bulunmuyor.";
  }

  const combined = sections
    .slice(0, 3)
    .map((section) => section.ai_summary.trim())
    .filter(Boolean)
    .join(" ");

  if (combined.length <= maxLength) {
    return combined;
  }

  const truncated = combined.slice(0, maxLength);
  const lastSpace = truncated.lastIndexOf(" ");
  return `${truncated.slice(0, lastSpace > 0 ? lastSpace : maxLength).trim()}…`;
}

export function getSectionAnchorId(section: DigestSection): string {
  return `section-${section.id}`;
}

export function sortSections(sections: DigestSection[]): DigestSection[] {
  return [...sections].sort((a, b) => a.section_order - b.section_order);
}
