export function DigestDetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-5 w-28 animate-pulse rounded bg-gray-200" />
      <div className="grid gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <div className="hidden space-y-3 lg:block">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="h-8 animate-pulse rounded bg-gray-200"
            />
          ))}
        </div>
        <div className="space-y-4">
          <div className="h-56 animate-pulse rounded-xl bg-gray-200" />
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="h-40 animate-pulse rounded-xl bg-gray-200"
            />
          ))}
        </div>
      </div>
      <span className="sr-only">Bülten detayı yükleniyor…</span>
    </div>
  );
}
