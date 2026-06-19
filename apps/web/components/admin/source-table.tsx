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
import { formatRelativeTime } from "@/lib/date-format";
import { getSourceEndpointLabel } from "@/lib/source-config";
import {
  SOURCE_CATEGORY_LABELS,
  SOURCE_TYPE_COLORS,
  SOURCE_TYPE_LABELS,
} from "@/lib/source-labels";
import { cn } from "@/lib/utils";
import type { SourceListItem } from "@/types/api";

interface SourceTableProps {
  sources: SourceListItem[];
  onEdit: (source: SourceListItem) => void;
  onDelete: (source: SourceListItem) => void;
  onToggleStatus: (source: SourceListItem) => void;
  togglingSourceId?: string | null;
}

function SourceTypeBadge({ sourceType }: { sourceType: SourceListItem["source_type"] }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
        SOURCE_TYPE_COLORS[sourceType],
      )}
    >
      {SOURCE_TYPE_LABELS[sourceType]}
    </span>
  );
}

function HealthIndicator({ source }: { source: SourceListItem }) {
  const color =
    source.status === "error"
      ? "bg-red-500"
      : source.error_count > 0
        ? "bg-yellow-500"
        : "bg-green-500";

  const label =
    source.status === "error"
      ? `Hatalı — ${source.error_count} hata`
      : source.error_count > 0
        ? `${source.error_count} hata kaydı`
        : "Sorunsuz";

  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={label}
      aria-label={`Sağlık: ${label}`}
    >
      <span className={cn("h-2.5 w-2.5 rounded-full", color)} aria-hidden />
    </span>
  );
}

function StatusToggle({
  source,
  onToggle,
  isLoading,
}: {
  source: SourceListItem;
  onToggle: (source: SourceListItem) => void;
  isLoading: boolean;
}) {
  const isActive = source.status === "active";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isActive}
      aria-label={`${source.name} durumu: ${isActive ? "aktif" : "pasif"}`}
      disabled={isLoading}
      onClick={() => onToggle(source)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        isActive ? "bg-green-500" : "bg-gray-300",
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
          isActive ? "translate-x-5" : "translate-x-0.5",
          "mt-0.5",
        )}
        aria-hidden
      />
    </button>
  );
}

function SourceActionsMenu({
  source,
  onEdit,
  onDelete,
}: {
  source: SourceListItem;
  onEdit: (source: SourceListItem) => void;
  onDelete: (source: SourceListItem) => void;
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

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-navy-800"
        aria-label={`${source.name} işlemleri`}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        onClick={() => setIsOpen((open) => !open)}
      >
        •••
      </button>

      {isOpen ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-36 rounded-md border border-gray-200 bg-white py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => {
              setIsOpen(false);
              onEdit(source);
            }}
          >
            Düzenle
          </button>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
            onClick={() => {
              setIsOpen(false);
              onDelete(source);
            }}
          >
            Sil
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function SourceTable({
  sources,
  onEdit,
  onDelete,
  onToggleStatus,
  togglingSourceId,
}: SourceTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead>Kaynak</DataTableHead>
          <DataTableHead className="w-[90px]">Tip</DataTableHead>
          <DataTableHead className="w-[110px]">Kategori</DataTableHead>
          <DataTableHead className="w-[80px]">Durum</DataTableHead>
          <DataTableHead className="w-[60px]">Sağlık</DataTableHead>
          <DataTableHead className="w-[120px]">Son Çekim</DataTableHead>
          <DataTableHead className="w-[80px]">
            <span className="sr-only">İşlemler</span>
          </DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {sources.map((source) => {
            const endpoint = getSourceEndpointLabel(
              source.source_type,
              source.config,
            );

            return (
              <DataTableRow key={source.id}>
                <DataTableCell>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-gray-900">
                      {source.name}
                    </p>
                    <p className="truncate text-sm text-gray-500">{endpoint}</p>
                  </div>
                </DataTableCell>
                <DataTableCell>
                  <SourceTypeBadge sourceType={source.source_type} />
                </DataTableCell>
                <DataTableCell>
                  <span className="text-sm text-gray-700">
                    {SOURCE_CATEGORY_LABELS[source.category]}
                  </span>
                </DataTableCell>
                <DataTableCell>
                  <StatusToggle
                    source={source}
                    onToggle={onToggleStatus}
                    isLoading={togglingSourceId === source.id}
                  />
                </DataTableCell>
                <DataTableCell>
                  <HealthIndicator source={source} />
                </DataTableCell>
                <DataTableCell className="text-sm text-gray-600">
                  {formatRelativeTime(source.last_fetched_at)}
                </DataTableCell>
                <DataTableCell>
                  <SourceActionsMenu
                    source={source}
                    onEdit={onEdit}
                    onDelete={onDelete}
                  />
                </DataTableCell>
              </DataTableRow>
            );
          })}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
