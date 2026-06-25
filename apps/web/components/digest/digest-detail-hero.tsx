import { NewsletterBadge } from "@/components/digest/newsletter-badge";
import { computeDigestStats } from "@/lib/digest-detail-utils";
import { formatDateTime, formatPeriodRange } from "@/lib/date-format";
import type { DigestDetail } from "@/types/api";

interface DigestDetailHeroProps {
  digest: DigestDetail;
}

export function DigestDetailHero({ digest }: DigestDetailHeroProps) {
  const stats = computeDigestStats(digest);
  const publishedAt = digest.completed_at ?? digest.created_at;

  return (
    <section
      aria-labelledby="digest-detail-title"
      className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm"
    >
      <div className="space-y-4">
        <NewsletterBadge newsletterSlug={digest.newsletter_slug} />

        <div>
          <h1
            id="digest-detail-title"
            className="text-[22px] font-extrabold leading-tight text-navy-800"
          >
            {digest.title}
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            {formatPeriodRange(digest.period_start, digest.period_end)} ·{" "}
            {digest.total_sources_used} kaynaktan derlendi · {stats.sectionCount}{" "}
            bölüm
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-gray-500">Kaynak</dt>
            <dd className="font-semibold text-navy-800">
              {digest.total_sources_used}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Haber</dt>
            <dd className="font-semibold text-navy-800">{stats.newsCount}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Yıldız etkili bölüm</dt>
            <dd className="font-semibold text-navy-800">
              {stats.yildizImpactCount}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Oluşturulma</dt>
            <dd className="font-semibold text-navy-800">
              {formatDateTime(publishedAt)}
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
