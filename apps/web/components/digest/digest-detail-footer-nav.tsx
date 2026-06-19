import Link from "next/link";

interface DigestDetailFooterNavProps {
  previousId?: string | null;
  nextId?: string | null;
}

export function DigestDetailFooterNav({
  previousId,
  nextId,
}: DigestDetailFooterNavProps) {
  return (
    <nav
      aria-label="Bülten navigasyonu"
      className="no-print flex flex-col items-center justify-between gap-3 border-t border-gray-200 pt-6 sm:flex-row"
    >
      {previousId ? (
        <Link
          href={`/digests/${previousId}`}
          className="text-sm font-semibold text-navy-800 hover:text-gold-500"
        >
          ← Önceki Bülten
        </Link>
      ) : (
        <span className="hidden sm:block sm:w-32" aria-hidden />
      )}

      <Link
        href="/digests"
        className="text-sm font-semibold text-gray-600 hover:text-navy-800"
      >
        Bültenler
      </Link>

      {nextId ? (
        <Link
          href={`/digests/${nextId}`}
          className="text-sm font-semibold text-navy-800 hover:text-gold-500"
        >
          Sonraki Bülten →
        </Link>
      ) : (
        <span className="hidden sm:block sm:w-32" aria-hidden />
      )}
    </nav>
  );
}
