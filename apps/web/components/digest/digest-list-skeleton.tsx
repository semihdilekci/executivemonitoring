import { cn } from "@/lib/utils";

export function ExecutiveBriefSkeleton() {
  return (
    <div
      className="animate-pulse overflow-hidden rounded-xl bg-navy-800 p-6"
      aria-busy="true"
      aria-hidden
    >
      <div className="flex justify-between gap-4">
        <div className="h-4 w-32 rounded bg-white/20" />
        <div className="h-4 w-40 rounded bg-white/20" />
      </div>
      <div className="mt-6 space-y-3">
        <div className="h-4 w-full rounded bg-white/20" />
        <div className="h-4 w-5/6 rounded bg-white/20" />
        <div className="h-4 w-2/3 rounded bg-white/20" />
      </div>
      <div className="mt-6 grid grid-cols-2 gap-4 border-t border-white/10 pt-6 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-10 rounded bg-white/15" />
        ))}
      </div>
      <span className="sr-only">Günün özeti yükleniyor…</span>
    </div>
  );
}

export function TeaserSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-hidden>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className={cn("h-14 animate-pulse rounded-lg bg-gray-200")}
        />
      ))}
    </div>
  );
}

export function DigestListSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, index) => (
          <div
            key={index}
            className="h-44 animate-pulse rounded-xl bg-gray-200"
          />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-16 animate-pulse rounded-lg bg-gray-200"
          />
        ))}
      </div>
      <span className="sr-only">Bültenler yükleniyor…</span>
    </div>
  );
}
