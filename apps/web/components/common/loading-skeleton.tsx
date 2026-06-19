import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  className?: string;
  lines?: number;
}

export function LoadingSkeleton({
  className,
  lines = 3,
}: LoadingSkeletonProps) {
  return (
    <div className={cn("animate-pulse space-y-3", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className={cn(
            "h-4 rounded-md bg-gray-200",
            index === lines - 1 && "w-2/3",
          )}
        />
      ))}
      <span className="sr-only">Yükleniyor…</span>
    </div>
  );
}

export function PageLoadingSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-36 animate-pulse rounded-xl bg-gray-200" />
      <div className="space-y-4">
        <LoadingSkeleton lines={4} />
      </div>
    </div>
  );
}

export function UserTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" aria-busy="true">
      <div className="border-b border-gray-100 bg-gray-50/80 px-4 py-3">
        <div className="h-4 w-48 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="flex items-center gap-3 px-4 py-4">
            <div className="h-9 w-9 animate-pulse rounded-full bg-gray-200" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-40 animate-pulse rounded bg-gray-200" />
              <div className="h-3 w-56 animate-pulse rounded bg-gray-200" />
            </div>
            <div className="h-6 w-16 animate-pulse rounded-full bg-gray-200" />
          </div>
        ))}
      </div>
      <span className="sr-only">Kullanıcılar yükleniyor…</span>
    </div>
  );
}

export function SourceTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" aria-busy="true">
      <div className="border-b border-gray-100 bg-gray-50/80 px-4 py-3">
        <div className="h-4 w-40 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="flex items-center gap-3 px-4 py-4">
            <div className="h-6 w-14 animate-pulse rounded-full bg-gray-200" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-44 animate-pulse rounded bg-gray-200" />
              <div className="h-3 w-64 animate-pulse rounded bg-gray-200" />
            </div>
            <div className="h-6 w-11 animate-pulse rounded-full bg-gray-200" />
            <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-gray-200" />
          </div>
        ))}
      </div>
      <span className="sr-only">Kaynaklar yükleniyor…</span>
    </div>
  );
}

export function PromptTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" aria-busy="true">
      <div className="border-b border-gray-100 bg-gray-50/80 px-4 py-3">
        <div className="h-4 w-52 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="flex items-center gap-3 px-4 py-4">
            <div className="flex-1 space-y-2">
              <div className="h-4 w-48 animate-pulse rounded bg-gray-200" />
              <div className="h-3 w-32 animate-pulse rounded bg-gray-200" />
            </div>
            <div className="h-6 w-20 animate-pulse rounded-full bg-gray-200" />
            <div className="h-4 w-10 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
          </div>
        ))}
      </div>
      <span className="sr-only">Prompt şablonları yükleniyor…</span>
    </div>
  );
}

export function ApiKeysSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2" aria-busy="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="animate-pulse space-y-4 rounded-lg border border-gray-200 bg-white p-5"
        >
          <div className="h-6 w-16 rounded-full bg-gray-200" />
          <div className="h-5 w-40 rounded bg-gray-200" />
          <div className="h-10 w-full rounded bg-gray-100" />
          <div className="h-4 w-24 rounded bg-gray-200" />
        </div>
      ))}
      <span className="sr-only">API anahtarları yükleniyor…</span>
    </div>
  );
}

export function AuditLogTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" aria-busy="true">
      <div className="border-b border-gray-100 bg-gray-50/80 px-4 py-3">
        <div className="h-4 w-56 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 10 }).map((_, index) => (
          <div key={index} className="grid grid-cols-5 gap-3 px-4 py-4">
            <div className="h-4 w-28 animate-pulse rounded bg-gray-200" />
            <div className="h-6 w-24 animate-pulse rounded-full bg-gray-200" />
            <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-40 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-6 animate-pulse rounded bg-gray-200" />
          </div>
        ))}
      </div>
      <span className="sr-only">Denetim kayıtları yükleniyor…</span>
    </div>
  );
}

export function ChatHistoryTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white" aria-busy="true">
      <div className="border-b border-gray-100 bg-gray-50/80 px-4 py-3">
        <div className="h-4 w-48 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="flex items-center gap-3 px-4 py-4">
            <div className="h-8 w-8 animate-pulse rounded-full bg-gray-200" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-full max-w-md animate-pulse rounded bg-gray-200" />
              <div className="h-3 w-32 animate-pulse rounded bg-gray-200" />
            </div>
            <div className="h-4 w-12 animate-pulse rounded bg-gray-200" />
            <div className="h-8 w-14 animate-pulse rounded bg-gray-200" />
          </div>
        ))}
      </div>
      <span className="sr-only">Sohbet geçmişi yükleniyor…</span>
    </div>
  );
}

export function NotificationSettingsSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="animate-pulse space-y-4 rounded-lg border border-gray-200 bg-white p-6">
        <div className="h-6 w-48 rounded bg-gray-200" />
        <div className="h-4 w-full max-w-lg rounded bg-gray-200" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-12 w-full rounded bg-gray-100" />
          ))}
        </div>
      </div>
      <div className="animate-pulse space-y-4 rounded-lg border border-gray-200 bg-white p-6">
        <div className="h-6 w-40 rounded bg-gray-200" />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="h-10 rounded bg-gray-100" />
          <div className="h-10 rounded bg-gray-100" />
        </div>
      </div>
      <span className="sr-only">Bildirim ayarları yükleniyor…</span>
    </div>
  );
}
