"use client";

import { useCallback, useMemo, useState } from "react";
import { PromptEditor } from "@/components/admin/prompt-editor";
import { RoleGate } from "@/components/auth/role-gate";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { PromptTableSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { DigestTypeBadge } from "@/components/digest/digest-type-badge";
import {
  useCreatePromptTemplate,
  usePromptTemplates,
  useUpdatePromptTemplate,
} from "@/hooks/use-prompts";
import { DIGEST_TYPE_FILTERS } from "@/lib/digest-labels";
import { formatRelativeTime } from "@/lib/date-format";
import type { DigestType, PromptTemplateItem } from "@/types/api";
import { isApiError } from "@/types/api";

type DigestFilter = DigestType | "all";
type ActiveFilter = "all" | "active" | "inactive";

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminPromptTemplatesPage() {
  const [digestFilter, setDigestFilter] = useState<DigestFilter>("all");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<PromptTemplateItem | null>(
    null,
  );
  const [toast, setToast] = useState<ToastState | null>(null);

  const templatesQuery = usePromptTemplates({
    digest_type: digestFilter === "all" ? undefined : digestFilter,
    is_active:
      activeFilter === "all"
        ? undefined
        : activeFilter === "active",
  });

  const createTemplate = useCreatePromptTemplate();
  const updateTemplate = useUpdatePromptTemplate();

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

  const openCreate = () => {
    setEditingTemplate(null);
    setFormMode("create");
  };

  const openEdit = (template: PromptTemplateItem) => {
    setEditingTemplate(template);
    setFormMode("edit");
  };

  const closeForm = () => {
    setFormMode(null);
    setEditingTemplate(null);
  };

  const handleCreate = async (
    values: Parameters<typeof createTemplate.mutateAsync>[0],
  ) => {
    try {
      await createTemplate.mutateAsync(values);
      closeForm();
      showToast("Prompt şablonu oluşturuldu.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Şablon oluşturulurken bir hata oluştu.";
      showToast(message, "error");
      throw error;
    }
  };

  const handleUpdate = async (
    values: Parameters<typeof updateTemplate.mutateAsync>[0]["body"],
  ) => {
    if (!editingTemplate) return;

    try {
      await updateTemplate.mutateAsync({
        templateId: editingTemplate.id,
        body: values,
      });
      closeForm();
      showToast("Prompt şablonu kaydedildi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Şablon kaydedilirken bir hata oluştu.";
      showToast(message, "error");
      throw error;
    }
  };

  const hasNoFilters = digestFilter === "all" && activeFilter === "all";

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">
              Prompt Şablon Yönetimi
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              AI bülten ve sohbet üretiminde kullanılan prompt şablonlarını yönetin.
            </p>
          </div>
          <Button type="button" onClick={openCreate}>
            Yeni Şablon
          </Button>
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="space-y-1.5">
            <label htmlFor="digest-filter" className="block text-sm font-medium text-gray-700">
              Bülten tipi
            </label>
            <select
              id="digest-filter"
              value={digestFilter}
              onChange={(event) =>
                setDigestFilter(event.target.value as DigestFilter)
              }
              className="flex h-10 min-w-[160px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              {DIGEST_TYPE_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="active-filter" className="block text-sm font-medium text-gray-700">
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
            title="Henüz prompt şablonu yok"
            description={
              hasNoFilters
                ? "AI'ın bülten üretebilmesi için prompt şablonları gerekli."
                : "Filtrelere uygun şablon bulunamadı."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={openCreate}>
                  Şablon Oluştur
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
                <DataTableHead>Şablon adı</DataTableHead>
                <DataTableHead>Bülten tipi</DataTableHead>
                <DataTableHead>Bölüm</DataTableHead>
                <DataTableHead>Durum</DataTableHead>
                <DataTableHead>Versiyon</DataTableHead>
                <DataTableHead>Son güncelleme</DataTableHead>
                <DataTableHead className="text-right">İşlem</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {templates.map((template) => (
                  <DataTableRow key={template.id}>
                    <DataTableCell>
                      <p className="font-semibold text-navy-800">{template.name}</p>
                      <p className="text-xs text-gray-500">{template.section_key}</p>
                    </DataTableCell>
                    <DataTableCell>
                      <DigestTypeBadge digestType={template.digest_type} />
                    </DataTableCell>
                    <DataTableCell className="font-mono text-xs">
                      {template.section_key}
                    </DataTableCell>
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
                    <DataTableCell>v{template.version}</DataTableCell>
                    <DataTableCell className="text-gray-500">
                      {formatRelativeTime(template.updated_at)}
                    </DataTableCell>
                    <DataTableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(template)}
                      >
                        Düzenle
                      </Button>
                    </DataTableCell>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </table>
          </DataTable>
        ) : null}
      </div>

      <PromptEditor
        mode={formMode === "edit" ? "edit" : "create"}
        template={editingTemplate ?? undefined}
        isOpen={formMode !== null}
        isSubmitting={createTemplate.isPending || updateTemplate.isPending}
        onClose={closeForm}
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
