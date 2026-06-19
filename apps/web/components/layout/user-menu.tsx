"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { getInitials } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface UserMenuProps {
  variant?: "header" | "sidebar";
}

export function UserMenu({ variant = "header" }: UserMenuProps) {
  const { user, logout, isLoading } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      window.location.href = "/login";
    } finally {
      setIsLoggingOut(false);
    }
  };

  const displayName = user?.fullName ?? "Kullanıcı";
  const initials = getInitials(displayName);

  if (isLoading) {
    return (
      <div
        className={cn(
          "h-10 w-10 animate-pulse rounded-full bg-gray-200",
          variant === "sidebar" && "bg-navy-700",
        )}
        aria-hidden
      />
    );
  }

  if (variant === "sidebar") {
    return (
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-700 text-sm font-bold text-gold-400">
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-white/90">
            {displayName}
          </p>
          <p className="text-xs text-gray-500">
            {user?.role === "admin" ? "Yönetici" : "Görüntüleyici"}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-white/70 hover:bg-white/10 hover:text-white"
          onClick={() => void handleLogout()}
          disabled={isLoggingOut}
        >
          Çıkış
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right sm:block">
        <p className="text-sm font-semibold text-gray-800">{displayName}</p>
        <p className="text-xs text-gray-500">
          {user?.role === "admin" ? "Yönetici" : "Görüntüleyici"}
        </p>
      </div>
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-100 text-sm font-bold text-navy-800">
        {initials}
      </div>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => void handleLogout()}
        disabled={isLoggingOut}
      >
        Çıkış
      </Button>
    </div>
  );
}
