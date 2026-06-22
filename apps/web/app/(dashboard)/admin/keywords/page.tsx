"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  EMPTY_KEYWORD_FILTERS,
  KeywordFilters,
  type KeywordFilterState,
} from "@/components/admin/keyword-filters";
import { KeywordFormModal } from "@/components/admin/keyword-form-modal";
import { KeywordTable } from "@/components/admin/keyword-table";
import { RoleGate } from "@/components/auth/role-gate";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { UserTableSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import {
  useCreateKeyword,
  useDeleteKeyword,
  useKeywords,
  useUpdateKeyword,
} from "@/hooks/use-keywords";
import type { KeywordCategory, KeywordResponse } from "@/types/api";
import { isApiError } from "@/types/api";

const PAGE_SIZE = 50;

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminKeywordsPage() {
  const [filters, setFilters] = useState<KeywordFilterState>(
    EMPTY_KEYWORD_FILTERS,
  );
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingKeyword, setEditingKeyword] = useState<KeywordResponse | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = useState<KeywordResponse | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(filters.q.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [filters.q]);

  // Filtre değişince ilk sayfaya dön.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filters.category, filters.isActive]);

  const apiFilters = useMemo(
    () => ({
      category: (filters.category || undefined) as KeywordCategory | undefined,
      // Backend `q` min 2 karakter ister — kısa girişte gönderme (422 önle).
      q: debouncedSearch.length >= 2 ? debouncedSearch : undefined,
      is_active:
        filters.isActive === "" ? undefined : filters.isActive === "true",
      page,
      page_size: PAGE_SIZE,
    }),
    [filters.category, filters.isActive, debouncedSearch, page],
  );

  const keywordsQuery = useKeywords(apiFilters);
  const createKeyword = useCreateKeyword();
  const updateKeyword = useUpdateKeyword();
  const deleteKeyword = useDeleteKeyword();

  const keywords = keywordsQuery.data?.data ?? [];
  const total = keywordsQuery.data?.pagination.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const showToast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      setToast({ message, variant });
    },
    [],
  );

  const openCreateModal = () => {
    setEditingKeyword(null);
    setFormMode("create");
  };

  const openEditModal = (keyword: KeywordResponse) => {
    setEditingKeyword(keyword);
    setFormMode("edit");
  };

  const closeFormModal = () => {
    setFormMode(null);
    setEditingKeyword(null);
  };

  const handleCreate = async (
    values: Parameters<typeof createKeyword.mutateAsync>[0],
  ) => {
    await createKeyword.mutateAsync(values);
    closeFormModal();
    showToast("Keyword eklendi.");
  };

  const handleUpdate = async (
    values: Parameters<typeof updateKeyword.mutateAsync>[0]["body"],
  ) => {
    if (!editingKeyword) return;
    await updateKeyword.mutateAsync({ keywordId: editingKeyword.id, body: values });
    closeFormModal();
    showToast("Keyword güncellendi.");
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteKeyword.mutateAsync(deleteTarget.id);
      showToast("Keyword silindi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Keyword silinirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  const hasNoFilters =
    filters.category === "" &&
    filters.isActive === "" &&
    debouncedSearch === "";

  const isEmpty =
    !keywordsQuery.isLoading && !keywordsQuery.isError && keywords.length === 0;

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">Keyword Takibi</h1>
            <p className="mt-1 text-sm text-gray-500">
              Processor havuzundaki keyword&apos;leri ve kategori rating&apos;lerini
              yönetin.
            </p>
          </div>
          <Button type="button" onClick={openCreateModal}>
            Keyword Ekle
          </Button>
        </div>

        <KeywordFilters value={filters} onChange={setFilters} />

        {keywordsQuery.isLoading ? <UserTableSkeleton /> : null}

        {keywordsQuery.isError ? (
          <ErrorView onRetry={() => void keywordsQuery.refetch()} />
        ) : null}

        {isEmpty ? (
          <EmptyState
            title={
              hasNoFilters
                ? "Henüz keyword eklenmemiş"
                : "Filtrelere uygun keyword bulunamadı"
            }
            description={
              hasNoFilters
                ? "Processor kategori seçimi ve relevance skoru için ilk keyword'ünüzü ekleyin."
                : "Farklı filtre kombinasyonu deneyin veya filtreleri temizleyin."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={openCreateModal}>
                  Keyword Ekle
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setFilters(EMPTY_KEYWORD_FILTERS)}
                >
                  Filtreleri temizle
                </Button>
              )
            }
          />
        ) : null}

        {!keywordsQuery.isLoading &&
        !keywordsQuery.isError &&
        keywords.length > 0 ? (
          <>
            <KeywordTable
              keywords={keywords}
              onEdit={openEditModal}
              onDelete={setDeleteTarget}
            />

            <div className="flex items-center justify-between text-sm text-gray-600">
              <span>
                Toplam {total} keyword · Sayfa {page}/{totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={page <= 1 || keywordsQuery.isFetching}
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                >
                  Önceki
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={page >= totalPages || keywordsQuery.isFetching}
                  onClick={() =>
                    setPage((prev) => Math.min(totalPages, prev + 1))
                  }
                >
                  Sonraki
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </div>

      <KeywordFormModal
        mode={formMode === "edit" ? "edit" : "create"}
        keyword={editingKeyword ?? undefined}
        isOpen={formMode !== null}
        isSubmitting={createKeyword.isPending || updateKeyword.isPending}
        onClose={closeFormModal}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
      />

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Keyword'ü sil"
        message={
          deleteTarget
            ? `'${deleteTarget.term_tr}' keyword'ü ve tüm kategori rating'leri silinecek. Bu işlem geri alınamaz. Devam etmek istiyor musunuz?`
            : ""
        }
        confirmLabel="Sil"
        isLoading={deleteKeyword.isPending}
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteTarget(null)}
      />

      {toast ? (
        <Toast
          message={toast.message}
          variant={toast.variant}
          onDismiss={() => setToast(null)}
        />
      ) : null}
    </RoleGate>
  );
}
