"use client";

import { getSectionAnchorId } from "@/lib/digest-detail-utils";
import { cn } from "@/lib/utils";
import type { DigestSection } from "@/types/api";
import { useEffect, useState } from "react";

interface DigestTocProps {
  sections: DigestSection[];
  variant?: "sidebar" | "mobile";
}

export function DigestToc({ sections, variant = "sidebar" }: DigestTocProps) {
  const [activeId, setActiveId] = useState<string>(
    sections[0] ? getSectionAnchorId(sections[0]) : "",
  );

  useEffect(() => {
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visible[0]?.target.id) {
          setActiveId(visible[0].target.id);
        }
      },
      {
        rootMargin: "-20% 0px -55% 0px",
        threshold: [0, 0.25, 0.5, 1],
      },
    );

    for (const section of sections) {
      const element = document.getElementById(getSectionAnchorId(section));
      if (element) observer.observe(element);
    }

    return () => observer.disconnect();
  }, [sections]);

  if (sections.length === 0) {
    return null;
  }

  function scrollToSection(section: DigestSection) {
    const element = document.getElementById(getSectionAnchorId(section));
    element?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(getSectionAnchorId(section));
  }

  if (variant === "mobile") {
    return (
      <nav
        aria-label="İçindekiler"
        className="no-print -mx-1 flex gap-2 overflow-x-auto pb-1 lg:hidden"
      >
        {sections.map((section) => {
          const anchorId = getSectionAnchorId(section);
          const isActive = activeId === anchorId;
          return (
            <button
              key={section.id}
              type="button"
              onClick={() => scrollToSection(section)}
              className={cn(
                "shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                isActive
                  ? "border-navy-800 bg-navy-800 text-white"
                  : "border-gray-200 bg-white text-gray-600",
              )}
            >
              {section.section_title}
            </button>
          );
        })}
      </nav>
    );
  }

  return (
    <nav aria-label="İçindekiler" className="no-print hidden lg:block">
      <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
        İçindekiler
      </p>
      <ul className="mt-4 space-y-1">
        {sections.map((section) => {
          const anchorId = getSectionAnchorId(section);
          const isActive = activeId === anchorId;
          const hasImpact = Boolean(section.impact_note?.trim());

          return (
            <li key={section.id}>
              <button
                type="button"
                onClick={() => scrollToSection(section)}
                className={cn(
                  "flex w-full items-start gap-2 border-l-2 py-2 pl-3 text-left text-sm transition-colors",
                  isActive
                    ? "border-gold-500 font-bold text-navy-800"
                    : "border-transparent text-gray-500 hover:border-gray-200 hover:text-navy-800",
                )}
              >
                {hasImpact ? (
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold-500"
                    aria-hidden
                  />
                ) : (
                  <span className="w-1.5 shrink-0" aria-hidden />
                )}
                <span>{section.section_title}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
