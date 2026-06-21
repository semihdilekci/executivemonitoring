"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  API_PROVIDER_BADGE_CLASS,
  API_PROVIDER_LABELS,
  formatMaskedApiKey,
} from "@/lib/api-labels";
import { formatNumericDate } from "@/lib/date-format";
import { cn } from "@/lib/utils";
import type { ApiKeyItem } from "@/types/api";

interface ApiKeyCardProps {
  apiKey: ApiKeyItem;
  isToggling?: boolean;
  onToggleStatus: (apiKey: ApiKeyItem) => void;
  onDelete: (apiKey: ApiKeyItem) => void;
}

export function ApiKeyCard({
  apiKey,
  isToggling = false,
  onToggleStatus,
  onDelete,
}: ApiKeyCardProps) {
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

      <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3 text-xs text-gray-500">
        <span>Öncelik: {apiKey.priority_order}</span>
        <span>Eklendi: {formatNumericDate(apiKey.created_at)}</span>
      </div>
    </Card>
  );
}
