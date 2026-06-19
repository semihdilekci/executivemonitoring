"use client";

import { useMemo, useState } from "react";
import { AuditLogTable } from "@/components/admin/audit-log-table";
import { RoleGate } from "@/components/auth/role-gate";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { AuditLogTableSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  flattenAuditLogPages,
  useAuditLogs,
} from "@/hooks/use-audit-logs";
import { flattenUserPages, useUsers } from "@/hooks/use-users";
import {
  AUDIT_EVENT_FILTER_OPTIONS,
  AUDIT_TARGET_TYPE_OPTIONS,
} from "@/lib/audit-labels";

export default function AdminAuditLogsPage() {
  const [eventType, setEventType] = useState("");
  const [actorUserId, setActorUserId] = useState("");
  const [targetType, setTargetType] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const usersQuery = useUsers({ limit: 100 });
  const auditQuery = useAuditLogs({
    event_type: eventType || undefined,
    actor_user_id: actorUserId || undefined,
    target_type: targetType || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit: 50,
  });

  const users = useMemo(
    () => flattenUserPages(usersQuery.data),
    [usersQuery.data],
  );

  const logs = useMemo(
    () => flattenAuditLogPages(auditQuery.data),
    [auditQuery.data],
  );

  const isEmpty =
    !auditQuery.isLoading && !auditQuery.isError && logs.length === 0;

  const hasNoFilters =
    !eventType && !actorUserId && !targetType && !startDate && !endDate;

  return (
    <RoleGate>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">Denetim Logu</h1>
          <p className="mt-1 text-sm text-gray-500">
            Sistem olaylarını kronolojik olarak görüntüleyin ve filtreleyin.
          </p>
          <p className="mt-2 text-xs text-gray-400">
            Arşiv verisi (90 günden eski) S3&apos;te saklanmaktadır.
          </p>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="space-y-1.5">
            <label
              htmlFor="audit-event-filter"
              className="block text-sm font-medium text-gray-700"
            >
              Olay tipi
            </label>
            <select
              id="audit-event-filter"
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              className="flex h-10 w-full min-w-[180px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {AUDIT_EVENT_FILTER_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="audit-actor-filter"
              className="block text-sm font-medium text-gray-700"
            >
              Kullanıcı
            </label>
            <select
              id="audit-actor-filter"
              value={actorUserId}
              onChange={(event) => setActorUserId(event.target.value)}
              className="flex h-10 w-full min-w-[180px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="">Tüm kullanıcılar</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="audit-target-filter"
              className="block text-sm font-medium text-gray-700"
            >
              Hedef tipi
            </label>
            <select
              id="audit-target-filter"
              value={targetType}
              onChange={(event) => setTargetType(event.target.value)}
              className="flex h-10 w-full min-w-[160px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {AUDIT_TARGET_TYPE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="w-full sm:max-w-[160px]">
            <Input
              label="Başlangıç"
              name="start_date"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </div>

          <div className="w-full sm:max-w-[160px]">
            <Input
              label="Bitiş"
              name="end_date"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </div>
        </div>

        {auditQuery.isLoading ? <AuditLogTableSkeleton /> : null}

        {auditQuery.isError ? (
          <ErrorView onRetry={() => void auditQuery.refetch()} />
        ) : null}

        {!auditQuery.isLoading && !auditQuery.isError && isEmpty ? (
          <EmptyState
            title="Henüz denetim kaydı yok"
            description={
              hasNoFilters
                ? "Sistem olayları otomatik olarak burada loglanacak."
                : "Filtrelere uygun denetim kaydı bulunamadı."
            }
          />
        ) : null}

        {!auditQuery.isLoading && !auditQuery.isError && logs.length > 0 ? (
          <>
            <AuditLogTable logs={logs} />

            {auditQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void auditQuery.fetchNextPage()}
                  disabled={auditQuery.isFetchingNextPage}
                >
                  {auditQuery.isFetchingNextPage
                    ? "Yükleniyor…"
                    : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </RoleGate>
  );
}
