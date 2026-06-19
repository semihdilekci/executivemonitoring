"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { AdminTopbar } from "@/components/layout/admin-topbar";
import { PillNav } from "@/components/layout/pill-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { UserMenu } from "@/components/layout/user-menu";
import { PageLoadingSkeleton } from "@/components/common/loading-skeleton";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAdmin, isLoading } = useAuth();
  const pathname = usePathname();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg p-6">
        <PageLoadingSkeleton />
      </div>
    );
  }

  if (isAdmin) {
    return (
      <div className="min-h-screen bg-bg">
        <div className="hidden lg:block">
          <Sidebar />
        </div>
        <AdminTopbar />
        <main className="min-h-screen lg:ml-sidebar">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    );
  }

  const pillActiveHref = pathname.startsWith("/digests")
    ? "/digests"
    : pathname.startsWith("/chatbot")
      ? "/chatbot"
      : "/";

  return (
    <div className="min-h-screen bg-bg">
      <header className="no-print sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <PillNav activeHref={pillActiveHref} />
          <UserMenu />
        </div>
      </header>
      <main className="w-full">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}
