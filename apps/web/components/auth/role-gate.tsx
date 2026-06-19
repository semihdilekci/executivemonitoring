"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/hooks/use-auth";
import { PageLoadingSkeleton } from "@/components/common/loading-skeleton";

interface RoleGateProps {
  children: ReactNode;
}

export function RoleGate({ children }: RoleGateProps) {
  const { isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return <PageLoadingSkeleton />;
  }

  if (!isAdmin) {
    return null;
  }

  return <>{children}</>;
}
