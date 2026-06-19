"use client";

import { Fragment, useState } from "react";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import {
  EVENT_BADGE_CLASS,
  formatAuditTarget,
  getAuditEventMeta,
  maskAuditPayload,
} from "@/lib/audit-labels";
import { formatNumericDateTime } from "@/lib/date-format";
import { cn } from "@/lib/utils";
import type { AuditLogItem } from "@/types/api";

interface AuditLogTableProps {
  logs: AuditLogItem[];
}

function ExpandButton({
  isExpanded,
  onClick,
  label,
}: {
  isExpanded: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-navy-800"
      aria-expanded={isExpanded}
      aria-label={label}
    >
      <span
        className={cn(
          "inline-block text-xs transition-transform",
          isExpanded ? "rotate-90" : "",
        )}
        aria-hidden
      >
        ▶
      </span>
    </button>
  );
}

function PayloadPreview({ payload }: { payload: Record<string, unknown> }) {
  const masked = maskAuditPayload(payload);
  const formatted = JSON.stringify(masked, null, 2);

  return (
    <pre className="overflow-x-auto rounded-lg bg-gray-50 p-4 text-xs leading-relaxed text-gray-700">
      {formatted}
    </pre>
  );
}

export function AuditLogTable({ logs }: AuditLogTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead className="w-[140px]">Zaman</DataTableHead>
          <DataTableHead className="w-[180px]">Olay</DataTableHead>
          <DataTableHead className="w-[140px]">Kullanıcı</DataTableHead>
          <DataTableHead>Hedef</DataTableHead>
          <DataTableHead className="w-[60px]">
            <span className="sr-only">Detay</span>
          </DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {logs.map((log) => {
            const meta = getAuditEventMeta(log.event_type);
            const isExpanded = expandedId === log.id;
            const hasPayload = Object.keys(log.payload).length > 0;

            return (
              <Fragment key={log.id}>
                <DataTableRow>
                  <DataTableCell className="whitespace-nowrap text-gray-600">
                    {formatNumericDateTime(log.created_at)}
                  </DataTableCell>
                  <DataTableCell>
                    <span
                      className={cn(
                        "inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                        EVENT_BADGE_CLASS[meta.variant],
                      )}
                    >
                      {meta.label}
                    </span>
                  </DataTableCell>
                  <DataTableCell className="text-gray-800">
                    {log.actor_name ?? "Sistem"}
                  </DataTableCell>
                  <DataTableCell className="text-gray-600">
                    {formatAuditTarget(
                      log.target_type,
                      log.target_id,
                      log.payload,
                    )}
                  </DataTableCell>
                  <DataTableCell>
                    {hasPayload ? (
                      <ExpandButton
                        isExpanded={isExpanded}
                        label={
                          isExpanded
                            ? "Detayı gizle"
                            : "Detayı göster"
                        }
                        onClick={() =>
                          setExpandedId(isExpanded ? null : log.id)
                        }
                      />
                    ) : (
                      <span className="text-gray-300" aria-hidden>
                        —
                      </span>
                    )}
                  </DataTableCell>
                </DataTableRow>
                {isExpanded && hasPayload ? (
                  <tr className="bg-gray-50/80">
                    <td colSpan={5} className="px-4 pb-4 pt-0">
                      <PayloadPreview payload={log.payload} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
