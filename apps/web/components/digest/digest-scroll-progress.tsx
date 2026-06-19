"use client";

import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

export function DigestScrollProgress() {
  const { isAdmin } = useAuth();
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function updateProgress() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      if (scrollable <= 0) {
        setProgress(0);
        return;
      }
      setProgress(Math.min(100, (window.scrollY / scrollable) * 100));
    }

    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);

    return () => {
      window.removeEventListener("scroll", updateProgress);
      window.removeEventListener("resize", updateProgress);
    };
  }, []);

  return (
    <div
      className={cn(
        "no-print pointer-events-none fixed top-0 z-[60] h-[3px] bg-transparent",
        isAdmin ? "left-0 lg:left-sidebar" : "left-0 right-0",
      )}
      style={{ right: 0 }}
      aria-hidden
    >
      <div
        className="h-full bg-gradient-to-r from-gold-400 to-gold-500 transition-[width] duration-150"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
