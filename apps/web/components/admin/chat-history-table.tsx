"use client";

import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { Button } from "@/components/ui/button";
import { formatNumericDateTime } from "@/lib/date-format";
import type { ChatHistoryItem } from "@/types/api";

interface ChatHistoryTableProps {
  items: ChatHistoryItem[];
  onViewDetail: (item: ChatHistoryItem) => void;
}

function UserAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";

  return (
    <span
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy-100 text-xs font-bold text-navy-700"
      aria-hidden
    >
      {initial}
    </span>
  );
}

export function ChatHistoryTable({ items, onViewDetail }: ChatHistoryTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead className="w-[160px]">Kullanıcı</DataTableHead>
          <DataTableHead>Soru</DataTableHead>
          <DataTableHead className="w-[140px]">Tarih</DataTableHead>
          <DataTableHead className="w-[90px]">Token</DataTableHead>
          <DataTableHead className="w-[80px]">İşlem</DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {items.map((item) => (
            <DataTableRow key={item.id}>
              <DataTableCell>
                <div className="flex items-center gap-2">
                  <UserAvatar name={item.user_name} />
                  <span className="font-medium text-gray-800">
                    {item.user_name}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell>
                <p className="line-clamp-2 text-gray-700">{item.question}</p>
              </DataTableCell>
              <DataTableCell className="whitespace-nowrap text-gray-600">
                {formatNumericDateTime(item.created_at)}
              </DataTableCell>
              <DataTableCell className="tabular-nums text-gray-600">
                {item.tokens_used.toLocaleString("tr-TR")}
              </DataTableCell>
              <DataTableCell>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => onViewDetail(item)}
                >
                  Detay
                </Button>
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
