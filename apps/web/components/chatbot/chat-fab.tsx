"use client";

import Link from "next/link";

interface ChatFabProps {
  digestId: string;
}

export function ChatFab({ digestId }: ChatFabProps) {
  const href = `/chatbot?digest_id=${encodeURIComponent(digestId)}`;

  return (
    <Link
      href={href}
      className="digest-print-hide fixed bottom-6 right-6 z-40 flex h-[52px] w-[52px] items-center justify-center rounded-full bg-gradient-to-br from-navy-800 to-navy-600 text-xl text-gold-400 shadow-lg transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500 focus-visible:ring-offset-2"
      aria-label="AI Chatbot'a git"
    >
      <span aria-hidden>✦</span>
    </Link>
  );
}
