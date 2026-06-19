"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { VIEWER_NAV_ITEMS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { NavItem } from "@/types/models";

interface PillNavProps {
  items?: readonly NavItem[];
  activeHref?: string;
}

function resolveActiveHref(pathname: string, activeHref?: string): string {
  if (activeHref) return activeHref;
  if (pathname.startsWith("/digests")) return "/digests";
  if (pathname.startsWith("/chatbot")) return "/chatbot";
  return "/";
}

export function PillNav({
  items = VIEWER_NAV_ITEMS,
  activeHref,
}: PillNavProps) {
  const pathname = usePathname();
  const navRef = useRef<HTMLElement>(null);
  const resolvedActive = resolveActiveHref(pathname, activeHref);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (prefersReducedMotion || !navRef.current) return;

    const links = navRef.current.querySelectorAll("[data-pill-link]");
    gsap.fromTo(
      links,
      { opacity: 0, y: 8 },
      {
        opacity: 1,
        y: 0,
        duration: 0.35,
        stagger: 0.06,
        ease: "power2.out",
      },
    );
  }, []);

  return (
    <nav
      ref={navRef}
      aria-label="Ana navigasyon"
      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white p-1 shadow-sm"
    >
      {items.map((item) => {
        const isActive = resolvedActive === item.href;

        return (
          <Link
            key={item.href}
            href={item.href}
            data-pill-link
            className={cn(
              "rounded-full px-4 py-2 text-sm font-semibold transition-colors",
              isActive
                ? "bg-navy-800 text-white shadow-sm"
                : "text-gray-600 hover:bg-gray-50 hover:text-navy-800",
            )}
            aria-current={isActive ? "page" : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
