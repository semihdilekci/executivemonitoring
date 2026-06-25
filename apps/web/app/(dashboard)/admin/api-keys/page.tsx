"use client";

import { useCallback, useMemo, useState } from "react";
import { ApiKeyCard } from "@/components/admin/api-key-card";
import { ApiKeyFormModal } from "@/components/admin/api-key-form-modal";
import { TranslationSettingsForm } from "@/components/admin/translation-settings-form";
import { UsageChart } from "@/components/admin/usage-chart";
import { RoleGate } from "@/components/auth/role-gate";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { ApiKeysSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import {
  useApiKeyUsageStats,
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  usePatchApiKeyStatus,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { API_PROVIDER_LABELS } from "@/lib/api-labels";
import type { ApiKeyItem, ApiProvider, LlmRequestType } from "@/types/api";
import { isApiError } from "@/types/api";

type RangeOption = "7" | "30" | "90";

interface ToastState {
  message: string;
  variant: "success" | "error";
}

function getDateRange(days: number): { start_date: string; end_date: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - days);

  const toIsoDate = (date: Date) => date.toISOString().slice(0, 10);

  return {
    start_date: toIsoDate(start),
    end_date: toIsoDate(end),
  };
}

export default function AdminApiKeysPage() {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ApiKeyItem | null>(null);
  const [togglingKeyId, setTogglingKeyId] = useState<string | null>(null);
  const [updatingScopeKeyId, setUpdatingScopeKeyId] = useState<string | null>(null);
  const [range, setRange] = useState<RangeOption>("30");
  const [providerFilter, setProviderFilter] = useState<ApiProvider | "all">("all");
  const [toast, setToast] = useState<ToastState | null>(null);

  const apiKeysQuery = useApiKeys();
  const createApiKey = useCreateApiKey();
  const patchApiKeyStatus = usePatchApiKeyStatus();
  const updateApiKey = useUpdateApiKey();
  const deleteApiKey = useDeleteApiKey();

  const dateRange = useMemo(() => getDateRange(Number.parseInt(range, 10)), [range]);

  const usageQuery = useApiKeyUsageStats({
    period: "daily",
    provider: providerFilter === "all" ? undefined : providerFilter,
    ...dateRange,
  });

  const sortedKeys = useMemo(() => {
    const keys = apiKeysQuery.data ?? [];
    return [...keys].sort((a, b) => a.priority_order - b.priority_order);
  }, [apiKeysQuery.data]);

  const activeProviderChain = useMemo(() => {
    return sortedKeys
      .filter((item) => item.is_active)
      .map((item) => `${API_PROVIDER_LABELS[item.provider]} (${item.key_alias})`)
      .join(" → ");
  }, [sortedKeys]);

  const showToast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      setToast({ message, variant });
    },
    [],
  );

  const handleCreate = async (
    values: Parameters<typeof createApiKey.mutateAsync>[0],
  ) => {
    await createApiKey.mutateAsync(values);
    setIsFormOpen(false);
    showToast("API anahtarı eklendi.");
  };

  const handleToggleStatus = async (apiKey: ApiKeyItem) => {
    setTogglingKeyId(apiKey.id);
    try {
      await patchApiKeyStatus.mutateAsync({
        keyId: apiKey.id,
        body: { is_active: !apiKey.is_active },
      });
      showToast(
        apiKey.is_active ? "API anahtarı pasif yapıldı." : "API anahtarı aktif edildi.",
      );
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Durum güncellenirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setTogglingKeyId(null);
    }
  };

  const handleUpdateScope = async (keyId: string, scope: LlmRequestType[]) => {
    setUpdatingScopeKeyId(keyId);
    try {
      await updateApiKey.mutateAsync({ keyId, body: { request_type_scope: scope } });
      showToast("Operasyon kapsamı güncellendi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Kapsam güncellenirken bir hata oluştu.";
      showToast(message, "error");
      throw error;
    } finally {
      setUpdatingScopeKeyId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      const response = await deleteApiKey.mutateAsync(deleteTarget.id);
      showToast(response.message);
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "API anahtarı silinirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  const allInactive =
    sortedKeys.length > 0 && sortedKeys.every((item) => !item.is_active);

  return (
    <RoleGate>
      <div className="space-y-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">API Key Yönetimi</h1>
            <p className="mt-1 text-sm text-gray-500">
              LLM API anahtarlarını yönetin ve token kullanımını izleyin.
            </p>
          </div>
          <Button type="button" onClick={() => setIsFormOpen(true)}>
            API Key Ekle
          </Button>
        </div>

        {allInactive ? (
          <div
            className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            role="alert"
          >
            Tüm LLM provider&apos;lar pasif — digest üretimi ve chatbot çalışmayabilir.
          </div>
        ) : null}

        {activeProviderChain ? (
          <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700">
            <span className="font-medium text-navy-800">Aktif provider sırası: </span>
            {activeProviderChain}
          </div>
        ) : null}

        {apiKeysQuery.isLoading ? <ApiKeysSkeleton /> : null}

        {apiKeysQuery.isError ? (
          <ErrorView onRetry={() => void apiKeysQuery.refetch()} />
        ) : null}

        {!apiKeysQuery.isLoading &&
        !apiKeysQuery.isError &&
        sortedKeys.length === 0 ? (
          <EmptyState
            title="Henüz API key eklenmemiş"
            description="AI servislerinin çalışması için en az bir API key gerekli."
            action={
              <Button type="button" onClick={() => setIsFormOpen(true)}>
                API Key Ekle
              </Button>
            }
          />
        ) : null}

        {!apiKeysQuery.isLoading &&
        !apiKeysQuery.isError &&
        sortedKeys.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2">
            {sortedKeys.map((apiKey) => (
              <ApiKeyCard
                key={apiKey.id}
                apiKey={apiKey}
                isToggling={togglingKeyId === apiKey.id}
                isUpdatingScope={updatingScopeKeyId === apiKey.id}
                onToggleStatus={(item) => void handleToggleStatus(item)}
                onUpdateScope={handleUpdateScope}
                onDelete={setDeleteTarget}
              />
            ))}
          </div>
        ) : null}

        <section className="space-y-4 border-t border-gray-200 pt-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-bold text-navy-800">Token Kullanımı</h2>
              <p className="mt-1 text-sm text-gray-500">
                Günlük token tüketimi ve sağlayıcı dağılımı.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <label htmlFor="range-filter" className="block text-sm font-medium text-gray-700">
                  Zaman aralığı
                </label>
                <select
                  id="range-filter"
                  value={range}
                  onChange={(event) => setRange(event.target.value as RangeOption)}
                  className="flex h-10 min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
                >
                  <option value="7">Son 7 gün</option>
                  <option value="30">Son 30 gün</option>
                  <option value="90">Son 90 gün</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="provider-filter"
                  className="block text-sm font-medium text-gray-700"
                >
                  Sağlayıcı
                </label>
                <select
                  id="provider-filter"
                  value={providerFilter}
                  onChange={(event) =>
                    setProviderFilter(event.target.value as ApiProvider | "all")
                  }
                  className="flex h-10 min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
                >
                  <option value="all">Tümü</option>
                  <option value="groq">Groq</option>
                  <option value="gemini">Gemini</option>
                  <option value="anthropic">Claude</option>
                </select>
              </div>
            </div>
          </div>

          {usageQuery.isError ? (
            <ErrorView onRetry={() => void usageQuery.refetch()} />
          ) : (
            <UsageChart data={usageQuery.data} isLoading={usageQuery.isLoading} />
          )}
        </section>

        <TranslationSettingsForm />
      </div>

      <ApiKeyFormModal
        isOpen={isFormOpen}
        existingKeys={sortedKeys}
        isSubmitting={createApiKey.isPending}
        onClose={() => setIsFormOpen(false)}
        onCreate={handleCreate}
      />

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="API anahtarını sil"
        message={
          deleteTarget
            ? `'${deleteTarget.key_alias}' anahtarı kalıcı olarak silinecek. Devam etmek istiyor musunuz?`
            : ""
        }
        confirmLabel="Sil"
        isLoading={deleteApiKey.isPending}
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
