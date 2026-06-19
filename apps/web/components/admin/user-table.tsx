"use client";

import { useEffect, useRef, useState } from "react";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { formatNumericDate, formatRelativeTime } from "@/lib/date-format";
import { getInitials } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { UserListItem } from "@/types/api";

interface UserTableProps {
  users: UserListItem[];
  currentUserId?: string;
  onEdit: (user: UserListItem) => void;
  onToggleActive: (user: UserListItem) => void;
}

function RoleBadge({ role }: { role: UserListItem["role"] }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
        role === "admin"
          ? "bg-navy-800 text-white"
          : "bg-gray-100 text-gray-600",
      )}
    >
      {role === "admin" ? "Admin" : "Viewer"}
    </span>
  );
}

function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          isActive ? "bg-green-500" : "bg-gray-300",
        )}
        aria-hidden
      />
      {isActive ? "Aktif" : "Pasif"}
    </span>
  );
}

function UserActionsMenu({
  user,
  currentUserId,
  onEdit,
  onToggleActive,
}: {
  user: UserListItem;
  currentUserId?: string;
  onEdit: (user: UserListItem) => void;
  onToggleActive: (user: UserListItem) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const isSelf = currentUserId === user.id;
  const canDeactivate = user.is_active && !isSelf;

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-navy-800"
        aria-label={`${user.full_name} işlemleri`}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        onClick={() => setIsOpen((open) => !open)}
      >
        •••
      </button>

      {isOpen ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-40 rounded-md border border-gray-200 bg-white py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => {
              setIsOpen(false);
              onEdit(user);
            }}
          >
            Düzenle
          </button>
          {canDeactivate ? (
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
              onClick={() => {
                setIsOpen(false);
                onToggleActive(user);
              }}
            >
              Pasif Yap
            </button>
          ) : null}
          {!user.is_active ? (
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
              onClick={() => {
                setIsOpen(false);
                onToggleActive(user);
              }}
            >
              Aktif Yap
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function UserTable({
  users,
  currentUserId,
  onEdit,
  onToggleActive,
}: UserTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead>Kullanıcı</DataTableHead>
          <DataTableHead className="w-[100px]">Rol</DataTableHead>
          <DataTableHead className="w-[100px]">Durum</DataTableHead>
          <DataTableHead className="w-[120px]">Son Giriş</DataTableHead>
          <DataTableHead className="w-[120px]">Oluşturulma</DataTableHead>
          <DataTableHead className="w-[80px]">
            <span className="sr-only">İşlemler</span>
          </DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {users.map((user) => (
            <DataTableRow key={user.id}>
              <DataTableCell>
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-100 text-xs font-bold text-navy-800"
                    aria-hidden
                  >
                    {getInitials(user.full_name)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-gray-900">
                      {user.full_name}
                    </p>
                    <p className="truncate text-sm text-gray-500">{user.email}</p>
                  </div>
                </div>
              </DataTableCell>
              <DataTableCell>
                <RoleBadge role={user.role} />
              </DataTableCell>
              <DataTableCell>
                <StatusBadge isActive={user.is_active} />
              </DataTableCell>
              <DataTableCell className="text-gray-600">
                {formatRelativeTime(user.last_login_at)}
              </DataTableCell>
              <DataTableCell className="text-gray-600">
                {formatNumericDate(user.created_at)}
              </DataTableCell>
              <DataTableCell>
                <UserActionsMenu
                  user={user}
                  currentUserId={currentUserId}
                  onEdit={onEdit}
                  onToggleActive={onToggleActive}
                />
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
