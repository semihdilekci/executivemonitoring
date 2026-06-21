import type {
  PipelineRunStatus,
  PipelineRunSummary,
  PipelineRunType,
  PipelineStage,
  PipelineStepStatus,
} from "@/types/api";

export const PIPELINE_RUN_TYPE_LABELS: Record<PipelineRunType, string> = {
  collect_pipeline: "Collect Pipeline",
  digest_update: "Bülten Güncelleme",
};

export const PIPELINE_RUN_TYPE_COLORS: Record<PipelineRunType, string> = {
  collect_pipeline: "bg-blue-100 text-blue-800",
  digest_update: "bg-purple-100 text-purple-800",
};

export interface PipelineStatusMeta {
  label: string;
  badgeClass: string;
  /** Çalışan run rozetinde nabız efekti. */
  pulse: boolean;
}

export const PIPELINE_STATUS_META: Record<PipelineRunStatus, PipelineStatusMeta> = {
  pending: { label: "Bekliyor", badgeClass: "bg-gray-100 text-gray-700", pulse: false },
  running: { label: "Çalışıyor", badgeClass: "bg-blue-100 text-blue-800", pulse: true },
  completed: { label: "Tamamlandı", badgeClass: "bg-green-100 text-green-800", pulse: false },
  partial: { label: "Kısmi", badgeClass: "bg-yellow-100 text-yellow-800", pulse: false },
  failed: { label: "Başarısız", badgeClass: "bg-red-100 text-red-800", pulse: false },
  cancelled: { label: "İptal", badgeClass: "bg-gray-100 text-gray-600", pulse: false },
};

/** Aşama sırası (`sequence`) — Toplama → Ingest → İşleme → Bülten. */
export const PIPELINE_STAGE_ORDER: PipelineStage[] = [
  "collect",
  "ingest",
  "process",
  "digest",
];

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  collect: "Toplama",
  ingest: "Ingest",
  process: "İşleme",
  digest: "Bülten",
};

/** `S-ADMIN-PIPELINE-TRIGGER` kaynak seçim chip etiketleri (`source_type` değerleri). */
export const SOURCE_TYPE_CHIP_LABELS: Record<string, string> = {
  rss: "RSS",
  email: "E-posta",
  gov: "Resmi",
  all: "Tümü",
};

export function getSourceTypeChipLabel(value: string): string {
  return SOURCE_TYPE_CHIP_LABELS[value] ?? value;
}

export const PIPELINE_RUN_TYPE_FILTERS: {
  value: PipelineRunType | "all";
  label: string;
}[] = [
  { value: "all", label: "Tümü" },
  { value: "collect_pipeline", label: "Collect Pipeline" },
  { value: "digest_update", label: "Bülten Güncelleme" },
];

export const PIPELINE_STATUS_FILTERS: {
  value: PipelineRunStatus | "all";
  label: string;
}[] = [
  { value: "all", label: "Tümü" },
  { value: "pending", label: "Bekliyor" },
  { value: "running", label: "Çalışıyor" },
  { value: "completed", label: "Tamamlandı" },
  { value: "partial", label: "Kısmi" },
  { value: "failed", label: "Başarısız" },
  { value: "cancelled", label: "İptal" },
];

const ACTIVE_RUN_STATUSES = new Set<PipelineRunStatus>(["pending", "running"]);

export function isActiveRun(status: PipelineRunStatus): boolean {
  return ACTIVE_RUN_STATUSES.has(status);
}

/**
 * Liste satırı için 4 aşamalı mini step göstergesinin durumlarını türetir.
 *
 * Liste özeti (`PipelineRunSummary`) adım detayını içermez — yalnızca `status` +
 * `current_stage`. Gösterge bu nedenle en iyi-çaba (best-effort): yeşil yalnızca
 * emin olunan durumda gösterilir. Aşama-bazlı kesin durum detay ekranındadır
 * (`S-ADMIN-PIPELINE-DETAIL`, İterasyon 8). `digest_update` run'ında yalnızca
 * Bülten aşaması aktiftir; diğerleri `skipped` (`Docs/01` §5.5).
 */
export function derivePipelineStageStates(
  run: PipelineRunSummary,
): Record<PipelineStage, PipelineStepStatus> {
  const states = {} as Record<PipelineStage, PipelineStepStatus>;

  if (run.run_type === "digest_update") {
    for (const stage of PIPELINE_STAGE_ORDER) {
      states[stage] = stage === "digest" ? mapDigestStage(run.status) : "skipped";
    }
    return states;
  }

  const currentIndex = run.current_stage
    ? PIPELINE_STAGE_ORDER.indexOf(run.current_stage)
    : -1;

  PIPELINE_STAGE_ORDER.forEach((stage, index) => {
    states[stage] = mapCollectStage(run.status, index, currentIndex);
  });
  return states;
}

function mapDigestStage(status: PipelineRunStatus): PipelineStepStatus {
  switch (status) {
    case "completed":
    case "partial":
      return "completed";
    case "failed":
      return "failed";
    case "running":
      return "running";
    case "cancelled":
      return "skipped";
    default:
      return "pending";
  }
}

function mapCollectStage(
  status: PipelineRunStatus,
  index: number,
  currentIndex: number,
): PipelineStepStatus {
  switch (status) {
    case "completed":
    case "partial":
      return "completed";
    case "running":
      if (currentIndex < 0) return "pending";
      if (index < currentIndex) return "completed";
      if (index === currentIndex) return "running";
      return "pending";
    case "failed":
    case "cancelled":
    case "pending":
    default:
      return "pending";
  }
}

export const PIPELINE_STEP_DOT_COLORS: Record<PipelineStepStatus, string> = {
  completed: "bg-green-500",
  running: "bg-blue-500 animate-pulse",
  failed: "bg-red-500",
  skipped: "bg-gray-300",
  pending: "bg-gray-200",
};

/**
 * Detay timeline'ı (`S-ADMIN-PIPELINE-DETAIL`) aşama ikonu + etiketi + renkleri.
 * İkon: ✓ tamamlandı / ⟳ çalışıyor / ✕ hata / ⊘ atlandı / ○ bekliyor (`Docs/06`).
 */
export interface PipelineStepStatusMeta {
  label: string;
  icon: string;
  /** İkon dairesi arka plan + metin rengi. */
  circleClass: string;
  /** Timeline dikey bağlayıcı çizgi rengi. */
  connectorClass: string;
  pulse: boolean;
}

export const PIPELINE_STEP_STATUS_META: Record<
  PipelineStepStatus,
  PipelineStepStatusMeta
> = {
  completed: {
    label: "Tamamlandı",
    icon: "✓",
    circleClass: "bg-green-100 text-green-700 ring-green-200",
    connectorClass: "bg-green-300",
    pulse: false,
  },
  running: {
    label: "Çalışıyor",
    icon: "⟳",
    circleClass: "bg-blue-100 text-blue-700 ring-blue-200",
    connectorClass: "bg-blue-200",
    pulse: true,
  },
  failed: {
    label: "Hata",
    icon: "✕",
    circleClass: "bg-red-100 text-red-700 ring-red-200",
    connectorClass: "bg-red-200",
    pulse: false,
  },
  skipped: {
    label: "Atlandı",
    icon: "⊘",
    circleClass: "bg-gray-100 text-gray-400 ring-gray-200",
    connectorClass: "bg-gray-200",
    pulse: false,
  },
  pending: {
    label: "Bekliyor",
    icon: "○",
    circleClass: "bg-gray-100 text-gray-400 ring-gray-200",
    connectorClass: "bg-gray-200",
    pulse: false,
  },
};

/**
 * Collect aşamasının `detail` JSONB'sinden kaynak-bazlı kırılım türetir
 * (`{ rss: {ok, published}, gov: {...}, email: {ok:false, error} }`). Güvenli
 * okunur: bilinmeyen/eksik alanlar atlanır, ham JSON render edilmez (`Docs/06`).
 */
export interface CollectSourceBreakdown {
  type: string;
  label: string;
  ok: boolean;
  /** `ok` ise yayınlanan kayıt sayısı; aksi halde null. */
  published: number | null;
  /** Başarısız kaynak sayısı (collector içi); ok ise. */
  sourcesFailed: number | null;
  error: string | null;
  requestId: string | null;
}

export function deriveCollectBreakdown(
  detail: Record<string, unknown> | null | undefined,
): CollectSourceBreakdown[] {
  if (!detail) return [];
  const out: CollectSourceBreakdown[] = [];
  for (const type of Object.keys(SOURCE_TYPE_CHIP_LABELS)) {
    const entry = detail[type];
    if (!entry || typeof entry !== "object") continue;
    const row = entry as Record<string, unknown>;
    const ok = row.ok === true;
    out.push({
      type,
      label: getSourceTypeChipLabel(type),
      ok,
      published: typeof row.published === "number" ? row.published : null,
      sourcesFailed:
        typeof row.sources_failed === "number" ? row.sources_failed : null,
      error: typeof row.error === "string" ? row.error : null,
      requestId: typeof row.request_id === "string" ? row.request_id : null,
    });
  }
  return out;
}

const TERMINAL_RUN_STATUSES = new Set<PipelineRunStatus>([
  "completed",
  "partial",
  "failed",
  "cancelled",
]);

export function isTerminalRun(status: PipelineRunStatus): boolean {
  return TERMINAL_RUN_STATUSES.has(status);
}

/** Başlangıç–bitiş süresini insan-okur biçime çevirir; çalışırken `now` geçilir. */
export function formatPipelineDuration(
  startedAt: string | null,
  finishedAt: string | null,
  now?: number,
): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : (now ?? Date.now());
  const diffSeconds = Math.max(0, Math.floor((end - start) / 1000));

  if (diffSeconds < 60) return `${diffSeconds} sn`;
  const minutes = Math.floor(diffSeconds / 60);
  const seconds = diffSeconds % 60;
  if (minutes < 60) return `${minutes} dk ${seconds} sn`;
  const hours = Math.floor(minutes / 60);
  return `${hours} sa ${minutes % 60} dk`;
}
