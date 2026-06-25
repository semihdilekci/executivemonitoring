"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/card";
import { API_PROVIDER_LABELS } from "@/lib/api-labels";
import { formatNumericDate } from "@/lib/date-format";
import type { ApiUsageStatsResponse, UsageStatsRow } from "@/types/api";

interface UsageChartProps {
  data: ApiUsageStatsResponse | undefined;
  isLoading?: boolean;
}

interface DailyTokenPoint {
  date: string;
  label: string;
  groq: number;
  gemini: number;
  anthropic: number;
  total: number;
}

interface ProviderBreakdownPoint {
  provider: string;
  tokens: number;
}

function aggregateDailyTokens(rows: UsageStatsRow[]): DailyTokenPoint[] {
  const byDate = new Map<string, DailyTokenPoint>();

  for (const row of rows) {
    const existing = byDate.get(row.date) ?? {
      date: row.date,
      label: formatNumericDate(row.date),
      groq: 0,
      gemini: 0,
      anthropic: 0,
      total: 0,
    };

    if (row.provider === "groq") {
      existing.groq += row.total_tokens;
    } else if (row.provider === "gemini") {
      existing.gemini += row.total_tokens;
    } else if (row.provider === "anthropic") {
      existing.anthropic += row.total_tokens;
    }
    existing.total += row.total_tokens;
    byDate.set(row.date, existing);
  }

  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function aggregateByProvider(rows: UsageStatsRow[]): ProviderBreakdownPoint[] {
  const totals = new Map<string, number>();

  for (const row of rows) {
    const current = totals.get(row.provider) ?? 0;
    totals.set(row.provider, current + row.total_tokens);
  }

  return Array.from(totals.entries()).map(([provider, tokens]) => ({
    provider: API_PROVIDER_LABELS[provider as keyof typeof API_PROVIDER_LABELS] ?? provider,
    tokens,
  }));
}

function formatTokenCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function UsageChart({ data, isLoading }: UsageChartProps) {
  const dailyPoints = useMemo(
    () => aggregateDailyTokens(data?.data ?? []),
    [data?.data],
  );

  const providerPoints = useMemo(
    () => aggregateByProvider(data?.data ?? []),
    [data?.data],
  );

  const totalTokens = useMemo(
    () => (data?.data ?? []).reduce((sum, row) => sum + row.total_tokens, 0),
    [data?.data],
  );

  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse rounded-md bg-gray-100" aria-busy="true">
          <span className="sr-only">Kullanım grafiği yükleniyor…</span>
        </div>
      </Card>
    );
  }

  if (!data || data.data.length === 0) {
    return (
      <Card>
        <h2 className="text-lg font-semibold text-navy-800">Token Kullanımı</h2>
        <p className="mt-2 text-sm text-gray-500">
          Seçilen dönemde kullanım verisi bulunamadı.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Toplam token
          </p>
          <p className="mt-1 text-2xl font-bold text-navy-800">
            {formatTokenCount(totalTokens)}
          </p>
        </Card>
        <Card>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Kayıt sayısı
          </p>
          <p className="mt-1 text-2xl font-bold text-navy-800">{data.data.length}</p>
        </Card>
        <Card>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Dönem
          </p>
          <p className="mt-1 text-2xl font-bold text-navy-800 capitalize">
            {data.period === "daily" ? "Günlük" : data.period}
          </p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-navy-800">
          Günlük token kullanımı
        </h2>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dailyPoints} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={formatTokenCount} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number) => [formatTokenCount(value), "Token"]}
                labelFormatter={(label) => `Tarih: ${label}`}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="groq"
                name="Groq"
                stroke="#0EA5E9"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="gemini"
                name="Gemini"
                stroke="#8B5CF6"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="anthropic"
                name="Claude"
                stroke="#F59E0B"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="total"
                name="Toplam"
                stroke="#1E3A5F"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {providerPoints.length > 0 ? (
        <Card>
          <h2 className="mb-4 text-lg font-semibold text-navy-800">
            Sağlayıcı bazlı dağılım
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={providerPoints} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="provider" tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={formatTokenCount} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number) => [formatTokenCount(value), "Token"]}
                />
                <Bar dataKey="tokens" name="Token" fill="#1E3A5F" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
