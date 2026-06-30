"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RoleGate } from "@/components/auth/role-gate";
import { SourceFormModal } from "@/components/admin/source-form-modal";
import { SourceTable } from "@/components/admin/source-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { SourceTableSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  flattenSourcePages,
  useCreateSource,
  useDeleteSource,
  usePatchSourceStatus,
  useSources,
  useUpdateSource,
} from "@/hooks/use-sources";
import { MVP_SOURCE_TYPES, SOURCE_TYPE_LABELS } from "@/lib/source-labels";
import type { SourceListItem, SourceStatus, SourceType } from "@/types/api";
import { isApiError } from "@/types/api";

type TypeFilter = "all" | SourceType;
type StatusFilter = "all" | SourceStatus;

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminSourcesPage() {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingSource, setEditingSource] = useState<SourceListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SourceListItem | null>(null);
  const [togglingSourceId, setTogglingSourceId] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const sourcesQuery = useSources({
    source_type: typeFilter === "all" ? undefined : typeFilter,
    status: statusFilter === "all" ? undefined : statusFilter,
    q: debouncedSearch || undefined,
    limit: 20,
  });

  const createSource = useCreateSource();
  const updateSource = useUpdateSource();
  const patchSourceStatus = usePatchSourceStatus();
  const deleteSource = useDeleteSource();

  const allSources = useMemo(
    () => flattenSourcePages(sourcesQuery.data),
    [sourcesQuery.data],
  );

  const showToast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      setToast({ message, variant });
    },
    [],
  );

  const openCreateModal = () => {
    setEditingSource(null);
    setFormMode("create");
  };

  const openEditModal = (source: SourceListItem) => {
    setEditingSource(source);
    setFormMode("edit");
  };

  const closeFormModal = () => {
    setFormMode(null);
    setEditingSource(null);
  };

  const handleCreate = async (values: Parameters<typeof createSource.mutateAsync>[0]) => {
    await createSource.mutateAsync(values);
    setFormMode(null);
    showToast("Kaynak eklendi.");
  };

  const handleUpdate = async (
    values: Parameters<typeof updateSource.mutateAsync>[0]["body"],
  ) => {
    if (!editingSource) return;
    await updateSource.mutateAsync({
      sourceId: editingSource.id,
      body: values,
    });
    setFormMode(null);
    setEditingSource(null);
    showToast("Kaynak güncellendi.");
  };

  const handleToggleStatus = async (source: SourceListItem) => {
    const nextStatus: SourceStatus =
      source.status === "active" ? "inactive" : "active";

    setTogglingSourceId(source.id);
    try {
      await patchSourceStatus.mutateAsync({
        sourceId: source.id,
        body: { status: nextStatus },
      });
      showToast(
        nextStatus === "active" ? "Kaynak aktif edildi." : "Kaynak pasif yapıldı.",
      );
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Durum güncellenirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setTogglingSourceId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      const response = await deleteSource.mutateAsync(deleteTarget.id);
      showToast(response.message);
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Kaynak silinirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  const isEmpty =
    !sourcesQuery.isLoading &&
    !sourcesQuery.isError &&
    allSources.length === 0;

  const hasNoFilters =
    typeFilter === "all" &&
    statusFilter === "all" &&
    debouncedSearch === "";

  const sourceCountLabel = useMemo(() => {
    const count = allSources.length;
    if (count === 0) return null;
    if (sourcesQuery.hasNextPage) {
      return debouncedSearch
        ? `${count}+ eşleşen kaynak`
        : `${count} kaynak gösteriliyor`;
    }
    return debouncedSearch
      ? `${count} eşleşen kaynak`
      : `Toplam ${count} kaynak`;
  }, [allSources.length, debouncedSearch, sourcesQuery.hasNextPage]);

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">Kaynak Yönetimi</h1>
            <p className="mt-1 text-sm text-gray-500">
              Veri kaynaklarını ekleyin, düzenleyin ve izleyin.
            </p>
          </div>
          <Button type="button" onClick={openCreateModal}>
            Kaynak Ekle
          </Button>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="w-full sm:max-w-xs">
            <Input
              label="Ara"
              name="search"
              type="search"
              placeholder="Kaynak adında ara…"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="type-filter" className="block text-sm font-medium text-gray-700">
              Tip
            </label>
            <select
              id="type-filter"
              value={typeFilter}
              onChange={(event) =>
                setTypeFilter(event.target.value as TypeFilter)
              }
              className="flex h-10 w-full min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="all">Tümü</option>
              {MVP_SOURCE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {SOURCE_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700">
              Durum
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as StatusFilter)
              }
              className="flex h-10 w-full min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="all">Tümü</option>
              <option value="active">Aktif</option>
              <option value="inactive">Pasif</option>
              <option value="error">Hatalı</option>
            </select>
          </div>
        </div>

        {!sourcesQuery.isLoading && !sourcesQuery.isError && sourceCountLabel ? (
          <p className="text-sm text-gray-600" aria-live="polite">
            {sourceCountLabel}
          </p>
        ) : null}

        {sourcesQuery.isLoading ? <SourceTableSkeleton /> : null}

        {sourcesQuery.isError ? (
          <ErrorView onRetry={() => void sourcesQuery.refetch()} />
        ) : null}

        {!sourcesQuery.isLoading && !sourcesQuery.isError && isEmpty ? (
          <EmptyState
            title="Henüz kaynak eklenmemiş"
            description={
              hasNoFilters
                ? "Veri toplamaya başlamak için ilk kaynağınızı ekleyin."
                : "Filtrelere uygun kaynak bulunamadı."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={openCreateModal}>
                  Kaynak Ekle
                </Button>
              ) : undefined
            }
          />
        ) : null}

        {!sourcesQuery.isLoading && !sourcesQuery.isError && allSources.length > 0 ? (
          <>
            <SourceTable
              sources={allSources}
              onEdit={openEditModal}
              onDelete={setDeleteTarget}
              onToggleStatus={(source) => void handleToggleStatus(source)}
              togglingSourceId={togglingSourceId}
            />

            {sourcesQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void sourcesQuery.fetchNextPage()}
                  disabled={sourcesQuery.isFetchingNextPage}
                >
                  {sourcesQuery.isFetchingNextPage
                    ? "Yükleniyor…"
                    : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <SourceFormModal
        mode={formMode === "edit" ? "edit" : "create"}
        source={editingSource ?? undefined}
        isOpen={formMode !== null}
        isSubmitting={createSource.isPending || updateSource.isPending}
        onClose={closeFormModal}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
      />

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Kaynağı sil"
        message={
          deleteTarget
            ? `'${deleteTarget.name}' kaynağı ve ilişkili ham veriler silinecek. Bu işlem geri alınamaz. Devam etmek istiyor musunuz?`
            : ""
        }
        confirmLabel="Sil"
        isLoading={deleteSource.isPending}
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
