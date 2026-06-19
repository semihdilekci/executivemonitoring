"use client";

import { cn } from "@/lib/utils";
import { useDigestReadToggle } from "@/hooks/use-digest-read";

interface ReadToggleProps {
  digestId: string;
  isRead: boolean;
  className?: string;
}

export function ReadToggle({ digestId, isRead, className }: ReadToggleProps) {
  const toggle = useDigestReadToggle();

  return (
    <button
      type="button"
      aria-label={isRead ? "Okunmadı olarak işaretle" : "Okundu olarak işaretle"}
      aria-pressed={isRead}
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
  );
}
