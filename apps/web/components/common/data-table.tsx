import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface DataTableProps {
  children: ReactNode;
  className?: string;
}

export function DataTable({ children, className }: DataTableProps) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm",
        className,
      )}
    >
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

interface DataTableHeaderProps {
  children: ReactNode;
}

export function DataTableHeader({ children }: DataTableHeaderProps) {
  return (
    <thead className="border-b border-gray-100 bg-gray-50/80">
      <tr>{children}</tr>
    </thead>
  );
}

interface DataTableHeadProps {
  children: ReactNode;
  className?: string;
}

export function DataTableHead({ children, className }: DataTableHeadProps) {
  return (
    <th
      scope="col"
      className={cn(
        "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500",
        className,
      )}
    >
      {children}
    </th>
  );
}

interface DataTableBodyProps {
  children: ReactNode;
}

export function DataTableBody({ children }: DataTableBodyProps) {
  return <tbody className="divide-y divide-gray-100">{children}</tbody>;
}

interface DataTableRowProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export function DataTableRow({ children, className, onClick }: DataTableRowProps) {
  return (
    <tr className={cn("hover:bg-gray-50/60", className)} onClick={onClick}>
      {children}
    </tr>
  );
}

interface DataTableCellProps {
  children: ReactNode;
  className?: string;
}

export function DataTableCell({ children, className }: DataTableCellProps) {
  return (
    <td className={cn("px-4 py-3 text-sm text-gray-700", className)}>
      {children}
    </td>
  );
}
