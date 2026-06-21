"use client";

import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from "@/components/common/data-table";
import { formatNumericDateTime } from "@/lib/date-format";
import {
  PIPELINE_RUN_TYPE_COLORS,
  PIPELINE_RUN_TYPE_LABELS,
  PIPELINE_STAGE_LABELS,
  PIPELINE_STAGE_ORDER,
  PIPELINE_STATUS_META,
  PIPELINE_STEP_DOT_COLORS,
  derivePipelineStageStates,
  formatPipelineDuration,
  getSourceTypeChipLabel,
} from "@/lib/pipeline-labels";
import { cn } from "@/lib/utils";
import type { PipelineRunStatus, PipelineRunSummary } from "@/types/api";

interface PipelineRunTableProps {
  runs: PipelineRunSummary[];
  onRowClick: (run: PipelineRunSummary) => void;
  /** Çalışan run sürelerini canlı tutmak için tetiklenen yeniden render zaman damgası. */
  now: number;
}

export function PipelineStatusBadge({ status }: { status: PipelineRunStatus }) {
  const meta = PIPELINE_STATUS_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        meta.badgeClass,
      )}
    >
      {meta.pulse ? (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden />
      ) : null}
      {meta.label}
    </span>
  );
}

function PipelineStageDots({ run }: { run: PipelineRunSummary }) {
  const states = derivePipelineStageStates(run);

  return (
    <div className="flex items-center gap-1.5" role="img" aria-label="Aşama ilerlemesi">
      {PIPELINE_STAGE_ORDER.map((stage) => {
        const state = states[stage];
        return (
          <span
            key={stage}
            className="inline-flex flex-col items-center gap-1"
            title={`${PIPELINE_STAGE_LABELS[stage]}: ${state}`}
          >
            <span
              className={cn("h-2.5 w-2.5 rounded-full", PIPELINE_STEP_DOT_COLORS[state])}
              aria-hidden
            />
            <span className="text-[10px] text-gray-400">
              {PIPELINE_STAGE_LABELS[stage]}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function SourceChips({ run }: { run: PipelineRunSummary }) {
  if (run.run_type === "digest_update" || run.source_types.length === 0) {
    return <span className="text-gray-400">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {run.source_types.map((value) => (
        <span
          key={value}
          className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700"
        >
          {getSourceTypeChipLabel(value)}
        </span>
      ))}
    </div>
  );
}

export function PipelineRunTable({ runs, onRowClick, now }: PipelineRunTableProps) {
  return (
    <DataTable>
      <table className="min-w-full">
        <DataTableHeader>
          <DataTableHead className="w-[150px]">Başlangıç</DataTableHead>
          <DataTableHead className="w-[140px]">Tip</DataTableHead>
          <DataTableHead className="w-[150px]">Kaynaklar</DataTableHead>
          <DataTableHead className="w-[120px]">Durum</DataTableHead>
          <DataTableHead className="w-[180px]">İlerleme</DataTableHead>
          <DataTableHead className="w-[100px]">Süre</DataTableHead>
        </DataTableHeader>
        <DataTableBody>
          {runs.map((run) => (
            <DataTableRow
              key={run.id}
              className="cursor-pointer hover:bg-gray-50"
              onClick={() => onRowClick(run)}
            >
              <DataTableCell>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onRowClick(run);
                  }}
                  className="block w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
                  aria-label={`${PIPELINE_RUN_TYPE_LABELS[run.run_type]} detayını aç`}
                >
                  {formatNumericDateTime(run.started_at ?? run.created_at)}
                </button>
              </DataTableCell>
              <DataTableCell>
                <span
                  className={cn(
                    "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    PIPELINE_RUN_TYPE_COLORS[run.run_type],
                  )}
                >
                  {PIPELINE_RUN_TYPE_LABELS[run.run_type]}
                </span>
              </DataTableCell>
              <DataTableCell>
                <SourceChips run={run} />
              </DataTableCell>
              <DataTableCell>
                <PipelineStatusBadge status={run.status} />
              </DataTableCell>
              <DataTableCell>
                <PipelineStageDots run={run} />
              </DataTableCell>
              <DataTableCell className="text-sm text-gray-600">
                {formatPipelineDuration(run.started_at, run.finished_at, now)}
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </table>
    </DataTable>
  );
}
