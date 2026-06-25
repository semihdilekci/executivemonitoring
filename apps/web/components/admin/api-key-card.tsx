"use client";

import { useEffect, useState } from "react";
import { RequestTypeScopeSelector } from "@/components/admin/request-type-scope-selector";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  API_PROVIDER_BADGE_CLASS,
  API_PROVIDER_LABELS,
  formatMaskedApiKey,
} from "@/lib/api-labels";
import { formatNumericDate } from "@/lib/date-format";
import { formatScopeSummary } from "@/lib/llm-request-type-labels";
import { cn } from "@/lib/utils";
import type { ApiKeyItem, LlmRequestType } from "@/types/api";

interface ApiKeyCardProps {
  apiKey: ApiKeyItem;
  isToggling?: boolean;
  isUpdatingScope?: boolean;
  onToggleStatus: (apiKey: ApiKeyItem) => void;
  onUpdateScope: (keyId: string, scope: LlmRequestType[]) => Promise<void>;
  onDelete: (apiKey: ApiKeyItem) => void;
}

export function ApiKeyCard({
  apiKey,
  isToggling = false,
  isUpdatingScope = false,
  onToggleStatus,
  onUpdateScope,
  onDelete,
}: ApiKeyCardProps) {
  const [isEditingScope, setIsEditingScope] = useState(false);
  const [draftScope, setDraftScope] = useState<LlmRequestType[]>(
    apiKey.request_type_scope,
  );

  // Sunucu güncellemesi sonrası taslağı senkronla (düzenleme kapalıyken).
  useEffect(() => {
    if (!isEditingScope) setDraftScope(apiKey.request_type_scope);
  }, [apiKey.request_type_scope, isEditingScope]);

  const handleSaveScope = async () => {
    await onUpdateScope(apiKey.id, draftScope);
    setIsEditingScope(false);
  };

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <span
            className={cn(
              "inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              API_PROVIDER_BADGE_CLASS[apiKey.provider],
            )}
          >
            {API_PROVIDER_LABELS[apiKey.provider]}
          </span>
          <h3 className="text-base font-semibold text-navy-800">{apiKey.key_alias}</h3>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-red-600 hover:bg-red-50 hover:text-red-700"
            onClick={() => onDelete(apiKey)}
            aria-label={`${apiKey.key_alias} anahtarını sil`}
          >
            Sil
          </Button>
        </div>
      </div>

      <div className="rounded-md bg-gray-50 px-3 py-2 font-mono text-sm text-gray-600">
        {formatMaskedApiKey(apiKey.key_alias, apiKey.key_suffix)}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex h-2.5 w-2.5 rounded-full",
              apiKey.is_active ? "bg-emerald-500" : "bg-gray-300",
            )}
            aria-hidden
          />
          <span className="text-gray-600">
            {apiKey.is_active ? "Aktif" : "Pasif"}
          </span>
        </div>

        <label className="flex cursor-pointer items-center gap-2">
          <span className="text-gray-600">Durum</span>
          <input
            type="checkbox"
            role="switch"
            aria-label={`${apiKey.key_alias} durumunu değiştir`}
            checked={apiKey.is_active}
            disabled={isToggling}
            onChange={() => onToggleStatus(apiKey)}
            className="h-5 w-9 cursor-pointer appearance-none rounded-full bg-gray-200 transition-colors checked:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </label>
      </div>

      <div className="space-y-2 border-t border-gray-100 pt-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Operasyon kapsamı
          </span>
          {!isEditingScope ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsEditingScope(true)}
            >
              Düzenle
            </Button>
          ) : null}
        </div>

        {isEditingScope ? (
          <div className="space-y-3">
            <RequestTypeScopeSelector
              value={draftScope}
              onChange={setDraftScope}
              disabled={isUpdatingScope}
            />
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isUpdatingScope}
                onClick={() => {
                  setDraftScope(apiKey.request_type_scope);
                  setIsEditingScope(false);
                }}
              >
                İptal
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={isUpdatingScope}
                onClick={() => void handleSaveScope()}
              >
                {isUpdatingScope ? "Kaydediliyor…" : "Kaydet"}
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-700">
            {formatScopeSummary(apiKey.request_type_scope)}
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3 text-xs text-gray-500">
        {apiKey.model ? <span>Model: {apiKey.model}</span> : null}
        <span>Öncelik: {apiKey.priority_order}</span>
        <span>Eklendi: {formatNumericDate(apiKey.created_at)}</span>
      </div>
    </Card>
  );
}
