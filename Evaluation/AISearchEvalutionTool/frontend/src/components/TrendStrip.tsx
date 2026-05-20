import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus, History, AlertCircle } from "lucide-react";
import { resultsApi } from "@/lib/api";
import type { ScalarDelta, TrendDirection } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface TrendStripProps {
  appId: string;
  runId: string;
}

export default function TrendStrip({ appId, runId }: TrendStripProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["trends", appId, runId],
    queryFn: () => resultsApi.getTrends(appId, runId),
    enabled: !!appId && !!runId,
    staleTime: 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 animate-pulse h-14" />
    );
  }

  if (isError || !data) {
    return null; // silent failure — trend strip is a nice-to-have
  }

  // No previous run — show a flat "first run" banner
  if (!data.has_baseline) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-2.5 flex items-center gap-3 text-xs text-gray-500">
        <History className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        <span>
          First completed run on golden set
          <span className="ml-1 font-mono text-gray-700">{data.golden_set_version}</span>
          {" "}— no baseline yet to compare against.
        </span>
      </div>
    );
  }

  const { deltas, previous_run_id, previous_run_date } = data;
  const prevLabel = previous_run_date
    ? new Date(previous_run_date).toLocaleString(undefined, {
        month: "short", day: "numeric", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : "previous run";

  // Pick the largest-magnitude failure-category delta to surface
  const worstFailureCat = pickWorstFailure(deltas.failures_by_category);

  return (
    <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-xs text-gray-500 shrink-0">
          <History className="w-3.5 h-3.5 text-violet-500" />
          <span>
            vs{" "}
            <span className="font-mono text-gray-700">{(previous_run_id || "").slice(0, 12)}</span>
            <span className="text-gray-400 ml-1">({prevLabel})</span>
          </span>
        </div>

        <div className="h-4 w-px bg-gray-200" />

        <div className="flex items-center gap-2 flex-wrap">
          <TrendChip
            label="Pass rate"
            delta={deltas.pass_rate}
            format={(v) => `${Math.round(v * 100)}%`}
            deltaFormat={(d) => `${d > 0 ? "+" : ""}${(d * 100).toFixed(1)}pp`}
          />
          <TrendChip
            label="Failed"
            delta={deltas.failed_cases}
            format={(v) => String(v)}
            deltaFormat={(d) => `${d > 0 ? "+" : ""}${d}`}
          />
          <TrendChip
            label="Avg chunk rank"
            delta={deltas.avg_chunk_rank}
            format={(v) => `#${v.toFixed(1)}`}
            deltaFormat={(d) => `${d > 0 ? "+" : ""}${d.toFixed(1)}`}
          />
          {deltas.weakest_judge_metric.changed && deltas.weakest_judge_metric.current && (
            <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border border-amber-200 bg-amber-50 text-amber-800">
              <AlertCircle className="w-3 h-3" />
              Weakest metric shifted:{" "}
              <span className="font-mono">
                {deltas.weakest_judge_metric.previous ?? "—"} → {deltas.weakest_judge_metric.current}
              </span>
            </span>
          )}
          {worstFailureCat && (
            <TrendChip
              label={`Failures (${worstFailureCat.cat})`}
              delta={worstFailureCat.delta}
              format={(v) => String(v)}
              deltaFormat={(d) => `${d > 0 ? "+" : ""}${d}`}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function TrendChip({
  label, delta, format, deltaFormat,
}: {
  label: string;
  delta: ScalarDelta;
  format: (v: number) => string;
  deltaFormat: (d: number) => string;
}) {
  if (delta.current == null) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border border-gray-200 bg-gray-50 text-gray-500">
        <span className="text-gray-400">{label}</span>
        <span className="font-mono">—</span>
      </span>
    );
  }

  const tone = directionTone(delta.direction);
  const Icon =
    delta.direction === "better" ? TrendingUp
    : delta.direction === "worse" ? TrendingDown
    : Minus;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border",
        tone
      )}
      title={
        delta.previous != null
          ? `Was ${format(delta.previous)} on previous run`
          : "No previous value"
      }
    >
      <span className="text-gray-500">{label}</span>
      <span className="font-mono font-semibold">{format(delta.current)}</span>
      {delta.delta != null && (
        <span className="inline-flex items-center gap-0.5 font-mono">
          <Icon className="w-3 h-3" />
          {deltaFormat(delta.delta)}
        </span>
      )}
    </span>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function directionTone(d: TrendDirection): string {
  if (d === "better") return "border-green-200 bg-green-50 text-green-800";
  if (d === "worse")  return "border-red-200 bg-red-50 text-red-800";
  return "border-gray-200 bg-gray-50 text-gray-700";
}

function pickWorstFailure(
  cats: Record<string, ScalarDelta>,
): { cat: string; delta: ScalarDelta } | null {
  let worst: { cat: string; delta: ScalarDelta } | null = null;
  for (const [cat, d] of Object.entries(cats)) {
    if (d.direction !== "worse") continue;
    if (typeof d.delta !== "number") continue;
    if (!worst || d.delta > (worst.delta.delta ?? 0)) {
      worst = { cat, delta: d };
    }
  }
  return worst;
}
