"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ADMIN_NAV_ITEMS,
  VIEWER_NAV_ITEMS,
} from "@/lib/constants";
import { cn } from "@/lib/utils";
import { AppLogo } from "@/components/common/app-logo";
import { UserMenu } from "./user-menu";

function NavSection({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="mb-2">
      <p className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function SidebarLink({ href, label }: { href: string; label: string }) {
  const pathname = usePathname();
  const isActive =
    href === "/"
      ? pathname === "/"
      : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "bg-gold-500/10 text-gold-400"
          : "text-white/60 hover:bg-white/5 hover:text-white/90",
      )}
      aria-current={isActive ? "page" : undefined}
    >
      {label}
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="no-print fixed inset-y-0 left-0 z-40 flex w-sidebar flex-col bg-navy-900">
      <div className="border-b border-white/10 px-5 py-6">
        <AppLogo size="md" variant="light" className="w-full" />
        <p className="mt-2 text-[11px] font-medium uppercase tracking-wide text-gray-400">
          Global Intelligence Platform
        </p>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="Yönetim menüsü">
        <NavSection label="Ana Menü">
          {VIEWER_NAV_ITEMS.map((item) => (
            <SidebarLink key={item.href} href={item.href} label={item.label} />
          ))}
        </NavSection>

        <NavSection label="Yönetim">
          {ADMIN_NAV_ITEMS.map((item) => (
            <SidebarLink key={item.href} href={item.href} label={item.label} />
          ))}
        </NavSection>
      </nav>

      <div className="border-t border-white/10 p-4">
        <UserMenu variant="sidebar" />
      </div>
    </aside>
  );
}
