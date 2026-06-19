"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { cn } from "@/lib/utils";

interface AdminTopbarProps {
  title?: string;
}

export function AdminTopbar({ title = "YGIP Yönetim" }: AdminTopbarProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <>
      <header className="no-print sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 lg:hidden">
        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-gray-200 text-navy-800"
          aria-label="Menüyü aç"
          aria-expanded={isSidebarOpen}
          onClick={() => setIsSidebarOpen((open) => !open)}
        >
          <span className="text-lg leading-none">☰</span>
        </button>
        <p className="text-sm font-semibold text-navy-800">{title}</p>
        <div className="w-10" aria-hidden />
      </header>

      {isSidebarOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          aria-label="Menüyü kapat"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <div
        className={cn(
          "lg:hidden",
          isSidebarOpen ? "block" : "hidden",
        )}
      >
        <Sidebar />
      </div>
    </>
  );
}
