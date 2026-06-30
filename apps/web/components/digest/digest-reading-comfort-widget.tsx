"use client";

import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import {
  DIGEST_READING_SCALE_MAX,
  DIGEST_READING_SCALE_MIN,
  type DigestReadingTheme,
} from "@/lib/digest-reading-comfort";

interface DigestReadingComfortWidgetProps {
  scale: number;
  theme: DigestReadingTheme;
  onIncreaseScale: () => void;
  onDecreaseScale: () => void;
  onThemeChange: (theme: DigestReadingTheme) => void;
}

const THEME_OPTIONS: Array<{
  id: DigestReadingTheme;
  label: string;
  shortLabel: string;
  swatchClass: string;
  activeBorderClass: string;
}> = [
  {
    id: "paper",
    label: "Kağıt modu",
    shortLabel: "K",
    swatchClass: "bg-[#f4ecd8] text-[#5c4f3f] border-[#dccfb8] hover:bg-[#ebe0c8]",
    activeBorderClass: "border-[#a8895c] ring-1 ring-[#a8895c]/40",
  },
  {
    id: "light",
    label: "Açık mod",
    shortLabel: "A",
    swatchClass: "bg-white text-navy-800 border-gray-200 hover:bg-gray-50",
    activeBorderClass: "border-navy-800 ring-1 ring-navy-800/25",
  },
  {
    id: "dark",
    label: "Koyu mod",
    shortLabel: "D",
    swatchClass: "bg-slate-800 text-slate-100 border-slate-600 hover:bg-slate-700",
    activeBorderClass: "border-gold-400 ring-1 ring-gold-400/35",
  },
];

function ScaleButton({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200 bg-white text-lg font-bold leading-none text-black transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500 disabled:cursor-not-allowed disabled:opacity-35",
        className,
      )}
      {...props}
    />
  );
}

export function DigestReadingComfortWidget({
  scale,
  theme,
  onIncreaseScale,
  onDecreaseScale,
  onThemeChange,
}: DigestReadingComfortWidgetProps) {
  const { isAdmin } = useAuth();
  const percent = Math.round(scale * 100);
  const canDecrease = scale > DIGEST_READING_SCALE_MIN;
  const canIncrease = scale < DIGEST_READING_SCALE_MAX;

  return (
    <div
      role="toolbar"
      aria-label="Okuma ayarları"
      className={cn(
        "digest-print-hide fixed right-4 z-40 flex items-center gap-1 rounded-full border border-gray-200/80 bg-white/90 px-1.5 py-1 shadow-md backdrop-blur-sm sm:right-6",
        isAdmin ? "top-[4.5rem] lg:top-6" : "top-[4.5rem]",
      )}
    >
      <ScaleButton
        onClick={onDecreaseScale}
        disabled={!canDecrease}
        aria-label="Metni küçült"
      >
        −
      </ScaleButton>

      <span
        className="min-w-[2.75rem] text-center text-[11px] font-semibold tabular-nums text-gray-600"
        aria-live="polite"
        aria-atomic="true"
      >
        {percent}%
      </span>

      <ScaleButton
        onClick={onIncreaseScale}
        disabled={!canIncrease}
        aria-label="Metni büyüt"
      >
        +
      </ScaleButton>

      <span className="mx-0.5 h-4 w-px bg-gray-200" aria-hidden />

      <div
        role="group"
        aria-label="Görünüm modu"
        className="flex items-center gap-1"
      >
        {THEME_OPTIONS.map((option) => {
          const isActive = theme === option.id;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onThemeChange(option.id)}
              aria-label={option.label}
              aria-pressed={isActive}
              title={option.label}
              className={cn(
                "inline-flex h-7 min-w-7 items-center justify-center rounded-md border text-xs font-bold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500",
                option.swatchClass,
                isActive
                  ? cn("border-2", option.activeBorderClass)
                  : "border",
              )}
            >
              {option.shortLabel}
            </button>
          );
        })}
      </div>
    </div>
  );
}
