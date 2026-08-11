import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { perfTestApi } from "@/lib/api";
import type { PerfResult, PerfRun } from "@/lib/api";
import { ArrowLeft, CheckCircle, Loader2, Square, XCircle, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function PerfRunDetailPage() {
  const { appId, runId } = useParams<{ appId: string; runId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: run } = useQuery({
    queryKey: ["perf-run", appId, runId],
    queryFn: () => perfTestApi.getRun(appId!, runId!),
    enabled: !!appId && !!runId,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });

  const isRunning = run?.status === "running";

  const { data: resultsResp } = useQuery({
    queryKey: ["perf-results", appId, runId],
    queryFn: () => perfTestApi.getResults(appId!, runId!, 5000, 0),
    enabled: !!appId && !!runId,
    refetchInterval: isRunning ? 1500 : false,
  });
  const results: PerfResult[] = resultsResp?.results ?? [];

  const { data: jobs = [] } = useQuery({
    queryKey: ["perf-jobs", appId],
    queryFn: () => perfTestApi.listJobs(appId!),
    enabled: !!appId && isRunning,
    refetchInterval: isRunning ? 1500 : false,
  });
  const activeJob = jobs.find((j) =>
    typeof j.result === "object" && j.result !== null && (j.result as Record<string, unknown>).run_id === runId,
  );

  const stopMutation = useMutation({
    mutationFn: () => perfTestApi.stop(appId!, activeJob!.job_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["perf-run", appId, runId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => perfTestApi.delete(appId!, runId!),
    onSuccess: () => navigate(`/apps/${appId}/perf-test`),
  });

  const errors = useMemo(() => results.filter((r) => r.error), [results]);

  if (!run) {
    return <div className="text-center py-16 text-gray-400">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/apps/${appId}/perf-test`)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4" /> Perf Test
        </button>
      </div>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={run.status} />
              <h1 className="text-lg font-bold text-gray-900 truncate">
                {run.golden_set_version} · {run.concurrency}× workers
              </h1>
            </div>
            <p className="text-xs text-gray-500 font-mono">{run.run_id}</p>
            <p className="text-xs text-gray-400 mt-1">
              Started {new Date(run.started_at).toLocaleString()}
              {run.finished_at && ` · finished ${new Date(run.finished_at).toLocaleString()}`}
            </p>
            {run.error_message && (
              <p className="text-xs text-red-600 mt-1">{run.error_message}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {run.status === "running" && activeJob && (
              <button
                onClick={() => stopMutation.mutate()}
                disabled={stopMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50"
              >
                {stopMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3 fill-current" />}
                Stop
              </button>
            )}
            {run.status !== "running" && (
              <button
                onClick={() => { if (confirm("Delete this perf run?")) deleteMutation.mutate(); }}
                disabled={deleteMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                <Trash2 className="w-3 h-3" /> Delete
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Aggregates strip */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Stat label="Total" value={String(run.total_requests)} />
        <Stat label="Success" value={String(run.success_count)} tone="green" />
        <Stat label="Errors" value={String(run.error_count)} tone={run.error_count > 0 ? "red" : undefined} />
        <Stat label="Avg" value={fmtMs(run.avg_ms)} />
        <Stat label="p95" value={fmtMs(run.p95_ms)} />
        <Stat label="p99" value={fmtMs(run.p99_ms)} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="p50" value={fmtMs(run.p50_ms)} />
        <Stat label="Max" value={fmtMs(run.max_ms)} />
        <Stat
          label="Error rate"
          value={run.total_requests > 0 ? `${((run.error_count / run.total_requests) * 100).toFixed(1)}%` : "—"}
          tone={run.error_count > 0 ? "red" : undefined}
        />
        <Stat
          label="Stop after"
          value={run.stop_mode === "iterations" ? `${run.iterations} req` : `${run.duration_s}s`}
        />
      </div>

      {/* Latency chart */}
      {results.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-700">Latency per request (ms)</h3>
            {isRunning && (
              <span className="inline-flex items-center gap-1 text-xs text-violet-600">
                <Loader2 className="w-3 h-3 animate-spin" /> Live · {results.length} so far
              </span>
            )}
          </div>
          <LatencyChart results={results} run={run} />
        </div>
      )}

      {/* Errors table */}
      {errors.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <h3 className="text-sm font-medium text-red-700 mb-3">Errors ({errors.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100">
                  <th className="py-1.5 pr-3">#</th>
                  <th className="py-1.5 pr-3">Status</th>
                  <th className="py-1.5 pr-3">Latency</th>
                  <th className="py-1.5 pr-3">tc_id</th>
                  <th className="py-1.5">Error</th>
                </tr>
              </thead>
              <tbody>
                {errors.slice(0, 200).map((e) => (
                  <tr key={e.seq} className="border-b border-gray-50">
                    <td className="py-1 pr-3 font-mono text-gray-400">{e.seq}</td>
                    <td className="py-1 pr-3 font-mono">{e.status_code ?? "—"}</td>
                    <td className="py-1 pr-3 font-mono">{e.latency_ms.toFixed(0)}ms</td>
                    <td className="py-1 pr-3 font-mono text-gray-400 truncate max-w-[140px]">{e.tc_id ?? "—"}</td>
                    <td className="py-1 font-mono text-red-600 truncate max-w-[400px]" title={e.error ?? ""}>{e.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {errors.length > 200 && (
              <p className="text-xs text-gray-400 mt-2">Showing first 200 of {errors.length}.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function fmtMs(v: number | null): string {
  if (v == null) return "—";
  return `${v.toFixed(0)}ms`;
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "green" | "red" }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wide text-gray-400">{label}</p>
      <p className={cn(
        "text-lg font-bold mt-0.5",
        tone === "green" ? "text-green-700" :
        tone === "red" ? "text-red-700" :
        "text-gray-800"
      )}>{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: PerfRun["status"] }) {
  const map = {
    running:  { bg: "bg-violet-50",  fg: "text-violet-700",  Icon: Loader2,     label: "Running",  spin: true  },
    complete: { bg: "bg-green-50",   fg: "text-green-700",   Icon: CheckCircle, label: "Complete", spin: false },
    failed:   { bg: "bg-red-50",     fg: "text-red-700",     Icon: XCircle,     label: "Failed",   spin: false },
    stopped:  { bg: "bg-amber-50",   fg: "text-amber-700",   Icon: Square,      label: "Stopped",  spin: false },
  } as const;
  const m = map[status];
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full", m.bg, m.fg)}>
      <m.Icon className={cn("w-3 h-3", m.spin && "animate-spin")} />
      {m.label}
    </span>
  );
}

function LatencyChart({ results, run }: { results: PerfResult[]; run: PerfRun }) {
  const sorted = [...results].sort((a, b) => a.seq - b.seq);
  if (sorted.length === 0) return null;

  const W = 800;
  const H = 220;
  const padL = 38;
  const padR = 8;
  const padT = 8;
  const padB = 18;

  const maxLat = Math.max(...sorted.map((r) => r.latency_ms), run.max_ms ?? 0, 1);
  const minSeq = sorted[0].seq;
  const maxSeq = sorted[sorted.length - 1].seq || 1;

  const sx = (seq: number) =>
    padL + ((seq - minSeq) / Math.max(1, maxSeq - minSeq)) * (W - padL - padR);
  const sy = (lat: number) =>
    H - padB - (lat / maxLat) * (H - padT - padB);

  const points = sorted.map((r) => `${sx(r.seq).toFixed(1)},${sy(r.latency_ms).toFixed(1)}`).join(" ");

  // Reference lines for p50/p95/p99
  const lines: { y: number; label: string; color: string }[] = [];
  if (run.p50_ms != null) lines.push({ y: sy(run.p50_ms), label: `p50 ${run.p50_ms.toFixed(0)}`, color: "#a3a3a3" });
  if (run.p95_ms != null) lines.push({ y: sy(run.p95_ms), label: `p95 ${run.p95_ms.toFixed(0)}`, color: "#f59e0b" });
  if (run.p99_ms != null) lines.push({ y: sy(run.p99_ms), label: `p99 ${run.p99_ms.toFixed(0)}`, color: "#dc2626" });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[220px]">
      {/* axes */}
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="#e5e7eb" />
      <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#e5e7eb" />
      {/* dots */}
      {sorted.map((r) => (
        <circle
          key={r.seq}
          cx={sx(r.seq)}
          cy={sy(r.latency_ms)}
          r={1.6}
          fill={r.error ? "#dc2626" : "#7c3aed"}
          opacity={0.55}
        />
      ))}
      {/* polyline */}
      <polyline points={points} fill="none" stroke="#7c3aed" strokeWidth={0.8} opacity={0.35} />
      {/* percentile lines */}
      {lines.map((l) => (
        <g key={l.label}>
          <line x1={padL} y1={l.y} x2={W - padR} y2={l.y} stroke={l.color} strokeWidth={1} strokeDasharray="4 4" opacity={0.6} />
          <text x={W - padR - 4} y={l.y - 3} fontSize="9" textAnchor="end" fill={l.color}>{l.label}</text>
        </g>
      ))}
      {/* y-axis labels */}
      <text x={padL - 4} y={padT + 8} fontSize="9" textAnchor="end" fill="#6b7280">{maxLat.toFixed(0)}ms</text>
      <text x={padL - 4} y={H - padB} fontSize="9" textAnchor="end" fill="#6b7280">0</text>
      <text x={padL} y={H - 4} fontSize="9" fill="#6b7280">#{minSeq}</text>
      <text x={W - padR} y={H - 4} fontSize="9" textAnchor="end" fill="#6b7280">#{maxSeq}</text>
    </svg>
  );
}
