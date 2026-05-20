import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { resultsApi, queryApi } from "@/lib/api";
import type { EvalResult, QueryResponse, ChunkSignal } from "@/lib/api";
import {
  ArrowLeft, ChevronDown, ChevronRight, CheckCircle, XCircle,
  ShieldAlert, AlertTriangle, Activity, Gauge, Copy, Check,
  Play, RotateCcw, Loader2, Download, FileWarning, X, Trash2,
  Code2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import InsightsPanel from "@/components/InsightsPanel";
import TrendStrip from "@/components/TrendStrip";
import ConfirmDialog from "@/components/ConfirmDialog";

// ── Metric definitions ─────────────────────────────────────────────────────────
const RUBRIC_METRICS = [
  {
    key: "groundedness", label: "Groundedness", max: 5,
    info: "Measures whether the answer is factually supported by retrieved documents. Score 5 = fully grounded; Score 1 = answer contains facts not in any retrieved document (hallucination).",
  },
  {
    key: "query_relevance", label: "Query Relevance", max: 5,
    info: "Measures how relevant the RAG response is to the original question. Score 5 = directly answers the question; Score 1 = unrelated content returned.",
  },
  {
    key: "ground_truth_relevance", label: "Ground Truth Relevance", max: 5,
    info: "Compares the model's answer to the expected (golden) answer. Score 5 = answer matches the ground truth closely; Score 1 = completely different content.",
  },
  {
    key: "coherence", label: "Coherence", max: 5,
    info: "Evaluates whether the response is logically structured and easy to follow. Score 5 = well-organized, clear flow; Score 1 = incoherent or contradictory.",
  },
  {
    key: "fluency", label: "Fluency", max: 5,
    info: "Measures the grammatical quality and readability of the response. Score 5 = fluent and natural language; Score 1 = poor grammar or incomprehensible text.",
  },
  {
    key: "completeness", label: "Completeness", max: 5,
    info: "Assesses how thoroughly the response covers all aspects of the question. Score 5 = fully complete; Score 1 = critical parts of the question are unanswered.",
  },
  {
    key: "paraphrasing", label: "Paraphrasing", max: 5,
    info: "Measures whether the response is a meaningful synthesis vs. a verbatim copy from source. Score 5 = natural paraphrase; Score 1 = direct copy-paste without synthesis.",
  },
  {
    key: "gpt_similarity", label: "GPT Similarity", max: 100,
    info: "Embedding-based semantic similarity between the generated answer and the ground truth answer. Score 100 = identical meaning; Score 0 = completely unrelated.",
  },
] as const;

const SAFETY_FLAGS = [
  { key: "toxicity_detected",      label: "Toxicity",     icon: AlertTriangle },
  { key: "bias_detected",          label: "Bias",         icon: ShieldAlert },
  { key: "banned_topic_violation", label: "Banned Topic", icon: ShieldAlert },
] as const;

const FAILURE_COLORS: Record<string, string> = {
  none:           "bg-green-100 text-green-700",
  hallucination:  "bg-red-100 text-red-700",
  retrieval_miss: "bg-orange-100 text-orange-700",
  off_topic:      "bg-purple-100 text-purple-700",
  incomplete:     "bg-blue-100 text-blue-700",
  toxic:          "bg-red-200 text-red-900",
  biased:         "bg-pink-100 text-pink-700",
  banned_topic:   "bg-amber-100 text-amber-800",
};

const QTYPE_COLORS: Record<string, string> = {
  factual:     "bg-blue-50 text-blue-700",
  multi_hop:   "bg-indigo-50 text-indigo-700",
  comparative: "bg-teal-50 text-teal-700",
  boundary:    "bg-amber-50 text-amber-700",
  follow_up:   "bg-violet-50 text-violet-700",
};

const CASE_COLORS: Record<number, string> = {
  1: "bg-gray-100 text-gray-700 border-gray-200",
  2: "bg-sky-50 text-sky-700 border-sky-200",
  3: "bg-emerald-50 text-emerald-700 border-emerald-200",
  4: "bg-violet-50 text-violet-700 border-violet-200",
};

export default function RunDetailPage() {
  const { appId, runId } = useParams<{ appId: string; runId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "pass" | "fail">("all");
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => resultsApi.delete(appId!, runId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["eval-runs", appId] });
      qc.removeQueries({ queryKey: ["eval-results", appId, runId] });
      navigate(`/apps/${appId}/results`);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail
        ?? (err as Error)?.message
        ?? "Failed to delete run.";
      setDeleteError(msg);
    },
  });

  const handleExport = async () => {
    if (!appId || !runId) return;
    setIsExporting(true);
    setExportError(null);
    try {
      const { api } = await import("@/lib/api");
      const response = await api.get(
        `/apps/${appId}/results/${runId}/export`,
        { responseType: "blob" },
      );
      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      a.href = url;
      a.download = `eval-${runId.slice(0, 12)}-${today}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      // When responseType is "blob", axios wraps error bodies as Blobs too — parse them.
      const errResp = (e as { response?: { data?: unknown } })?.response;
      let detail: string | null = null;
      if (errResp?.data instanceof Blob) {
        try {
          const text = await errResp.data.text();
          detail = JSON.parse(text)?.detail ?? null;
        } catch { /* ignore */ }
      } else if (typeof (errResp?.data as { detail?: string })?.detail === "string") {
        detail = (errResp?.data as { detail: string }).detail;
      }
      setExportError(detail || "Export failed — check backend logs.");
    } finally {
      setIsExporting(false);
    }
  };
  const [filterType, setFilterType] = useState<string>("all");
  const [filterFailure, setFilterFailure] = useState<string>("all");
  const [filterDocRetrieved, setFilterDocRetrieved] = useState<string>("all");
  const [tcIdFilter, setTcIdFilter] = useState<string[] | null>(null);
  const [tcIdFilterLabel, setTcIdFilterLabel] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const handleApplyRuleFilter = (payload: {
    failure_category?: string;
    question_type?: string;
    tc_ids?: string[];
  }) => {
    if (payload.failure_category) {
      setFilterFailure(payload.failure_category);
      setFilter("fail");
      setTcIdFilter(null);
      setTcIdFilterLabel(null);
    }
    if (payload.question_type) {
      setFilterType(payload.question_type);
      setTcIdFilter(null);
      setTcIdFilterLabel(null);
    }
    if (payload.tc_ids && payload.tc_ids.length > 0) {
      setTcIdFilter(payload.tc_ids);
      setTcIdFilterLabel(`${payload.tc_ids.length} flagged case${payload.tc_ids.length !== 1 ? "s" : ""}`);
      setFilter("all");
      setFilterType("all");
      setFilterFailure("all");
      setFilterDocRetrieved("all");
    }
    setTimeout(() => {
      document.getElementById("results-list-anchor")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const clearTcIdFilter = () => {
    setTcIdFilter(null);
    setTcIdFilterLabel(null);
  };

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["eval-results", appId, runId],
    queryFn: () => resultsApi.getResults(appId!, runId!),
    enabled: !!appId && !!runId,
  });

  const passCount = results.filter((r) => r.passed).length;
  const failCount = results.length - passCount;
  const passRate = results.length > 0 ? passCount / results.length : 0;

  const avgChunkRank = useMemo(() => {
    const ranks = results
      .map((r) => r.scores?.["chunk_rank"])
      .filter((v): v is number => typeof v === "number");
    return ranks.length ? Math.round((ranks.reduce((a, b) => a + b, 0) / ranks.length) * 10) / 10 : null;
  }, [results]);

  // ── Chunk-lifecycle accuracies ───────────────────────────────────────────
  // Each test case with a reference doc has, at most, one "matched chunk"
  // (the first chunk whose fields satisfy the test case's match spec).
  // Kore.ai tags every chunk with three boolean flags telling us how far the
  // chunk made it through the answer pipeline: was it qualified by retrieval
  // scoring, was it sent to the LLM, was it used in the final answer.
  // Compute the run-level percentages from those per-row flags.
  const lifecycleStats = useMemo(() => {
    const isBool = (v: unknown): v is boolean => typeof v === "boolean";
    const rowsWithMatchedChunk = results.filter((r) =>
      isBool(r.scores?.matched_chunk_qualified) ||
      isBool(r.scores?.matched_chunk_sent_to_llm) ||
      isBool(r.scores?.matched_chunk_used_in_answer)
    );
    const denom = rowsWithMatchedChunk.length;
    const countTrue = (key: string) =>
      rowsWithMatchedChunk.filter((r) => r.scores?.[key] === true).length;
    const qualified = countTrue("matched_chunk_qualified");
    const sentToLlm = countTrue("matched_chunk_sent_to_llm");
    const usedInAnswer = countTrue("matched_chunk_used_in_answer");
    const rate = (n: number) => (denom > 0 ? n / denom : null);
    return {
      denom,
      qualified,
      sentToLlm,
      usedInAnswer,
      retrievalAccuracy: rate(qualified),
      sentToLlmAccuracy: rate(sentToLlm),
      answerGenAccuracy: rate(usedInAnswer),
    };
  }, [results]);

  const questionTypes = Array.from(new Set(results.map((r) => r.question_type).filter(Boolean)));

  const metricAverages = useMemo(() => RUBRIC_METRICS.map((m) => {
    const values = results
      .map((r) => r.scores?.[m.key])
      .filter((v) => typeof v === "number") as number[];
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
    return { ...m, avg, count: values.length };
  }), [results]);

  const passByType = useMemo(() => {
    const grouped: Record<string, { total: number; passed: number }> = {};
    for (const r of results) {
      const t = r.question_type || "unknown";
      if (!grouped[t]) grouped[t] = { total: 0, passed: 0 };
      grouped[t].total++;
      if (r.passed) grouped[t].passed++;
    }
    return Object.entries(grouped).map(([type, { total, passed }]) => ({
      type, total, passed, rate: total > 0 ? passed / total : 0,
    })).sort((a, b) => b.total - a.total);
  }, [results]);

  const latencyStats = useMemo(() => {
    const llm = results.map((r) => r.latency_llm_ms).filter((v): v is number => typeof v === "number").sort((a, b) => a - b);
    const retr = results.map((r) => r.latency_retrieval_ms).filter((v): v is number => typeof v === "number").sort((a, b) => a - b);
    const p = (arr: number[], q: number) => arr.length ? arr[Math.floor(arr.length * q)] : 0;
    const avg = (arr: number[]) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    return {
      llm: { avg: avg(llm), p50: p(llm, 0.5), p95: p(llm, 0.95) },
      retr: { avg: avg(retr), p50: p(retr, 0.5), p95: p(retr, 0.95) },
    };
  }, [results]);

  const filtered = results.filter((r) => {
    if (tcIdFilter && !tcIdFilter.includes(r.tc_id)) return false;
    if (filter === "pass" && !r.passed) return false;
    if (filter === "fail" && r.passed) return false;
    if (filterType !== "all" && r.question_type !== filterType) return false;
    if (filterFailure !== "all" && (r.failure_category ?? "none") !== filterFailure) return false;
    if (filterDocRetrieved === "yes" && !r.doc_retrieved) return false;
    if (filterDocRetrieved === "no" && r.doc_retrieved) return false;
    return true;
  });

  const failureBreakdown = results.reduce<Record<string, number>>((acc, r) => {
    const cat = r.failure_category ?? "none";
    acc[cat] = (acc[cat] ?? 0) + 1;
    return acc;
  }, {});

  if (isLoading) {
    return <div className="text-center py-16 text-gray-400">Loading results...</div>;
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        No results found for this run.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/apps/${appId}/results`)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="w-4 h-4" />
          Results
        </button>
        <span className="text-gray-300">/</span>
        <span className="text-sm font-mono text-gray-600">{runId?.slice(0, 16)}...</span>

        <div className="ml-auto flex items-center gap-2">
          {exportError && (
            <span className="flex items-center gap-1 text-xs text-red-600">
              <FileWarning className="w-3.5 h-3.5 shrink-0" />
              {exportError}
            </span>
          )}
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isExporting
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Exporting...</>
              : <><Download className="w-3.5 h-3.5" /> Download Excel</>
            }
          </button>
          <button
            onClick={() => { setDeleteError(null); setShowDeleteConfirm(true); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-gray-200 rounded-lg text-red-600 hover:bg-red-50 hover:border-red-300 transition-colors"
            title="Delete this run"
          >
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete this evaluation run?"
        description={
          <>
            This permanently removes the run and all <strong>{results.length}</strong>{" "}
            associated result rows, plus any cached diagnostics and AI insights.
            This action cannot be undone.
          </>
        }
        confirmLabel="Delete run"
        loading={deleteMutation.isPending}
        error={deleteError}
        onCancel={() => {
          if (deleteMutation.isPending) return;
          setShowDeleteConfirm(false);
          setDeleteError(null);
        }}
        onConfirm={() => deleteMutation.mutate()}
      >
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600 font-mono">
          {runId}
        </div>
      </ConfirmDialog>

      {/* ── Top stats ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <StatCard label="Total" value={String(results.length)} />
        <StatCard label="Passed" value={String(passCount)} color="green" />
        <StatCard label="Failed" value={String(failCount)} color="red" />
        <StatCard
          label="Pass Rate"
          value={`${(passRate * 100).toFixed(1)}%`}
          color={passRate >= 0.8 ? "green" : passRate >= 0.6 ? "amber" : "red"}
        />
        <StatCard
          label="Avg Chunk Rank"
          value={avgChunkRank != null ? `#${avgChunkRank}` : "—"}
          color={avgChunkRank != null ? (avgChunkRank <= 10 ? "green" : avgChunkRank <= 30 ? "amber" : "red") : undefined}
        />
      </div>

      {/* ── Chunk pipeline accuracy ────────────────────────────────── */}
      {lifecycleStats.denom > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">Chunk Pipeline Accuracy</h3>
            <span className="text-xs text-gray-400">
              {lifecycleStats.denom} test case{lifecycleStats.denom === 1 ? "" : "s"} with a matched chunk
            </span>
          </div>
          <p className="text-xs text-gray-500 mb-4 leading-relaxed">
            How far did the expected document's chunk make it down Kore.ai's pipeline? Each stage is a stricter filter — qualified ⊇ sent to LLM ⊇ used in answer.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <PipelineStatCard
              stage="Retrieval"
              description="Chunk passed Kore.ai's retrieval / shortlist threshold (chunkQualified=true)"
              count={lifecycleStats.qualified}
              denom={lifecycleStats.denom}
              rate={lifecycleStats.retrievalAccuracy}
            />
            <PipelineStatCard
              stage="Sent to LLM"
              description="Chunk was included in the LLM's context for answer generation (sentToLLM=true)"
              count={lifecycleStats.sentToLlm}
              denom={lifecycleStats.denom}
              rate={lifecycleStats.sentToLlmAccuracy}
            />
            <PipelineStatCard
              stage="Answer generation"
              description="Chunk was actually cited / used in the final answer (usedInAnswer=true)"
              count={lifecycleStats.usedInAnswer}
              denom={lifecycleStats.denom}
              rate={lifecycleStats.answerGenAccuracy}
            />
          </div>
        </div>
      )}

      {/* ── Phase 2: Trend strip (vs previous run) ───────────────── */}
      <TrendStrip appId={appId!} runId={runId!} />

      {/* ── Phase 2: Insights panel (funnel + recommendations) ──── */}
      <InsightsPanel appId={appId!} runId={runId!} onApplyRuleFilter={handleApplyRuleFilter} />

      {/* ── Metrics + Latency ────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex flex-col lg:flex-row lg:gap-8 gap-5">

          {/* Quality metrics */}
          {metricAverages.some((m) => m.count > 0) && (
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-3">
                <Gauge className="w-4 h-4 text-violet-500" />
                <h3 className="text-sm font-semibold text-gray-900">Average Quality Metrics</h3>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {metricAverages.filter((m) => m.count > 0).map((m) => {
                  const pct = (m.avg / m.max) * 100;
                  const color = pct >= 80 ? "text-green-700 bg-green-50 border-green-200"
                    : pct >= 60 ? "text-amber-700 bg-amber-50 border-amber-200"
                    : "text-red-700 bg-red-50 border-red-200";
                  return (
                    <MetricChip key={m.key} label={m.label} avg={m.avg} max={m.max} color={color} info={m.info} />
                  );
                })}
              </div>
            </div>
          )}

          {/* Divider */}
          {metricAverages.some((m) => m.count > 0) && (
            <div className="hidden lg:block w-px bg-gray-100 shrink-0" />
          )}

          {/* Latency */}
          <div className="shrink-0">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-blue-500" />
              <h3 className="text-sm font-semibold text-gray-900">Latency</h3>
            </div>
            <table className="text-xs border-separate border-spacing-x-5 border-spacing-y-1 -ml-5">
              <thead>
                <tr>
                  <th />
                  <th className="text-left font-medium text-gray-500 pb-1">LLM Response</th>
                  <th className="text-left font-medium text-gray-500 pb-1">Retrieval</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "Avg", llm: latencyStats.llm.avg, retr: latencyStats.retr.avg },
                  { label: "p50", llm: latencyStats.llm.p50, retr: latencyStats.retr.p50 },
                  { label: "p95", llm: latencyStats.llm.p95, retr: latencyStats.retr.p95 },
                ].map(({ label, llm, retr }) => (
                  <tr key={label}>
                    <td className="text-gray-400">{label}</td>
                    <td className="font-mono text-gray-700">{(llm / 1000).toFixed(2)}s</td>
                    <td className="font-mono text-gray-700">{(retr / 1000).toFixed(2)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      </div>

      {/* ── Pass rate by question type ─────────────────────────── */}
      {passByType.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Pass Rate by Question Type</h3>
          <div className="space-y-2.5">
            {passByType.map(({ type, total, passed, rate }) => (
              <div key={type} className="flex items-center gap-3">
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded-full w-28 text-center font-medium shrink-0",
                  QTYPE_COLORS[type] ?? "bg-gray-100 text-gray-600"
                )}>{type}</span>
                <div className="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden relative">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      rate >= 0.8 ? "bg-green-500" : rate >= 0.6 ? "bg-amber-500" : "bg-red-500"
                    )}
                    style={{ width: `${rate * 100}%` }}
                  />
                  <span className="absolute inset-0 flex items-center justify-end pr-2 text-xs font-medium text-gray-700">
                    {passed}/{total} · {(rate * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Failure breakdown ──────────────────────────────────── */}
      {Object.keys(failureBreakdown).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Failure Categories</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(failureBreakdown)
              .sort((a, b) => b[1] - a[1])
              .map(([cat, count]) => (
                <span
                  key={cat}
                  className={cn("text-xs px-3 py-1 rounded-full", FAILURE_COLORS[cat] ?? "bg-gray-100 text-gray-600")}
                >
                  {cat}: {count}
                </span>
              ))}
          </div>
        </div>
      )}

      {/* ── Filters ───────────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Filters</p>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Pass/Fail */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
            {(["all", "pass", "fail"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "px-3 py-1.5 capitalize",
                  filter === f ? "bg-violet-600 text-white" : "text-gray-600 hover:bg-gray-50"
                )}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Question type */}
          {questionTypes.length > 0 && (
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All types</option>
              {questionTypes.map((t) => (
                <option key={t} value={t!}>{t}</option>
              ))}
            </select>
          )}

          {/* Failure category */}
          {Object.keys(failureBreakdown).some((k) => k !== "none") && (
            <select
              value={filterFailure}
              onChange={(e) => setFilterFailure(e.target.value)}
              className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="all">All failures</option>
              {Object.keys(failureBreakdown)
                .sort()
                .map((cat) => (
                  <option key={cat} value={cat}>{cat} ({failureBreakdown[cat]})</option>
                ))}
            </select>
          )}

          {/* Doc retrieved */}
          <select
            value={filterDocRetrieved}
            onChange={(e) => setFilterDocRetrieved(e.target.value)}
            className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            <option value="all">All (doc retrieved)</option>
            <option value="yes">Doc retrieved ✓</option>
            <option value="no">Doc not retrieved ✗</option>
          </select>

          {/* Active rule-filter chip */}
          {tcIdFilter && tcIdFilterLabel && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-violet-100 text-violet-800 inline-flex items-center gap-1.5 border border-violet-200">
              From insight: {tcIdFilterLabel}
              <button
                onClick={clearTcIdFilter}
                className="hover:text-violet-950"
                title="Clear insight filter"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          )}

          <span className="text-xs text-gray-400 ml-auto">{filtered.length} results</span>
        </div>
      </div>

      {/* ── Results list ─────────────────────────────────────── */}
      <div id="results-list-anchor" className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {/* Sticky count header */}
        <div className="sticky top-0 z-10 px-5 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-600">
            {filtered.length} question{filtered.length !== 1 ? "s" : ""}
          </span>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-green-600 font-medium">{filtered.filter((r) => r.passed).length} pass</span>
            <span className="text-red-500 font-medium">{filtered.filter((r) => !r.passed).length} fail</span>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">No results match the filter</div>
        ) : (
          <div className="divide-y divide-gray-100 max-h-[680px] overflow-y-auto">
            {filtered.map((result) => (
              <ResultRow
                key={result.tc_id}
                result={result}
                appId={appId!}
                isExpanded={expanded === result.tc_id}
                onToggle={() => setExpanded(expanded === result.tc_id ? null : result.tc_id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MetricChip({ label, avg, max, color, info }: {
  label: string; avg: number; max: number; color: string; info?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div
      className="relative"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <div className={cn("flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg border text-xs cursor-default w-full", color)}>
        <span className="text-gray-500 font-medium truncate">{label}</span>
        <span className="shrink-0 font-mono font-bold">{avg.toFixed(1)}<span className="text-gray-400 font-normal"> /{max}</span></span>
      </div>
      {show && info && (
        <div className="absolute bottom-full left-0 mb-2 w-72 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl leading-relaxed z-50 pointer-events-none">
          <p className="font-semibold text-gray-200 mb-1">{label}</p>
          {info}
          <div className="absolute top-full left-4 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-900" />
        </div>
      )}
    </div>
  );
}

type DocDisplayMode = "id" | "title" | "url";

function ResultRow({
  result,
  appId,
  isExpanded,
  onToggle,
}: {
  result: EvalResult;
  appId: string;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const passed = result.passed;
  const hasSafety = result.scores?.toxicity_detected || result.scores?.bias_detected || result.scores?.banned_topic_violation;
  const isExtract = (result.scores?.answer_mode as unknown as string) === "extract_only";

  const [docMode, setDocMode] = useState<DocDisplayMode>("id");
  const labelMap = result.doc_label_map ?? {};
  const hasLabels = Object.values(labelMap).some((l) => l.title);
  const hasUrls = Object.values(labelMap).some((l) => l.url);

  const getDocLabel = (id: string): string => {
    if (docMode === "title") return labelMap[id]?.title || id;
    if (docMode === "url") return labelMap[id]?.url || id;
    return id;
  };

  return (
    <div>
      <div
        className={cn(
          "flex items-start gap-3 px-5 py-4 cursor-pointer transition-colors",
          isExpanded ? "bg-violet-50/40" : "hover:bg-gray-50"
        )}
        onClick={onToggle}
      >
        {/* Pass/Fail icon */}
        <div className="mt-0.5 shrink-0">
          {passed ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
        </div>

        {/* Question + badge row */}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-800 font-medium leading-snug line-clamp-2">
            {result.question}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            {/* Verdict badge */}
            <span className={cn(
              "text-[11px] font-semibold px-2 py-0.5 rounded-full",
              passed ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            )}>
              {passed ? "Pass" : "Fail"}
            </span>

            {result.case_id && (
              <span
                title={result.verdict_source || ""}
                className={cn(
                  "text-[10px] font-semibold px-1.5 py-0.5 rounded border",
                  CASE_COLORS[result.case_id] ?? "bg-gray-100 text-gray-600 border-gray-200"
                )}
              >
                Case {result.case_id}
              </span>
            )}

            {result.question_type && (
              <span className={cn(
                "text-[11px] px-2 py-0.5 rounded-full",
                QTYPE_COLORS[result.question_type] ?? "bg-gray-100 text-gray-600"
              )}>
                {result.question_type}
              </span>
            )}

            {result.failure_category && result.failure_category !== "none" && (
              <span className={cn(
                "text-[11px] px-2 py-0.5 rounded-full",
                FAILURE_COLORS[result.failure_category] ?? "bg-gray-100 text-gray-600"
              )}>
                {result.failure_category}
              </span>
            )}

            {hasSafety && (
              <span className="text-[11px] px-2 py-0.5 bg-red-100 text-red-700 rounded-full flex items-center gap-1">
                <ShieldAlert className="w-3 h-3" /> safety
              </span>
            )}

            {/* Doc retrieved signal */}
            <span className={cn(
              "text-[11px] px-2 py-0.5 rounded-full",
              result.doc_retrieved ? "bg-teal-50 text-teal-700" : "bg-orange-50 text-orange-700"
            )}>
              {result.doc_retrieved ? "doc ✓" : "doc ✗"}
            </span>

            {result.latency_llm_ms && (
              <span className="text-[11px] text-gray-400 font-mono">
                {Math.round(result.latency_llm_ms)}ms
              </span>
            )}
          </div>
        </div>

        {/* Expand chevron */}
        <div className="shrink-0 mt-1">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-violet-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-300" />
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="px-5 pb-5 pt-3 bg-gray-50/80 border-t border-violet-100">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
            {/* Left column */}
            <div className="space-y-3">
              <Section title="Question">{result.question}</Section>
              <Section title="Expected Answer">
                {result.expected_answer ?? <span className="italic text-gray-400">— (not provided)</span>}
              </Section>

              {/* RAG Response — prominent answer box */}
              <div>
                <p className="font-medium text-gray-600 mb-1.5 flex items-center gap-2">
                  RAG Response
                  {isExtract
                    ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium">📄 Extract Only</span>
                    : <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">⚡ Answer Generation</span>
                  }
                </p>
                {result.rag_response ? (
                  <div className={cn(
                    "p-3 rounded-lg border text-xs leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto",
                    passed
                      ? "bg-green-50 border-green-200 text-green-900"
                      : "bg-red-50 border-red-200 text-red-900"
                  )}>
                    {result.rag_response}
                  </div>
                ) : (
                  <div className="p-3 rounded-lg border border-gray-200 bg-white text-gray-400 italic text-xs">
                    No answer was returned by the RAG system during evaluation.
                    Use the Test Query panel below to run the query live.
                  </div>
                )}
              </div>
            </div>

            {/* Right column */}
            <div className="space-y-3">
              {/* Verdict source — tells user HOW pass/fail was derived */}
              {result.verdict_source && (
                <div className={cn(
                  "rounded-lg border px-3 py-2 text-xs flex items-center gap-2",
                  passed
                    ? "bg-green-50 border-green-200 text-green-800"
                    : result.verdict
                      ? "bg-red-50 border-red-200 text-red-800"
                      : "bg-gray-50 border-gray-200 text-gray-700"
                )}>
                  <span className="font-semibold uppercase tracking-wide text-[10px]">Verdict source</span>
                  <span className="font-medium">{result.verdict_source}</span>
                </div>
              )}

              {/* Retrieval / Similarity metrics — Cases 2/3/4 */}
              <RetrievalMetricsBlock result={result} />

              {/* Chunk rank — first so retrieval quality is immediately visible */}
              <ChunkRankBadge
                chunkRank={typeof result.scores?.["chunk_rank"] === "number" ? result.scores["chunk_rank"] as number : null}
                hasReference={result.reference_doc_ids.length > 0}
              />

              {/* Judge Feedback — only when judge actually ran */}
              {result.judge_rationale && (
                <div className="rounded-lg border border-violet-100 bg-violet-50 p-3">
                  <p className="text-xs font-semibold text-violet-800 mb-1.5 flex items-center gap-1.5">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Judge Feedback
                  </p>
                  <p className="text-xs text-violet-900 leading-relaxed">{result.judge_rationale}</p>
                </div>
              )}

              {/* Quality Scores — only when judge produced rubric scores */}
              {(() => {
                const rubricScores = RUBRIC_METRICS.filter(
                  (m) => typeof result.scores?.[m.key] === "number"
                );
                if (rubricScores.length === 0) return null;
                return (
                  <div>
                    <p className="font-medium text-gray-600 mb-2">Quality Scores</p>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                      {rubricScores.map((m) => (
                        <div key={m.key} className="flex items-center justify-between">
                          <span className="text-gray-500">{m.label}</span>
                          <ScoreValue value={result.scores![m.key] as number} max={m.max} />
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              <div>
                <p className="font-medium text-gray-600 mb-1.5">Safety Flags</p>
                <div className="flex flex-wrap gap-2">
                  {SAFETY_FLAGS.map((f) => {
                    const flagged = result.scores?.[f.key] === true;
                    return (
                      <span
                        key={f.key}
                        className={cn(
                          "text-xs px-2 py-0.5 rounded-full inline-flex items-center gap-1",
                          flagged ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-400"
                        )}
                      >
                        {flagged ? "⚠" : "✓"} {f.label}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Document display — with mode toggle */}
              {(result.reference_doc_ids.length > 0 || result.retrieved_doc_ids.length > 0) && (
                <div className="space-y-2">
                  {/* Toggle: only show when labels are available; applies to Retrieved Docs only */}
                  {hasLabels && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">Retrieved docs — show as</span>
                      <div className="flex rounded border border-gray-200 overflow-hidden text-[11px]">
                        {(["id", "title", ...(hasUrls ? ["url"] : [])] as DocDisplayMode[]).map((mode) => {
                          const labels: Record<DocDisplayMode, string> = { id: "Doc ID", title: "Title", url: "URL" };
                          return (
                            <button
                              key={mode}
                              onClick={() => setDocMode(mode)}
                              className={cn(
                                "px-2 py-0.5 transition-colors",
                                docMode === mode
                                  ? "bg-violet-600 text-white"
                                  : "text-gray-500 hover:bg-gray-50"
                              )}
                            >
                              {labels[mode]}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {result.reference_doc_ids.length > 0 && (
                    <div>
                      <p className="font-medium text-gray-600 mb-1.5">Expected Document</p>
                      <div className="flex flex-wrap gap-1">
                        {result.reference_doc_ids.map((id) => {
                          const hit = result.retrieved_doc_ids.includes(id);
                          return (
                            <span
                              key={id}
                              className={cn(
                                "px-2 py-0.5 rounded font-mono text-xs inline-flex items-center gap-1",
                                hit ? "bg-green-100 text-green-700" : "bg-red-50 text-red-600"
                              )}
                            >
                              {hit ? "✓" : "✗"} {id}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {result.retrieved_doc_ids.length > 0 && (
                    <div>
                      <p className="font-medium text-gray-600 mb-1.5">
                        Retrieved Docs
                        <span className={cn(
                          "ml-1.5 text-xs font-normal",
                          result.doc_retrieved ? "text-green-600" : "text-red-500"
                        )}>
                          ({result.doc_retrieved ? "✓ match" : "✗ miss"})
                        </span>
                        {result.retrieved_doc_ids.length > 20 && (
                          <span className="ml-1.5 text-xs text-gray-400">
                            — top 20 of {result.retrieved_doc_ids.length}
                          </span>
                        )}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {result.retrieved_doc_ids.slice(0, 20).map((id) => {
                          const isExpected = result.reference_doc_ids.includes(id);
                          const label = getDocLabel(id);
                          return (
                            <span
                              key={id}
                              title={docMode !== "id" ? id : undefined}
                              className={cn(
                                "px-2 py-0.5 rounded text-xs max-w-[280px] truncate",
                                docMode === "id" ? "font-mono" : "font-sans",
                                isExpected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                              )}
                            >
                              {label}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Search payload + response + live test — full width */}
          {((result.search_payload && Object.keys(result.search_payload).length > 0) ||
            (result.search_response && Object.keys(result.search_response).length > 0)) && (
            <SearchPayloadBlock
              payload={result.search_payload || undefined}
              response={result.search_response || undefined}
            />
          )}

          {/* Live test panel */}
          <LiveTestPanel
            appId={appId}
            question={result.question}
            defaultPayload={result.search_payload ?? null}
          />
        </div>
      )}
    </div>
  );
}

// ── Live Test Panel ────────────────────────────────────────────────────────────
type LiveTab = "answer" | "chunks" | "raw";

const DEFAULT_PAYLOAD_KEYS = {
  answerSearch: true,
  searchResults: true,
  includeChunksInResponse: true,
  maxNumOfChunks: 100,
};

function buildDefaultPayload(q: string, stored: Record<string, unknown> | null): string {
  const base = stored
    ? { ...stored, query: q }
    : { query: q, ...DEFAULT_PAYLOAD_KEYS };
  return JSON.stringify(base, null, 2);
}

function LiveTestPanel({
  appId,
  question,
  defaultPayload,
}: {
  appId: string;
  question: string;
  defaultPayload: Record<string, unknown> | null;
}) {
  const [open, setOpen] = useState(false);
  const [editedQuestion, setEditedQuestion] = useState(question);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<LiveTab>("answer");
  const [rawCopied, setRawCopied] = useState(false);

  // Payload editor state
  const [payloadOpen, setPayloadOpen] = useState(false);
  const [payloadJson, setPayloadJson] = useState(() => buildDefaultPayload(question, defaultPayload));
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [payloadCopied, setPayloadCopied] = useState(false);

  // Keep payload.query in sync with the question textarea
  const syncPayloadQuestion = (newQ: string) => {
    setPayloadJson((prev) => {
      try {
        const parsed = JSON.parse(prev);
        return JSON.stringify({ ...parsed, query: newQ }, null, 2);
      } catch {
        return prev; // if JSON is invalid, leave it as-is
      }
    });
  };

  const handleQuestionChange = (newQ: string) => {
    setEditedQuestion(newQ);
    syncPayloadQuestion(newQ);
  };

  const handleReset = () => {
    setEditedQuestion(question);
    setPayloadJson(buildDefaultPayload(question, defaultPayload));
    setPayloadError(null);
    setResult(null);
    setError(null);
  };

  const handlePayloadChange = (text: string) => {
    setPayloadJson(text);
    setPayloadError(null);
    // Also sync the question textarea if query field changed and JSON is valid
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed.query === "string" && parsed.query !== editedQuestion) {
        setEditedQuestion(parsed.query);
      }
    } catch { /* wait until valid */ }
  };

  const handleRun = async () => {
    if (!editedQuestion.trim()) return;

    // If payload editor is open, validate and parse the JSON
    let payloadOverride: Record<string, unknown> | null = null;
    if (payloadOpen) {
      try {
        payloadOverride = JSON.parse(payloadJson);
        setPayloadError(null);
      } catch (e) {
        setPayloadError(`Invalid JSON: ${(e as Error).message}`);
        return;
      }
    }

    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await queryApi.run(appId, {
        question: editedQuestion.trim(),
        payload_override: payloadOverride,
      });
      setResult(res);
      setActiveTab("answer");
    } catch (e: unknown) {
      const resp = (e as { response?: { status?: number; data?: { detail?: string } } })?.response;
      const status = resp?.status;
      const detail = resp?.data?.detail;
      setError(
        detail
          ? `${status ? `[${status}] ` : ""}${detail}`
          : "Query failed — check backend logs.",
      );
    } finally {
      setIsRunning(false);
    }
  };

  const handleCopyRaw = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setRawCopied(true);
      setTimeout(() => setRawCopied(false), 1500);
    } catch { /* ignore */ }
  };

  const handleCopyPayload = async () => {
    try {
      await navigator.clipboard.writeText(payloadJson);
      setPayloadCopied(true);
      setTimeout(() => setPayloadCopied(false), 1500);
    } catch { /* ignore */ }
  };

  // Check if payload has been modified from default
  const isPayloadModified = useMemo(() => {
    try {
      return payloadJson !== buildDefaultPayload(editedQuestion, defaultPayload);
    } catch {
      return true;
    }
  }, [payloadJson, editedQuestion, defaultPayload]);

  return (
    <div className="mt-4 border-t border-gray-200 pt-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs font-medium text-violet-700 hover:text-violet-900"
        >
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <Play className="w-3 h-3" />
          Test Query Live
          <span className="text-gray-400 font-normal ml-1">(edit &amp; run against RAG)</span>
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-3">
          {/* Editable question */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-gray-600">Query</label>
              {(editedQuestion !== question || isPayloadModified) && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
                >
                  <RotateCcw className="w-3 h-3" /> Reset all
                </button>
              )}
            </div>
            <textarea
              value={editedQuestion}
              onChange={(e) => handleQuestionChange(e.target.value)}
              rows={3}
              className="w-full text-xs p-2.5 border border-gray-200 rounded-lg bg-white resize-none focus:outline-none focus:ring-2 focus:ring-violet-500 font-sans"
            />
          </div>

          {/* ── Payload editor ────────────────────────────────────── */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-gray-50">
              <button
                onClick={() => setPayloadOpen((o) => !o)}
                className="flex items-center gap-1.5 text-xs font-medium text-gray-700 hover:text-gray-900"
              >
                {payloadOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                <Code2 className="w-3.5 h-3.5 text-gray-500" />
                Request Payload
                {isPayloadModified && (
                  <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                    modified
                  </span>
                )}
              </button>
              {payloadOpen && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setPayloadJson(buildDefaultPayload(editedQuestion, defaultPayload));
                      setPayloadError(null);
                    }}
                    className="text-[11px] text-gray-400 hover:text-gray-700"
                    title="Reset payload to default"
                  >
                    <RotateCcw className="w-3 h-3" />
                  </button>
                  <button
                    onClick={handleCopyPayload}
                    className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-800 px-2 py-0.5 rounded border border-gray-200 bg-white"
                  >
                    {payloadCopied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
                    {payloadCopied ? "Copied" : "Copy"}
                  </button>
                </div>
              )}
            </div>

            {payloadOpen && (
              <div>
                <textarea
                  value={payloadJson}
                  onChange={(e) => handlePayloadChange(e.target.value)}
                  rows={14}
                  spellCheck={false}
                  className={cn(
                    "w-full text-[11px] p-3 bg-gray-900 text-gray-100 font-mono resize-y focus:outline-none leading-relaxed",
                    payloadError ? "border-t-2 border-red-500" : ""
                  )}
                />
                {payloadError && (
                  <div className="px-3 py-1.5 bg-red-50 border-t border-red-200 text-xs text-red-700 font-mono">
                    {payloadError}
                  </div>
                )}
                <div className="px-3 py-1.5 bg-gray-50 border-t border-gray-200 text-[11px] text-gray-400">
                  Edit any field — will be sent as-is to Kore.ai. The <code className="text-gray-600">query</code> field stays in sync with the Query box above.
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRun}
              disabled={isRunning || !editedQuestion.trim() || !!payloadError}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRunning ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Running...</>
              ) : (
                <><Play className="w-3 h-3" /> Run Query</>
              )}
            </button>
            {payloadOpen && isPayloadModified && !payloadError && (
              <span className="text-[11px] text-amber-600 flex items-center gap-1">
                <Code2 className="w-3 h-3" /> Using custom payload
              </span>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-red-200 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border-b border-red-200">
                <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                <span className="text-xs font-semibold text-red-700">Request Failed</span>
              </div>
              <pre className="p-3 bg-white text-xs text-red-800 whitespace-pre-wrap break-all leading-relaxed max-h-40 overflow-y-auto font-mono">
                {error}
              </pre>
            </div>
          )}

          {/* Live response — Postman-style tabbed viewer */}
          {result && (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Status bar */}
              <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "text-[11px] font-semibold px-2 py-0.5 rounded-full",
                    result.is_valid_answer ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"
                  )}>
                    {result.is_valid_answer ? "200 OK" : "200 No Answer"}
                  </span>
                  <span className={cn(
                    "text-[11px] px-1.5 py-0.5 rounded-full font-medium",
                    result.answer_mode === "extract_only"
                      ? "bg-amber-50 text-amber-700"
                      : "bg-blue-50 text-blue-700"
                  )}>
                    {result.answer_mode === "extract_only" ? "Extract Only" : "Answer Generation"}
                  </span>
                </div>
                <div className="flex gap-3 text-[11px] text-gray-400">
                  {result.latency_llm_ms != null && (
                    <span>LLM <span className="font-mono text-gray-600">{Math.round(result.latency_llm_ms)}ms</span></span>
                  )}
                  {result.latency_retrieval_ms != null && (
                    <span>Retrieval <span className="font-mono text-gray-600">{Math.round(result.latency_retrieval_ms)}ms</span></span>
                  )}
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-gray-200 bg-white">
                {(["answer", "chunks", "raw"] as LiveTab[]).map((tab) => {
                  const labels: Record<LiveTab, string> = {
                    answer: "Answer",
                    chunks: `Chunks (${result.chunk_signals?.length ?? 0})`,
                    raw: "Raw Response",
                  };
                  return (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        "px-4 py-2 text-xs font-medium border-b-2 transition-colors",
                        activeTab === tab
                          ? "border-violet-500 text-violet-700 bg-violet-50/50"
                          : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                      )}
                    >
                      {labels[tab]}
                    </button>
                  );
                })}
              </div>

              {/* Tab content */}
              <div className="bg-white">
                {/* Answer tab */}
                {activeTab === "answer" && (
                  <div className="p-3 space-y-3">
                    {result.answer ? (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-900 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
                        {result.answer}
                      </div>
                    ) : (
                      <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-400 italic">
                        RAG returned no answer for this query.
                      </div>
                    )}

                    {result.cited_doc_ids.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 mb-1">
                          Cited Documents ({result.cited_doc_ids.length})
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {result.cited_doc_ids.map((id) => (
                            <span key={id} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-mono text-xs">
                              {id}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {result.result_doc_ids.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-600 mb-1">
                          All Result Documents ({result.result_doc_ids.length})
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {result.result_doc_ids.map((id) => (
                            <span key={id} className={cn(
                              "px-2 py-0.5 rounded font-mono text-xs",
                              result.cited_doc_ids.includes(id)
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-500"
                            )}>
                              {id}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Chunks tab */}
                {activeTab === "chunks" && (
                  <div className="max-h-96 overflow-y-auto">
                    {(result.chunk_signals?.length ?? 0) === 0 ? (
                      <div className="p-4 text-xs text-gray-400 italic text-center">No chunk signals returned.</div>
                    ) : (
                      <table className="w-full text-[11px]">
                        <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium text-gray-500">#</th>
                            <th className="text-left px-3 py-2 font-medium text-gray-500">Doc ID</th>
                            <th className="text-left px-3 py-2 font-medium text-gray-500">Title</th>
                            <th className="text-right px-3 py-2 font-medium text-gray-500">Score</th>
                            <th className="text-center px-3 py-2 font-medium text-gray-500">Qualified</th>
                            <th className="text-center px-3 py-2 font-medium text-gray-500">Sent to LLM</th>
                            <th className="text-center px-3 py-2 font-medium text-gray-500">Used in Answer</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {(result.chunk_signals as ChunkSignal[]).map((c, i) => (
                            <tr key={i} className={cn(
                              "hover:bg-gray-50",
                              c.usedInAnswer ? "bg-green-50/40" : ""
                            )}>
                              <td className="px-3 py-1.5 text-gray-400 font-mono">{i + 1}</td>
                              <td className="px-3 py-1.5 font-mono text-gray-600 max-w-[140px] truncate" title={c.docId ?? ""}>
                                {c.docId ?? "—"}
                              </td>
                              <td className="px-3 py-1.5 text-gray-600 max-w-[180px] truncate" title={c.recordTitle ?? ""}>
                                {c.recordTitle ?? "—"}
                              </td>
                              <td className="px-3 py-1.5 text-right font-mono text-gray-700">
                                {c.score != null ? c.score.toFixed(4) : "—"}
                              </td>
                              <td className="px-3 py-1.5 text-center">
                                <FlagDot value={c.chunkQualified} />
                              </td>
                              <td className="px-3 py-1.5 text-center">
                                <FlagDot value={c.sentToLLM} />
                              </td>
                              <td className="px-3 py-1.5 text-center">
                                <FlagDot value={c.usedInAnswer} highlight />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}

                {/* Raw Response tab */}
                {activeTab === "raw" && (
                  <CollapsibleJson
                    data={result.raw_response ?? {}}
                    copied={rawCopied}
                    onCopy={() => handleCopyRaw(JSON.stringify(result.raw_response ?? {}, null, 2))}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FlagDot({ value, highlight = false }: { value: boolean | null | undefined; highlight?: boolean }) {
  if (value === true) {
    return (
      <span className={cn(
        "inline-block w-2 h-2 rounded-full",
        highlight ? "bg-green-500" : "bg-teal-400"
      )} title="true" />
    );
  }
  if (value === false) {
    return <span className="inline-block w-2 h-2 rounded-full bg-gray-200" title="false" />;
  }
  return <span className="text-gray-300">—</span>;
}

// ── Collapsible JSON Tree ──────────────────────────────────────────────────────
function JsonNode({
  value,
  depth,
  maxInitialDepth,
  isLast,
}: {
  value: unknown;
  depth: number;
  maxInitialDepth: number;
  isLast?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(depth > maxInitialDepth);
  const comma = !isLast ? <span className="text-gray-500">,</span> : null;

  if (value === null) {
    return <span><span className="text-gray-400">null</span>{comma}</span>;
  }
  if (typeof value === "boolean") {
    return <span><span className="text-blue-300">{String(value)}</span>{comma}</span>;
  }
  if (typeof value === "number") {
    return <span><span className="text-yellow-300">{value}</span>{comma}</span>;
  }
  if (typeof value === "string") {
    return (
      <span>
        <span className="text-emerald-300 break-all">"{value}"</span>{comma}
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span><span className="text-gray-400">[]</span>{comma}</span>;
    return (
      <span>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-gray-500 hover:text-white mr-0.5 select-none leading-none"
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "▶" : "▼"}
        </button>
        <span className="text-gray-300">[</span>
        {collapsed ? (
          <>
            <button
              onClick={() => setCollapsed(false)}
              className="mx-1 text-[10px] text-gray-400 hover:text-gray-200 italic"
            >
              {value.length} {value.length === 1 ? "item" : "items"}
            </button>
            <span className="text-gray-300">]</span>{comma}
          </>
        ) : (
          <>
            <div className="ml-4 border-l border-gray-700 pl-2">
              {value.map((item, i) => (
                <div key={i}>
                  <JsonNode
                    value={item}
                    depth={depth + 1}
                    maxInitialDepth={maxInitialDepth}
                    isLast={i === value.length - 1}
                  />
                </div>
              ))}
            </div>
            <span className="text-gray-300">]</span>{comma}
          </>
        )}
      </span>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span><span className="text-gray-400">{"{}"}</span>{comma}</span>;
    return (
      <span>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-gray-500 hover:text-white mr-0.5 select-none leading-none"
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "▶" : "▼"}
        </button>
        <span className="text-gray-300">{"{"}</span>
        {collapsed ? (
          <>
            <button
              onClick={() => setCollapsed(false)}
              className="mx-1 text-[10px] text-gray-400 hover:text-gray-200 italic"
            >
              {entries.length} {entries.length === 1 ? "key" : "keys"}
            </button>
            <span className="text-gray-300">{"}"}</span>{comma}
          </>
        ) : (
          <>
            <div className="ml-4 border-l border-gray-700 pl-2">
              {entries.map(([k, v], i) => (
                <div key={k} className="flex flex-wrap gap-x-1 items-start">
                  <span className="text-sky-300 shrink-0">"{k}"</span>
                  <span className="text-gray-500 shrink-0">:</span>
                  <span className="min-w-0">
                    <JsonNode
                      value={v}
                      depth={depth + 1}
                      maxInitialDepth={maxInitialDepth}
                      isLast={i === entries.length - 1}
                    />
                  </span>
                </div>
              ))}
            </div>
            <span className="text-gray-300">{"}"}</span>{comma}
          </>
        )}
      </span>
    );
  }

  return <span className="text-gray-300">{String(value)}</span>;
}

function CollapsibleJson({
  data,
  copied,
  onCopy,
}: {
  data: unknown;
  copied: boolean;
  onCopy: () => void;
}) {
  const [viewKey, setViewKey] = useState(0);
  const [initDepth, setInitDepth] = useState(1);

  const expandAll  = () => { setInitDepth(999); setViewKey((k) => k + 1); };
  const collapseAll = () => { setInitDepth(-1);  setViewKey((k) => k + 1); };

  return (
    <div>
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900 border-b border-gray-700">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-gray-400 font-mono mr-1">application/json</span>
          <button
            onClick={expandAll}
            className="text-[11px] text-gray-400 hover:text-gray-100 px-1.5 py-0.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
          >
            Expand all
          </button>
          <button
            onClick={collapseAll}
            className="text-[11px] text-gray-400 hover:text-gray-100 px-1.5 py-0.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
          >
            Collapse all
          </button>
        </div>
        <button
          onClick={onCopy}
          className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-200 px-2 py-0.5 rounded border border-gray-600 bg-gray-800 transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div
        key={viewKey}
        className="p-3 bg-gray-900 text-[11px] font-mono leading-relaxed overflow-x-auto max-h-[520px] overflow-y-auto"
      >
        <JsonNode value={data} depth={0} maxInitialDepth={initDepth} isLast />
      </div>
    </div>
  );
}

function RetrievalMetricsBlock({ result }: { result: EvalResult }) {
  const rank = result.expected_doc_rank;
  const recall = result.recall_at_k || {};
  const sim = result.answer_similarity;
  const hasRank = result.case_id === 3 || result.case_id === 4;
  const hasSim  = result.case_id === 2 || result.case_id === 4;
  if (!hasRank && !hasSim) return null;

  const recallLevels = ["1", "3", "5", "10"];
  const hasAnyRecall = recallLevels.some((k) => k in recall);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
      <p className="text-xs font-semibold text-gray-700">Retrieval &amp; Similarity</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        {hasRank && (
          <div>
            <p className="text-gray-500 mb-0.5">Expected doc rank</p>
            <p className={cn(
              "font-mono font-semibold",
              rank == null ? "text-red-600" : rank <= 5 ? "text-green-700" : rank <= 10 ? "text-amber-700" : "text-red-700"
            )}>
              {rank == null ? "not found" : `#${rank}`}
            </p>
          </div>
        )}
        {hasSim && (
          <div>
            <p className="text-gray-500 mb-0.5">Answer similarity</p>
            <p className={cn(
              "font-mono font-semibold",
              sim == null ? "text-gray-400" : sim >= 0.8 ? "text-green-700" : sim >= 0.6 ? "text-amber-700" : "text-red-700"
            )}>
              {sim == null ? "—" : sim.toFixed(2)}
            </p>
          </div>
        )}
      </div>
      {hasRank && hasAnyRecall && (
        <div>
          <p className="text-[11px] text-gray-500 mb-1">Recall @ K</p>
          <div className="flex gap-1.5">
            {recallLevels.map((k) => {
              const v = recall[k];
              if (v === undefined) return null;
              return (
                <span
                  key={k}
                  className={cn(
                    "text-[10px] font-mono px-1.5 py-0.5 rounded border",
                    v === 1
                      ? "bg-green-50 border-green-200 text-green-700"
                      : "bg-gray-50 border-gray-200 text-gray-500"
                  )}
                >
                  @{k}: {v === 1 ? "✓" : "✗"}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function ChunkRankBadge({ chunkRank, hasReference }: { chunkRank: number | null; hasReference: boolean }) {
  if (!hasReference) return null;
  return (
    <div>
      <p className="font-medium text-gray-600 mb-1.5">Chunk Position (out of 100)</p>
      {chunkRank !== null ? (
        <span className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border",
          chunkRank <= 10
            ? "bg-green-50 border-green-200 text-green-800"
            : chunkRank <= 30
            ? "bg-amber-50 border-amber-200 text-amber-800"
            : "bg-red-50 border-red-200 text-red-800"
        )}>
          <span className="text-base leading-none">#</span>
          {chunkRank}
          <span className="font-normal text-gray-500">/ 100</span>
          <span className="ml-1 font-normal">
            {chunkRank <= 10 ? "— top 10%" : chunkRank <= 30 ? "— top 30%" : "— low rank"}
          </span>
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-red-100 border border-red-300 text-red-800">
          Not found in top 100 chunks
        </span>
      )}
    </div>
  );
}

function SearchPayloadBlock({
  payload, response,
}: {
  payload?: Record<string, unknown>;
  response?: Record<string, unknown>;
}) {
  const [open, setOpen] = useState(false);
  const hasPayload = payload && Object.keys(payload).length > 0;
  const hasResponse = response && Object.keys(response).length > 0;
  const [tab, setTab] = useState<"request" | "response">(
    hasPayload ? "request" : "response"
  );

  const metaFilters = (payload as { metaFilters?: unknown } | undefined)?.metaFilters;
  const customData = (payload as { customData?: { userContext?: { userId?: string } } } | undefined)?.customData;
  const userId = customData?.userContext?.userId;
  const filterCount = Array.isArray(metaFilters) ? metaFilters.length : 0;
  const responseBytes = useMemo(
    () => (response ? JSON.stringify(response).length : 0),
    [response],
  );

  return (
    <div className="mt-4 border-t border-gray-200 pt-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-700 hover:text-gray-900"
        >
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          Search Request &amp; Response
          <span className="text-gray-400 font-normal ml-1">
            ({hasPayload && `filters: ${filterCount}`}
            {userId && hasPayload ? `, racl: ${userId}` : userId ? `racl: ${userId}` : ""}
            {hasResponse && (hasPayload || userId) ? "; " : ""}
            {hasResponse && `response: ${(responseBytes / 1024).toFixed(1)} KB`})
          </span>
        </button>
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          {hasPayload && hasResponse && (
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">
              {(["request", "response"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "px-3 py-1 capitalize transition-colors",
                    tab === t
                      ? "bg-violet-600 text-white"
                      : "bg-white text-gray-600 hover:bg-gray-50"
                  )}
                >
                  {t === "request" ? "Request payload" : "Full response"}
                </button>
              ))}
            </div>
          )}
          {tab === "request" && hasPayload && (
            <JsonPane title="Request body sent to Kore.ai" json={payload!} />
          )}
          {tab === "response" && hasResponse && (
            <JsonPane title="Full raw response from Kore.ai" json={response!} />
          )}
          {tab === "response" && !hasResponse && hasPayload && (
            <p className="text-[11px] text-gray-400 italic">
              No raw response stored for this row (run was created before raw-response capture was added).
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function JsonPane({ title, json }: { title: string; json: Record<string, unknown> }) {
  const [copied, setCopied] = useState(false);
  const pretty = useMemo(() => JSON.stringify(json, null, 2), [json]);
  const sizeKb = (pretty.length / 1024).toFixed(1);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(pretty);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between px-2 py-1 text-[11px] text-gray-500 bg-gray-50 border border-gray-200 border-b-0 rounded-t-lg">
        <span>{title}</span>
        <div className="flex items-center gap-2">
          <span className="text-gray-400">{sizeKb} KB</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-gray-500 hover:text-gray-800 px-2 py-0.5 rounded border border-gray-200 bg-white"
          >
            {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      <pre className="p-3 bg-gray-900 text-gray-100 rounded-b-lg text-[11px] leading-relaxed overflow-auto font-mono max-h-[480px]">
        {pretty}
      </pre>
    </div>
  );
}

function Section({ title, children }: { title: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <p className="font-medium text-gray-600 mb-1">{title}</p>
      <p className="text-gray-500 whitespace-pre-wrap leading-relaxed">{children}</p>
    </div>
  );
}

function ScoreValue({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const color = pct >= 80 ? "text-green-700" : pct >= 60 ? "text-amber-700" : "text-red-700";
  return (
    <span className={cn("font-mono font-semibold text-xs", color)}>
      {value} <span className="text-gray-400 font-normal">/ {max}</span>
    </span>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: "green" | "red" | "amber";
}) {
  const textColor =
    color === "green" ? "text-green-700" :
    color === "red" ? "text-red-700" :
    color === "amber" ? "text-amber-700" :
    "text-gray-900";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <p className="text-xs font-medium text-gray-500 mb-1">{label}</p>
      <p className={cn("text-2xl font-bold", textColor)}>{value}</p>
    </div>
  );
}

function PipelineStatCard({
  stage, description, count, denom, rate,
}: {
  stage: string;
  description: string;
  count: number;
  denom: number;
  rate: number | null;
}) {
  const pct = rate != null ? rate * 100 : null;
  const tone =
    pct == null ? "border-gray-200 bg-gray-50/40 text-gray-600" :
    pct >= 80 ? "border-green-200 bg-green-50/40 text-green-700" :
    pct >= 50 ? "border-amber-200 bg-amber-50/40 text-amber-700" :
    "border-red-200 bg-red-50/40 text-red-700";
  return (
    <div className={cn("rounded-lg border p-4 flex flex-col gap-2", tone)}>
      <div className="flex items-baseline justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{stage}</p>
        <span className="text-[11px] font-mono text-gray-500">{count}/{denom}</span>
      </div>
      <p className="text-3xl font-bold leading-none">
        {pct != null ? `${pct.toFixed(1)}%` : "—"}
      </p>
      <p className="text-[11px] text-gray-500 leading-snug">{description}</p>
    </div>
  );
}
