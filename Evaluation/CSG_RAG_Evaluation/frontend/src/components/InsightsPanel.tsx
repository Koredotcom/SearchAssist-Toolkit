import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  AlertOctagon, AlertTriangle, Info, Lightbulb, RefreshCw,
  Sparkles, Filter as FilterIcon, ChevronDown, ChevronRight,
  Wand2, Loader2, RotateCcw, Settings,
} from "lucide-react";
import { resultsApi } from "@/lib/api";
import type { FiredRule, RuleSeverity, RunDiagnostics } from "@/lib/api";
import { cn } from "@/lib/utils";
import { FEATURE_AI_DEEP_DIVE } from "@/lib/featureFlags";
import Markdown from "@/components/Markdown";

// ── Severity styling ─────────────────────────────────────────────────────────
const SEVERITY_STYLES: Record<RuleSeverity, {
  bar: string; chip: string; ring: string; icon: typeof AlertOctagon;
}> = {
  high: {
    bar: "bg-red-500",
    chip: "bg-red-100 text-red-700 border-red-200",
    ring: "border-red-200 bg-red-50/40",
    icon: AlertOctagon,
  },
  medium: {
    bar: "bg-amber-500",
    chip: "bg-amber-100 text-amber-800 border-amber-200",
    ring: "border-amber-200 bg-amber-50/40",
    icon: AlertTriangle,
  },
  low: {
    bar: "bg-blue-500",
    chip: "bg-blue-100 text-blue-700 border-blue-200",
    ring: "border-blue-200 bg-blue-50/40",
    icon: Info,
  },
};

// ── Funnel step labels & descriptions ────────────────────────────────────────
const FUNNEL_STEPS: Array<{
  key: keyof RunDiagnostics["funnel"];
  label: string;
  hint: string;
}> = [
  { key: "queried",             label: "Queried",                 hint: "Total RAG queries attempted" },
  { key: "retrieved_any_doc",   label: "Retrieved ≥1 doc",        hint: "Got at least one document back" },
  { key: "expected_doc_top10",  label: "Expected doc in top 10",  hint: "Reference doc ranked ≤10 (Cases 3/4)" },
  { key: "expected_doc_top5",   label: "Expected doc in top 5",   hint: "Reference doc ranked ≤5" },
  { key: "expected_doc_top1",   label: "Expected doc = #1",       hint: "Reference doc ranked first" },
  { key: "expected_chunk_top5", label: "Expected chunk in top 5", hint: "Matching chunk ranked ≤5 (stricter)" },
  { key: "answered",            label: "RAG returned answer",     hint: "Non-empty answer produced" },
  { key: "verdict_pass",        label: "Verdict: pass",           hint: "Final verdict was pass" },
];

// ── Props ────────────────────────────────────────────────────────────────────
export interface InsightsPanelProps {
  appId: string;
  runId: string;
  /** Notifies parent of recommended filter changes (e.g. "show only retrieval_miss"). */
  onApplyRuleFilter?: (filter: {
    failure_category?: string;
    question_type?: string;
    tc_ids?: string[];
  }) => void;
}

export default function InsightsPanel({ appId, runId, onApplyRuleFilter }: InsightsPanelProps) {
  const qc = useQueryClient();
  const [isRecomputing, setIsRecomputing] = useState(false);
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["diagnostics", appId, runId],
    queryFn: () => resultsApi.getDiagnostics(appId, runId),
    enabled: !!appId && !!runId,
    staleTime: 5 * 60 * 1000,
  });

  const handleRecompute = async () => {
    try {
      setIsRecomputing(true);
      const fresh = await resultsApi.getDiagnostics(appId, runId, true);
      qc.setQueryData(["diagnostics", appId, runId], fresh);
    } finally {
      setIsRecomputing(false);
    }
  };

  const busy = isRecomputing || isFetching;

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-48 bg-gray-200 rounded" />
          <div className="h-3 w-full bg-gray-100 rounded" />
          <div className="h-3 w-3/4 bg-gray-100 rounded" />
          <div className="h-24 w-full bg-gray-100 rounded" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="bg-white border border-red-200 rounded-xl p-5">
        <div className="flex items-center gap-2 text-red-700 mb-1">
          <AlertTriangle className="w-4 h-4" />
          <p className="text-sm font-semibold">Failed to compute diagnostics</p>
        </div>
        <p className="text-xs text-red-600 mb-3">
          {(error as Error | undefined)?.message ?? "Backend returned an error."}
        </p>
        <button
          onClick={handleRecompute}
          className="text-xs font-medium px-3 py-1 border border-red-300 rounded-md text-red-700 hover:bg-red-50"
        >
          Try again
        </button>
      </div>
    );
  }

  const { funnel, fired_rules, weakest_judge_metric, retrieval, totals } = data;
  const maxFunnel = Math.max(funnel.queried, 1);

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* ── Header ───────────────────────────────────────── */}
      <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-3 bg-gradient-to-r from-violet-50/50 to-transparent">
        <div className="w-7 h-7 rounded-md bg-violet-100 text-violet-700 flex items-center justify-center shrink-0">
          <Lightbulb className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-gray-900">Insights</h2>
          <p className="text-xs text-gray-500">
            Deterministic diagnostics — funnel, weak spots, and recommended fixes
          </p>
        </div>
        <button
          onClick={handleRecompute}
          disabled={busy}
          title="Re-compute diagnostics from the latest results"
          className="flex items-center gap-1 text-xs px-2.5 py-1 border border-gray-200 rounded-md text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={cn("w-3 h-3", busy && "animate-spin")} />
          {busy ? "Computing…" : "Recompute"}
        </button>
      </div>

      <div className="p-5 grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── Funnel ────────────────────────────────────── */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <FilterIcon className="w-3.5 h-3.5 text-gray-400" />
            <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Retrieval Funnel</h3>
          </div>
          <div className="space-y-1.5">
            {FUNNEL_STEPS.map((step, i) => {
              const value = funnel[step.key];
              const pct = (value / maxFunnel) * 100;
              const prev = i > 0 ? funnel[FUNNEL_STEPS[i - 1].key] : value;
              const dropPct = prev > 0 ? Math.round(((prev - value) / prev) * 100) : 0;
              return (
                <FunnelStep
                  key={step.key}
                  label={step.label}
                  hint={step.hint}
                  value={value}
                  pct={pct}
                  dropPct={i === 0 ? null : dropPct}
                />
              );
            })}
          </div>

          <div className="grid grid-cols-2 gap-3 mt-5">
            <MiniStat
              label="Avg chunk rank"
              value={retrieval.avg_chunk_rank != null ? `#${retrieval.avg_chunk_rank}` : "—"}
              tone={
                retrieval.avg_chunk_rank == null
                  ? "neutral"
                  : retrieval.avg_chunk_rank <= 10
                  ? "good"
                  : retrieval.avg_chunk_rank <= 30
                  ? "warn"
                  : "bad"
              }
            />
            <MiniStat
              label="Recall @5"
              value={retrieval.recall_at_5 != null ? `${Math.round(retrieval.recall_at_5 * 100)}%` : "—"}
              tone={
                retrieval.recall_at_5 == null
                  ? "neutral"
                  : retrieval.recall_at_5 >= 0.8
                  ? "good"
                  : retrieval.recall_at_5 >= 0.6
                  ? "warn"
                  : "bad"
              }
            />
            <MiniStat
              label="Recall @10"
              value={retrieval.recall_at_10 != null ? `${Math.round(retrieval.recall_at_10 * 100)}%` : "—"}
              tone={
                retrieval.recall_at_10 == null
                  ? "neutral"
                  : retrieval.recall_at_10 >= 0.8
                  ? "good"
                  : retrieval.recall_at_10 >= 0.6
                  ? "warn"
                  : "bad"
              }
            />
            <MiniStat
              label="No verdict"
              value={String(totals.no_verdict)}
              tone={totals.no_verdict === 0 ? "good" : totals.no_verdict <= 3 ? "warn" : "bad"}
            />
            <MiniStat
              label="Weakest metric"
              value={weakest_judge_metric ?? "—"}
              tone="warn"
            />
          </div>
        </div>

        {/* ── Rules / Recommendations ─────────────────── */}
        <div className="lg:col-span-3">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-3.5 h-3.5 text-violet-500" />
            <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
              Recommendations <span className="text-gray-400 normal-case font-normal">
                {fired_rules.length === 0
                  ? "— no patterns detected"
                  : `(${fired_rules.length})`
                }
              </span>
            </h3>
          </div>

          {fired_rules.length === 0 ? (
            <div className="border border-dashed border-green-200 bg-green-50/40 rounded-lg p-6 text-center">
              <p className="text-sm font-medium text-green-800">No patterns detected.</p>
              <p className="text-xs text-green-700 mt-1">
                Either this run is healthy, or the rule engine didn't find enough failures to flag.
              </p>
            </div>
          ) : (
            <ul className="space-y-2.5">
              {fired_rules.map((rule) => (
                <RuleCard
                  key={rule.rule_id}
                  rule={rule}
                  onApplyFilter={onApplyRuleFilter}
                />
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── AI Deep Dive (LLM narrative) ───────────────────────────
          Gated by FEATURE_AI_DEEP_DIVE. Backend routes, DB columns and the
          `insights` agent are preserved so we can flip this back on with one
          line. Discuss + re-enable later. */}
      {FEATURE_AI_DEEP_DIVE && (
        <div className="border-t border-gray-100 bg-gray-50/60 px-5 py-4">
          <AIDeepDive appId={appId} runId={runId} />
        </div>
      )}
    </div>
  );
}

// ── AI Deep Dive sub-component ──────────────────────────────────────────────
function AIDeepDive({ appId, runId }: { appId: string; runId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [showSource, setShowSource] = useState(false);

  // Lightweight read — never triggers an LLM call. Tells us if a cached
  // narrative already exists.
  const { data, isLoading } = useQuery({
    queryKey: ["ai-insights", appId, runId],
    queryFn: () => resultsApi.getAiInsights(appId, runId),
    enabled: !!appId && !!runId,
    staleTime: 60 * 1000,
  });

  const generateMutation = useMutation({
    mutationFn: (regenerate: boolean) => resultsApi.generateAiInsights(appId, runId, regenerate),
    onSuccess: (fresh) => {
      qc.setQueryData(["ai-insights", appId, runId], fresh);
      setOpen(true);
    },
  });

  const hasCached = !!data?.markdown;
  const generating = generateMutation.isPending;
  const errorMsg = (generateMutation.error as { response?: { data?: { detail?: string } }; message?: string } | null)
    ?.response?.data?.detail
    ?? (generateMutation.error as Error | null)?.message
    ?? null;

  const generatedLabel = data?.generated_at
    ? new Date(data.generated_at).toLocaleString(undefined, {
        month: "short", day: "numeric", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : null;

  return (
    <div>
      <div className="flex items-start gap-3 flex-wrap">
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white flex items-center justify-center shrink-0 shadow-sm">
          <Wand2 className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-gray-900">AI Deep Dive</p>
            {hasCached && (
              <span className="text-[10px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 border border-violet-200">
                cached
              </span>
            )}
            {data?.model && (
              <span className="text-[10px] font-mono text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">
                {data.model}
              </span>
            )}
            {generatedLabel && (
              <span className="text-[10px] text-gray-400">generated {generatedLabel}</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            LLM-written analysis of what the rule engine missed — patterns, root cause, ranked actions.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {hasCached && !generating && (
            <button
              onClick={() => setOpen((o) => !o)}
              className="text-xs px-2.5 py-1 border border-gray-200 rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              {open ? "Hide" : "Show"} narrative
            </button>
          )}
          {hasCached && (
            <button
              onClick={() => generateMutation.mutate(true)}
              disabled={generating}
              title="Regenerate — discards cached narrative and re-runs the LLM"
              className="flex items-center gap-1 text-xs px-2.5 py-1 border border-gray-200 rounded-md text-gray-600 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
              {generating ? "Regenerating…" : "Regenerate"}
            </button>
          )}
          {!hasCached && (
            <button
              onClick={() => generateMutation.mutate(false)}
              disabled={generating || isLoading}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-md hover:from-violet-700 hover:to-fuchsia-700 disabled:opacity-60 shadow-sm"
            >
              {generating ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
              ) : (
                <><Sparkles className="w-3.5 h-3.5" /> Generate AI Deep Dive</>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Inline status messages */}
      {errorMsg && (
        <div className="mt-3 p-2.5 border border-red-200 bg-red-50 rounded-md text-xs text-red-700">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span><span className="font-medium">Generation failed:</span> {errorMsg}</span>
          </div>
          {/empty response|max_tokens|finish_reason/i.test(errorMsg) && (
            <div className="mt-2 pl-5">
              <Link
                to={`/apps/${appId}/llm-config`}
                className="inline-flex items-center gap-1 text-xs font-medium text-red-700 hover:text-red-900 underline underline-offset-2"
              >
                <Settings className="w-3 h-3" />
                Adjust the Insights agent in LLM Config
              </Link>
            </div>
          )}
        </div>
      )}

      {data?.warnings && data.warnings.length > 0 && !errorMsg && (
        <div className="mt-3 space-y-1.5">
          {data.warnings.map((w, i) => (
            <div key={i} className="p-2 border border-amber-200 bg-amber-50 rounded-md text-xs text-amber-800 flex items-start gap-2">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Narrative body */}
      {hasCached && open && data?.markdown && (
        <div className="mt-4 border border-violet-100 rounded-lg bg-white p-4">
          <Markdown text={data.markdown} />
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2">
            <button
              onClick={() => setShowSource((s) => !s)}
              className="text-[11px] text-gray-400 hover:text-gray-700"
            >
              {showSource ? "Hide" : "View"} raw markdown
            </button>
          </div>
          {showSource && (
            <pre className="mt-2 p-3 bg-gray-900 text-gray-100 rounded text-[11px] leading-relaxed overflow-x-auto font-mono max-h-96">
              {data.markdown}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Funnel step bar ──────────────────────────────────────────────────────────
function FunnelStep({
  label, hint, value, pct, dropPct,
}: {
  label: string; hint: string; value: number; pct: number; dropPct: number | null;
}) {
  const [hover, setHover] = useState(false);
  return (
    <div
      className="relative"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="flex items-center gap-2 text-xs">
        <span className="w-44 shrink-0 text-gray-700 truncate">{label}</span>
        <div className="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden relative">
          <div
            className={cn(
              "h-full transition-all",
              pct >= 80 ? "bg-green-400" : pct >= 50 ? "bg-amber-400" : "bg-red-400"
            )}
            style={{ width: `${Math.max(pct, 1.5)}%` }}
          />
          <span className="absolute inset-0 flex items-center justify-end pr-2 text-[11px] font-mono font-semibold text-gray-700">
            {value}
          </span>
        </div>
        {dropPct !== null && (
          <span
            className={cn(
              "w-10 text-right text-[10px] font-mono shrink-0",
              dropPct === 0 ? "text-gray-300" : dropPct <= 10 ? "text-gray-500" : "text-red-500"
            )}
            title={`Dropped ${dropPct}% from the previous step`}
          >
            {dropPct > 0 ? `−${dropPct}%` : ""}
          </span>
        )}
      </div>
      {hover && (
        <div className="absolute left-44 top-full mt-1 z-20 bg-gray-900 text-white text-xs rounded-md px-2 py-1 shadow-lg pointer-events-none">
          {hint}
        </div>
      )}
    </div>
  );
}

// ── Rule card ────────────────────────────────────────────────────────────────
function RuleCard({
  rule, onApplyFilter,
}: {
  rule: FiredRule;
  onApplyFilter?: InsightsPanelProps["onApplyRuleFilter"];
}) {
  const [open, setOpen] = useState(false);
  const sev = SEVERITY_STYLES[rule.severity];
  const SevIcon = sev.icon;

  // Derive the right filter action for known rule_id patterns
  const filterIntent = deriveFilterIntent(rule);

  return (
    <li className={cn("border rounded-lg overflow-hidden", sev.ring)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-3.5 py-3 flex items-start gap-3 text-left hover:bg-white/50 transition-colors"
      >
        <div className={cn("w-7 h-7 shrink-0 rounded-md flex items-center justify-center", sev.chip, "border")}>
          <SevIcon className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-gray-900">{rule.title}</p>
            <span className={cn("text-[10px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border", sev.chip)}>
              {rule.severity}
            </span>
            {rule.impact_count > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-mono">
                {rule.impact_count} case{rule.impact_count !== 1 ? "s" : ""}
                {rule.impact_pct > 0 && ` · ${Math.round(rule.impact_pct * 100)}%`}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-600 mt-1 leading-relaxed">{rule.description}</p>
        </div>
        <div className="shrink-0 pt-0.5">
          {open ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-300" />
          )}
        </div>
      </button>

      {open && (
        <div className="px-3.5 pb-3.5 pt-1 border-t border-white/60 bg-white/60">
          {rule.recommendations.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500 mb-1.5">
                Recommended actions
              </p>
              <ul className="space-y-1.5">
                {rule.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2 text-xs text-gray-700 leading-relaxed">
                    <span className="text-violet-500 shrink-0 mt-0.5">→</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex items-center flex-wrap gap-2">
            {filterIntent && onApplyFilter && (
              <button
                onClick={() => onApplyFilter(filterIntent.payload)}
                className="text-[11px] font-medium px-2.5 py-1 rounded-md border border-violet-200 bg-white text-violet-700 hover:bg-violet-50"
              >
                {filterIntent.label}
              </button>
            )}
            {rule.evidence_tc_ids.length > 0 && (
              <span className="text-[10px] text-gray-400 font-mono">
                Evidence: {rule.evidence_tc_ids.slice(0, 4).map((t) => t.slice(0, 8)).join(", ")}
                {rule.evidence_tc_ids.length > 4 && ` +${rule.evidence_tc_ids.length - 4} more`}
              </span>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

// ── Helper: map rule_id → suggested filter action ────────────────────────────
function deriveFilterIntent(rule: FiredRule): {
  label: string;
  payload: { failure_category?: string; question_type?: string; tc_ids?: string[] };
} | null {
  if (rule.rule_id === "retrieval_miss_dominant") {
    return { label: "Show retrieval-miss cases", payload: { failure_category: "retrieval_miss" } };
  }
  if (rule.rule_id === "safety_violations_detected") {
    return { label: "Show flagged cases", payload: { tc_ids: rule.evidence_tc_ids } };
  }
  if (rule.rule_id.startsWith("weak_qtype_")) {
    const qtype = rule.rule_id.replace("weak_qtype_", "");
    return { label: `Show '${qtype}' cases`, payload: { question_type: qtype } };
  }
  if (rule.evidence_tc_ids.length > 0) {
    return { label: `Show these ${rule.evidence_tc_ids.length} cases`, payload: { tc_ids: rule.evidence_tc_ids } };
  }
  return null;
}

// ── Mini stat tile ───────────────────────────────────────────────────────────
function MiniStat({
  label, value, tone,
}: {
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "neutral";
}) {
  const toneClass =
    tone === "good" ? "bg-green-50 border-green-200 text-green-800"
    : tone === "warn" ? "bg-amber-50 border-amber-200 text-amber-800"
    : tone === "bad" ? "bg-red-50 border-red-200 text-red-800"
    : "bg-gray-50 border-gray-200 text-gray-700";
  return (
    <div className={cn("border rounded-lg px-2.5 py-2", toneClass)}>
      <p className="text-[10px] uppercase tracking-wider opacity-70">{label}</p>
      <p className="text-sm font-mono font-bold mt-0.5 truncate">{value}</p>
    </div>
  );
}
