import { getDigestTypeMeta } from "@/lib/digest-labels";
import { cn } from "@/lib/utils";
import type { DigestType } from "@/types/api";

interface DigestTypeBadgeProps {
  digestType: DigestType;
  className?: string;
}

export function DigestTypeBadge({ digestType, className }: DigestTypeBadgeProps) {
  const meta = getDigestTypeMeta(digestType);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        meta.badgeClass,
        className,
      )}
    >
      <span aria-hidden>{meta.emoji}</span>
      {meta.label}
    </span>
  );
}
