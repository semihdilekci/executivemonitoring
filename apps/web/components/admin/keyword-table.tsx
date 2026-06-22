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
import {
  getKeywordCategoryLabel,
  getRatingChipClass,
} from "@/lib/keyword-labels";
import { cn } from "@/lib/utils";
import type { KeywordResponse } from "@/types/api";

interface KeywordTableProps {
  keywords: KeywordResponse[];
  onEdit: (keyword: KeywordResponse) => void;
  onDelete: (keyword: KeywordResponse) => void;
}

/** Tek kategori-rating chip'i: "Finans · 6". */
function CategoryRatingChip({
  category,
  rating,
}: {
  category: string;
  rating: number;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        getRatingChipClass(rating),
      )}
    >
      {getKeywordCategoryLabel(category)} · {rating}
    </span>
  );
}

function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
        isActive ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600",
      )}
    >
      {isActive ? "Aktif" : "Pasif"}
    </span>
  );
}

function KeywordActionsMenu({
  keyword,
  onEdit,
  onDelete,
}: {
  keyword: KeywordResponse;
  onEdit: (keyword: KeywordResponse) => void;
  onDelete: (keyword: KeywordResponse) => void;
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
        aria-label={`${keyword.term_tr} işlemleri`}
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
              onEdit(keyword);
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
              onDelete(keyword);
            }}
          >
            Sil
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function KeywordTable({ keywords, onEdit, onDelete }: KeywordTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead>Terim (TR)</DataTableHead>
          <DataTableHead>Terim (EN)</DataTableHead>
          <DataTableHead>Kategori &amp; Rating</DataTableHead>
          <DataTableHead className="w-[80px]">Durum</DataTableHead>
          <DataTableHead className="w-[80px]">
            <span className="sr-only">İşlemler</span>
          </DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {keywords.map((keyword) => (
            <DataTableRow key={keyword.id}>
              <DataTableCell>
                <span className="font-medium text-gray-900">
                  {keyword.term_tr}
                </span>
              </DataTableCell>
              <DataTableCell>
                <span className="text-sm text-gray-700">{keyword.term_en}</span>
              </DataTableCell>
              <DataTableCell>
                <div className="flex flex-wrap gap-1.5">
                  {keyword.categories.map((item) => (
                    <CategoryRatingChip
                      key={item.category}
                      category={item.category}
                      rating={item.rating}
                    />
                  ))}
                </div>
              </DataTableCell>
              <DataTableCell>
                <StatusBadge isActive={keyword.is_active} />
              </DataTableCell>
              <DataTableCell>
                <KeywordActionsMenu
                  keyword={keyword}
                  onEdit={onEdit}
                  onDelete={onDelete}
                />
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
