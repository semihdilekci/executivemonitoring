"use client";

import { useCallback, useMemo, useState } from "react";
import { NewsletterEditor } from "@/components/admin/newsletter-editor";
import { RoleGate } from "@/components/auth/role-gate";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { PromptTableSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import {
  useCreateNewsletterTemplate,
  useDeleteNewsletterTemplate,
  useNewsletterTemplates,
  useUpdateNewsletterTemplate,
} from "@/hooks/use-newsletter-templates";
import { formatRelativeTime } from "@/lib/date-format";
import type {
  CreateNewsletterTemplateRequest,
  NewsletterTemplate,
  UpdateNewsletterTemplateRequest,
} from "@/types/api";
import { isApiError } from "@/types/api";

type ActiveFilter = "all" | "active" | "inactive";
type View =
  | { mode: "list" }
  | { mode: "create" }
  | { mode: "edit"; template: NewsletterTemplate };

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminNewsletterTemplatesPage() {
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [view, setView] = useState<View>({ mode: "list" });
  const [toast, setToast] = useState<ToastState | null>(null);
  const [pendingDelete, setPendingDelete] = useState<NewsletterTemplate | null>(
    null,
  );

  const templatesQuery = useNewsletterTemplates({
    is_active: activeFilter === "all" ? undefined : activeFilter === "active",
  });

  const createTemplate = useCreateNewsletterTemplate();
  const updateTemplate = useUpdateNewsletterTemplate();
  const deleteTemplate = useDeleteNewsletterTemplate();

  const templates = useMemo(
    () => templatesQuery.data ?? [],
    [templatesQuery.data],
  );

  const showToast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      setToast({ message, variant });
    },
    [],
  );

  const handleCreate = async (body: CreateNewsletterTemplateRequest) => {
    try {
      await createTemplate.mutateAsync(body);
      setView({ mode: "list" });
      showToast("Bülten oluşturuldu.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Bülten oluşturulurken bir hata oluştu.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleUpdate = async (body: UpdateNewsletterTemplateRequest) => {
    if (view.mode !== "edit") return;

    try {
      await updateTemplate.mutateAsync({ templateId: view.template.id, body });
      setView({ mode: "list" });
      showToast("Bülten kaydedildi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Bülten kaydedilirken bir hata oluştu.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;

    try {
      await deleteTemplate.mutateAsync(pendingDelete.id);
      setPendingDelete(null);
      showToast("Bülten silindi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Bülten silinirken bir hata oluştu.";
      showToast(message, "error");
    }
  };

  if (view.mode !== "list") {
    return (
      <RoleGate>
        <NewsletterEditor
          mode={view.mode}
          template={view.mode === "edit" ? view.template : undefined}
          isSubmitting={createTemplate.isPending || updateTemplate.isPending}
          onCancel={() => setView({ mode: "list" })}
          onCreate={handleCreate}
          onUpdate={handleUpdate}
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

  const hasNoFilters = activeFilter === "all";

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">
              Bülten Şablonları
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Serbest bülten konfigürasyonu ve sınırsız bölüm prompt&apos;larını
              tek ekrandan yönetin.
            </p>
          </div>
          <Button type="button" onClick={() => setView({ mode: "create" })}>
            Yeni Bülten
          </Button>
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="space-y-1.5">
            <label
              htmlFor="active-filter"
              className="block text-sm font-medium text-gray-700"
            >
              Durum
            </label>
            <select
              id="active-filter"
              value={activeFilter}
              onChange={(event) =>
                setActiveFilter(event.target.value as ActiveFilter)
              }
              className="flex h-10 min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="all">Tümü</option>
              <option value="active">Aktif</option>
              <option value="inactive">Pasif</option>
            </select>
          </div>
        </div>

        {templatesQuery.isLoading ? <PromptTableSkeleton /> : null}

        {templatesQuery.isError ? (
          <ErrorView onRetry={() => void templatesQuery.refetch()} />
        ) : null}

        {!templatesQuery.isLoading &&
        !templatesQuery.isError &&
        templates.length === 0 ? (
          <EmptyState
            title="Henüz bülten şablonu yok"
            description={
              hasNoFilters
                ? "AI'ın bülten üretebilmesi için en az bir bülten şablonu gerekli."
                : "Filtrelere uygun bülten bulunamadı."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={() => setView({ mode: "create" })}>
                  Yeni Bülten
                </Button>
              ) : undefined
            }
          />
        ) : null}

        {!templatesQuery.isLoading &&
        !templatesQuery.isError &&
        templates.length > 0 ? (
          <DataTable>
            <table className="min-w-full">
              <DataTableHeader>
                <DataTableHead>Bülten adı</DataTableHead>
                <DataTableHead>Slug</DataTableHead>
                <DataTableHead>Bölüm</DataTableHead>
                <DataTableHead>Min skor</DataTableHead>
                <DataTableHead>Durum</DataTableHead>
                <DataTableHead>Son güncelleme</DataTableHead>
                <DataTableHead className="text-right">İşlem</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {templates.map((template) => (
                  <DataTableRow key={template.id}>
                    <DataTableCell>
                      <button
                        type="button"
                        className="text-left font-semibold text-navy-800 hover:underline"
                        onClick={() => setView({ mode: "edit", template })}
                      >
                        {template.name}
                      </button>
                    </DataTableCell>
                    <DataTableCell className="font-mono text-xs text-gray-500">
                      {template.slug}
                    </DataTableCell>
                    <DataTableCell>{template.sections.length}</DataTableCell>
                    <DataTableCell>{template.min_content_score}</DataTableCell>
                    <DataTableCell>
                      <span
                        className={
                          template.is_active
                            ? "inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                            : "inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600"
                        }
                      >
                        {template.is_active ? "Aktif" : "Pasif"}
                      </span>
                    </DataTableCell>
                    <DataTableCell className="text-gray-500">
                      {formatRelativeTime(template.updated_at)}
                    </DataTableCell>
                    <DataTableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setView({ mode: "edit", template })}
                      >
                        Düzenle
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-red-500 hover:bg-red-50"
                        onClick={() => setPendingDelete(template)}
                      >
                        Sil
                      </Button>
                    </DataTableCell>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </table>
          </DataTable>
        ) : null}
      </div>

      <ConfirmDialog
        isOpen={pendingDelete !== null}
        title="Bülteni sil"
        message={`"${pendingDelete?.name ?? ""}" bülteni ve tüm bölümleri silinecek. Bu işlem geri alınamaz.`}
        confirmLabel="Sil"
        variant="danger"
        isLoading={deleteTemplate.isPending}
        onConfirm={() => void handleDelete()}
        onCancel={() => setPendingDelete(null)}
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
