"use client";

import { ErrorView } from "@/components/common/error-view";
import { ExecutiveBriefSkeleton } from "@/components/digest/digest-list-skeleton";
import { formatDateTime } from "@/lib/date-format";
import { useBrief } from "@/hooks/use-brief";
import type { TodayBrief } from "@/types/api";

function BriefStatsBand({ stats }: { stats: TodayBrief["stats"] }) {
  const items = [
    { label: "Kaynak", value: stats.source_count },
    { label: "Yeni bülten", value: stats.new_digest_count },
    { label: "İşlenen haber", value: stats.processed_news_count },
    { label: "Yıldız etkili", value: stats.yildiz_impact_count },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 border-t border-white/15 pt-5 sm:grid-cols-4">
      {items.map((item) => (
        <div key={item.label}>
          <p className="text-xl font-bold text-white">{item.value}</p>
          <p className="text-xs text-white/70">{item.label}</p>
        </div>
      ))}
    </div>
  );
}

function renderSummary(summary: string) {
  const parts = summary.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <span key={index} className="font-semibold text-gold-400">
          {part.slice(2, -2)}
        </span>
      );
    }
    return part;
  });
}

export function ExecutiveBrief() {
  const { data, isLoading, isError, error, refetch } = useBrief();

  if (isLoading) {
    return <ExecutiveBriefSkeleton />;
  }

  if (isError) {
    return (
      <ErrorView
        message={
          error instanceof Error ? error.message : "Günün özeti yüklenemedi."
        }
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (!data || data.status === "pending") {
    return (
      <div className="rounded-xl border border-dashed border-navy-100 bg-white px-6 py-8 text-center">
        <p className="text-sm font-medium text-navy-800">
          Günün özeti hazırlanıyor…
        </p>
        <p className="mt-2 text-sm text-gray-500">
          Yeni bültenler üretildiğinde özet burada görünecek.
        </p>
      </div>
    );
  }

  if (data.status === "empty") {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-white px-6 py-8 text-center">
        <p className="text-sm text-gray-600">
          Bugün için henüz bir özet bulunmuyor.
        </p>
      </div>
    );
  }

  const { brief } = data;

  return (
    <section
      aria-labelledby="executive-brief-heading"
      className="relative overflow-hidden rounded-xl bg-gradient-to-br from-navy-900 via-navy-800 to-navy-700 p-6 shadow-lg"
    >
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gold-500/20 blur-2xl"
        aria-hidden
      />

      <div className="relative space-y-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p
              id="executive-brief-heading"
              className="text-xs font-bold uppercase tracking-wider text-gold-400"
            >
              ⭐ Günün Özeti
            </p>
          </div>
          <p className="text-xs text-white/70">
            {formatDateTime(brief.generated_at)}
          </p>
        </div>

        <p className="text-sm leading-relaxed text-white/95 sm:text-base">
          {renderSummary(brief.summary)}
        </p>

        <BriefStatsBand stats={brief.stats} />
      </div>
    </section>
  );
}
