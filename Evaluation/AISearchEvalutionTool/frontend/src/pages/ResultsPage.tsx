import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { resultsApi } from "@/lib/api";
import type { EvalRun } from "@/lib/api";
import {
  BarChart3, ChevronRight, TrendingUp, TrendingDown, Minus, Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ConfirmDialog from "@/components/ConfirmDialog";

export default function ResultsPage() {
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<EvalRun | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["eval-runs", appId],
    queryFn: () => resultsApi.listRuns(appId!),
    enabled: !!appId,
  });

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => resultsApi.delete(appId!, runId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["eval-runs", appId] });
      setPendingDelete(null);
      setDeleteError(null);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail
        ?? (err as Error)?.message
        ?? "Failed to delete run.";
      setDeleteError(msg);
    },
  });

  if (isLoading) {
    return <div className="text-center py-16 text-gray-400">Loading results...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Results</h1>
        <p className="text-sm text-gray-500 mt-1">Evaluation run history and pass rates</p>
      </div>

      {runs.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-gray-200 rounded-xl">
          <BarChart3 className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No evaluation runs yet</p>
          <p className="text-gray-400 text-sm mt-1">
            Run an evaluation from the Evaluate page
          </p>
        </div>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              label="Total Runs"
              value={String(runs.length)}
              sub="all time"
            />
            <StatCard
              label="Latest Pass Rate"
              value={`${(runs[0].pass_rate * 100).toFixed(1)}%`}
              sub={runs[0].golden_set_version}
              trend={runs.length > 1 ? runs[0].pass_rate - runs[1].pass_rate : null}
            />
            <StatCard
              label="Cases Evaluated"
              value={String(runs.reduce((s, r) => s + r.total_cases, 0))}
              sub="across all runs"
            />
          </div>

          {/* Runs table */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Run ID</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Golden Set</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">RAG Version</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Pass Rate</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Cases</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Avg Chunk Rank</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Status</th>
                  <th className="px-5 py-3 font-medium text-gray-500 text-xs">Date</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {runs.map((run, idx) => (
                  <RunRow
                    key={run.run_id}
                    run={run}
                    prevPassRate={idx < runs.length - 1 ? runs[idx + 1].pass_rate : null}
                    onClick={() => navigate(`/apps/${appId}/results/${run.run_id}`)}
                    onDelete={() => {
                      setDeleteError(null);
                      setPendingDelete(run);
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete this evaluation run?"
        description={pendingDelete && (
          <>
            This permanently removes the run and all <strong>{pendingDelete.total_cases}</strong>{" "}
            associated result rows. This action cannot be undone.
          </>
        )}
        confirmLabel="Delete run"
        loading={deleteMutation.isPending}
        error={deleteError}
        onCancel={() => {
          if (deleteMutation.isPending) return;
          setPendingDelete(null);
          setDeleteError(null);
        }}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.run_id)}
      >
        {pendingDelete && (
          <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600 font-mono">
            {pendingDelete.run_id}
            <span className="ml-2 text-gray-400">
              · {pendingDelete.golden_set_version} · {new Date(pendingDelete.started_at).toLocaleString()}
            </span>
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}

function RunRow({
  run,
  prevPassRate,
  onClick,
  onDelete,
}: {
  run: EvalRun;
  prevPassRate: number | null;
  onClick: () => void;
  onDelete: () => void;
}) {
  const passRate = run.pass_rate * 100;
  const delta = prevPassRate !== null ? run.pass_rate - prevPassRate : null;
  const isRunning = run.status === "running";

  return (
    <tr
      className="hover:bg-gray-50 cursor-pointer group"
      onClick={onClick}
    >
      <td className="px-5 py-3 font-mono text-xs text-gray-500">{run.run_id.slice(0, 12)}...</td>
      <td className="px-5 py-3">
        <span className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full">
          {run.golden_set_version}
        </span>
      </td>
      <td className="px-5 py-3 text-gray-600 text-xs">{run.rag_version}</td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-2">
          <PassRateBar rate={run.pass_rate} />
          <span className={cn(
            "font-semibold text-sm",
            passRate >= 80 ? "text-green-700" : passRate >= 60 ? "text-amber-700" : "text-red-700"
          )}>
            {passRate.toFixed(1)}%
          </span>
          {delta !== null && (
            <DeltaChip delta={delta} />
          )}
        </div>
      </td>
      <td className="px-5 py-3 text-gray-600 text-xs">
        {run.passed_cases}/{run.total_cases}
      </td>
      <td className="px-5 py-3">
        {run.avg_chunk_rank != null ? (
          <span className={cn(
            "font-mono text-xs font-semibold",
            run.avg_chunk_rank <= 10 ? "text-green-700" :
            run.avg_chunk_rank <= 30 ? "text-amber-700" : "text-red-700"
          )}>
            #{run.avg_chunk_rank.toFixed(1)}
          </span>
        ) : (
          <span className="text-xs text-gray-300">—</span>
        )}
      </td>
      <td className="px-5 py-3">
        <StatusBadge status={run.status} />
      </td>
      <td className="px-5 py-3 text-gray-400 text-xs">
        {new Date(run.started_at).toLocaleDateString()}
      </td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-1.5 justify-end">
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            disabled={isRunning}
            title={isRunning ? "Stop the run before deleting" : "Delete run"}
            className={cn(
              "p-1 rounded transition-opacity",
              isRunning
                ? "text-gray-300 cursor-not-allowed opacity-100"
                : "text-gray-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 focus:opacity-100"
            )}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <ChevronRight className="w-4 h-4 text-gray-300" />
        </div>
      </td>
    </tr>
  );
}

function PassRateBar({ rate }: { rate: number }) {
  return (
    <div className="w-16 bg-gray-100 rounded-full h-1.5 overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full",
          rate >= 0.8 ? "bg-green-500" : rate >= 0.6 ? "bg-amber-500" : "bg-red-500"
        )}
        style={{ width: `${rate * 100}%` }}
      />
    </div>
  );
}

function DeltaChip({ delta }: { delta: number }) {
  const pct = (delta * 100).toFixed(1);
  if (Math.abs(delta) < 0.001) {
    return <Minus className="w-3 h-3 text-gray-400" />;
  }
  return (
    <span className={cn(
      "flex items-center gap-0.5 text-xs font-medium",
      delta > 0 ? "text-green-600" : "text-red-600"
    )}>
      {delta > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {delta > 0 ? "+" : ""}{pct}%
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    complete: "bg-green-100 text-green-700",
    running: "bg-violet-100 text-violet-700",
    failed: "bg-red-100 text-red-600",
  };
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded-full", colors[status] ?? "bg-gray-100 text-gray-600")}>
      {status}
    </span>
  );
}

function StatCard({
  label,
  value,
  sub,
  trend,
}: {
  label: string;
  value: string;
  sub: string;
  trend?: number | null;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <p className="text-xs font-medium text-gray-500 mb-1">{label}</p>
      <div className="flex items-end gap-2">
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {trend != null && Math.abs(trend) >= 0.001 && (
          <span className={cn(
            "text-sm font-medium mb-0.5",
            trend > 0 ? "text-green-600" : "text-red-600"
          )}>
            {trend > 0 ? "+" : ""}{(trend * 100).toFixed(1)}%
          </span>
        )}
      </div>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}
