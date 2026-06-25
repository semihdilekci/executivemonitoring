import { getNewsletterBadgeMeta } from "@/lib/digest-labels";
import { cn } from "@/lib/utils";

interface NewsletterBadgeProps {
  newsletterSlug: string;
  className?: string;
}

/**
 * Bülten rozeti (Faz 6.5) — serbest `newsletter_slug`'tan etiket/renk türetir.
 * Bilinmeyen slug'larda nötr rozete düşer; hiçbir zaman hata fırlatmaz.
 */
export function NewsletterBadge({
  newsletterSlug,
  className,
}: NewsletterBadgeProps) {
  const meta = getNewsletterBadgeMeta(newsletterSlug);

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
