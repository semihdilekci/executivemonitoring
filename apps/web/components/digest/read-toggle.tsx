"use client";

import { cn } from "@/lib/utils";
import { useDigestReadToggle } from "@/hooks/use-digest-read";
import { isApiError } from "@/types/api";

interface ReadToggleProps {
  digestId: string;
  isRead: boolean;
  className?: string;
}

export function ReadToggle({ digestId, isRead, className }: ReadToggleProps) {
  const toggle = useDigestReadToggle();

  const errorMessage =
    toggle.isError && toggle.error
      ? isApiError(toggle.error)
        ? toggle.error.message
        : "Okuma durumu güncellenemedi."
      : null;

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <button
        type="button"
        aria-label={isRead ? "Okunmadı olarak işaretle" : "Okundu olarak işaretle"}
        aria-pressed={isRead}
        aria-describedby={errorMessage ? `read-toggle-error-${digestId}` : undefined}
        disabled={toggle.isPending}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          toggle.mutate({ digestId, read: !isRead });
        }}
        className={cn(
          "inline-flex h-9 w-9 items-center justify-center rounded-full border text-base transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500 focus-visible:ring-offset-2 disabled:opacity-50",
          isRead
            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
            : "border-gold-400 bg-gold-50 text-gold-500",
          className,
        )}
      >
        <span aria-hidden>{isRead ? "✓" : "👁"}</span>
      </button>
      {errorMessage ? (
        <p
          id={`read-toggle-error-${digestId}`}
          className="max-w-[9rem] text-center text-xs text-red-600"
          role="alert"
        >
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
