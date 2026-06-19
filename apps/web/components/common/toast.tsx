"use client";

import { useEffect } from "react";
import { cn } from "@/lib/utils";

export type ToastVariant = "success" | "error";

interface ToastProps {
  message: string;
  variant?: ToastVariant;
  onDismiss: () => void;
  durationMs?: number;
}

export function Toast({
  message,
  variant = "success",
  onDismiss,
  durationMs = 4000,
}: ToastProps) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [durationMs, onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed bottom-6 right-6 z-50 max-w-sm rounded-lg px-4 py-3 text-sm font-medium shadow-lg",
        variant === "success"
          ? "bg-navy-800 text-white"
          : "bg-red-600 text-white",
      )}
    >
      {message}
    </div>
  );
}
