"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatDetailModal } from "@/components/admin/chat-detail-modal";
import { ChatHistoryTable } from "@/components/admin/chat-history-table";
import { RoleGate } from "@/components/auth/role-gate";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { ChatHistoryTableSkeleton } from "@/components/common/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  flattenChatHistoryPages,
  useChatHistory,
} from "@/hooks/use-chat-history";
import { flattenUserPages, useUsers } from "@/hooks/use-users";
import type { ChatHistoryItem } from "@/types/api";

export default function AdminChatHistoryPage() {
  const [userId, setUserId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [detailItem, setDetailItem] = useState<ChatHistoryItem | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim().toLowerCase());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const usersQuery = useUsers({ limit: 50 });
  const historyQuery = useChatHistory({
    user_id: userId || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    limit: 20,
  });

  const users = useMemo(
    () => flattenUserPages(usersQuery.data),
    [usersQuery.data],
  );

  const allItems = useMemo(
    () => flattenChatHistoryPages(historyQuery.data),
    [historyQuery.data],
  );

  const filteredItems = useMemo(() => {
    if (!debouncedSearch) return allItems;
    return allItems.filter((item) =>
      item.question.toLowerCase().includes(debouncedSearch),
    );
  }, [allItems, debouncedSearch]);

  const isEmpty =
    !historyQuery.isLoading &&
    !historyQuery.isError &&
    filteredItems.length === 0;

  const hasNoFilters =
    !userId && !startDate && !endDate && debouncedSearch === "";

  return (
    <RoleGate>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-800">Sohbet Geçmişi</h1>
          <p className="mt-1 text-sm text-gray-500">
            Kullanıcıların chatbot sorularını ve yanıtlarını inceleyin.
          </p>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="space-y-1.5">
            <label
              htmlFor="chat-user-filter"
              className="block text-sm font-medium text-gray-700"
            >
              Kullanıcı
            </label>
            <select
              id="chat-user-filter"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
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

          <div className="w-full sm:max-w-[160px]">
            <Input
              label="Başlangıç"
              name="chat_start_date"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </div>

          <div className="w-full sm:max-w-[160px]">
            <Input
              label="Bitiş"
              name="chat_end_date"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </div>

          <div className="w-full sm:max-w-xs">
            <Input
              label="Ara"
              name="chat_search"
              type="search"
              placeholder="Soru metninde ara"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>
        </div>

        {historyQuery.isLoading ? <ChatHistoryTableSkeleton /> : null}

        {historyQuery.isError ? (
          <ErrorView onRetry={() => void historyQuery.refetch()} />
        ) : null}

        {!historyQuery.isLoading && !historyQuery.isError && isEmpty ? (
          <EmptyState
            title="Henüz sohbet geçmişi yok"
            description={
              hasNoFilters
                ? "Kullanıcılar chatbot'u kullandıkça sohbet geçmişi burada görünecek."
                : "Filtrelere uygun sohbet kaydı bulunamadı."
            }
          />
        ) : null}

        {!historyQuery.isLoading &&
        !historyQuery.isError &&
        filteredItems.length > 0 ? (
          <>
            <ChatHistoryTable
              items={filteredItems}
              onViewDetail={setDetailItem}
            />

            {historyQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void historyQuery.fetchNextPage()}
                  disabled={historyQuery.isFetchingNextPage}
                >
                  {historyQuery.isFetchingNextPage
                    ? "Yükleniyor…"
                    : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <ChatDetailModal
        item={detailItem}
        isOpen={detailItem !== null}
        onClose={() => setDetailItem(null)}
      />
    </RoleGate>
  );
}
