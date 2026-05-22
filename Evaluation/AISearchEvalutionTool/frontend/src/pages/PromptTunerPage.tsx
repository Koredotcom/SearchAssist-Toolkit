import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  promptTunerApi, promptsApi,
} from "@/lib/api";
import type {
  FailureSample, PromptTunerFineTuneResponse, PromptTunerRunSummary,
  TunableAgent,
} from "@/lib/api";
import {
  Sparkles, Wand2, Save, Check, Loader2, AlertCircle, RefreshCw,
  ChevronDown, ChevronRight, FileText, MessageSquareText, ArrowRight,
  RotateCcw, Copy,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function PromptTunerPage() {
  const { appId } = useParams<{ appId: string }>();
  const qc = useQueryClient();
  const [activeAgent, setActiveAgent] = useState<string>("answer_generator");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [draftPrompt, setDraftPrompt] = useState<string | null>(null);
  const [userNotes, setUserNotes] = useState("");
  const [maxSamples, setMaxSamples] = useState(10);
  const [improved, setImproved] = useState<PromptTunerFineTuneResponse | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [tuneError, setTuneError] = useState<string | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────
  const { data: agents = [] } = useQuery({
    queryKey: ["prompt-tuner-agents", appId],
    queryFn: () => promptTunerApi.listAgents(appId!),
    enabled: !!appId,
  });

  const { data: runs = [] } = useQuery({
    queryKey: ["prompt-tuner-runs", appId],
    queryFn: () => promptTunerApi.listRuns(appId!),
    enabled: !!appId,
  });

  const { data: activePrompt } = useQuery({
    queryKey: ["prompt-active", appId, activeAgent],
    queryFn: () => promptsApi.getActive(appId!, activeAgent),
    enabled: !!appId && !!activeAgent,
    retry: false,
  });

  const { data: failuresData, isFetching: failuresLoading } = useQuery({
    queryKey: ["prompt-tuner-failures", appId, selectedRunId, activeAgent, maxSamples],
    queryFn: () => promptTunerApi.getFailures(appId!, selectedRunId!, activeAgent, maxSamples),
    enabled: !!appId && !!selectedRunId && !!activeAgent,
  });

  // Default to the freshest run that has failures, if the user hasn't picked one yet.
  useEffect(() => {
    if (!selectedRunId && runs.length) {
      const firstWithFailures = runs.find((r) => r.failure_count > 0);
      setSelectedRunId((firstWithFailures ?? runs[0]).run_id);
    }
  }, [runs, selectedRunId]);

  // When agent changes, clear any pending draft / improved suggestion.
  useEffect(() => {
    setDraftPrompt(null);
    setImproved(null);
    setTuneError(null);
  }, [activeAgent]);

  const currentPromptText = draftPrompt ?? activePrompt?.prompt_text ?? "";

  // ── Mutations ────────────────────────────────────────────────────────────
  const tuneMutation = useMutation({
    mutationFn: () => promptTunerApi.fineTune(appId!, {
      agent_name: activeAgent,
      current_prompt: currentPromptText || null,
      run_id: selectedRunId,
      max_samples: maxSamples,
      user_notes: userNotes.trim() || null,
    }),
    onMutate: () => {
      setTuneError(null);
      setImproved(null);
    },
    onSuccess: (data) => {
      setImproved(data);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail
        ?? (err as Error)?.message
        ?? "Failed to fine-tune prompt.";
      setTuneError(msg);
    },
  });

  const saveMutation = useMutation({
    mutationFn: (text: string) => promptsApi.update(appId!, activeAgent, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      qc.invalidateQueries({ queryKey: ["prompt-active", appId, activeAgent] });
      setDraftPrompt(null);
      setImproved(null);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
    },
  });

  const selectedRun = useMemo<PromptTunerRunSummary | undefined>(
    () => runs.find((r) => r.run_id === selectedRunId),
    [runs, selectedRunId],
  );

  const canTune = !!selectedRunId && !!currentPromptText && (failuresData?.returned ?? 0) > 0;
  const promptDirty = draftPrompt !== null && draftPrompt !== (activePrompt?.prompt_text ?? "");

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Wand2 className="w-5 h-5 text-violet-600" />
            <h1 className="text-2xl font-bold text-gray-900">Prompt Fine-Tuning</h1>
            <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full font-semibold">
              Beta
            </span>
          </div>
          <p className="text-sm text-gray-500">
            Improve an agent's prompt by showing it real evaluation failures (question + expected vs. generated response).
          </p>
        </div>
      </div>

      {/* ── Step 1: choose agent + run ─────────────────────────────────── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <SectionHeader
          step={1}
          title="Choose what to tune"
          subtitle="Pick the agent whose prompt you want to improve, and the run to learn failures from."
        />

        <div className="grid gap-4 md:grid-cols-2">
          <AgentSelect
            agents={agents}
            value={activeAgent}
            onChange={setActiveAgent}
          />
          <RunSelect
            runs={runs}
            value={selectedRunId}
            onChange={(v) => { setSelectedRunId(v); setImproved(null); }}
          />
        </div>

        {selectedRun && (
          <div className="text-xs text-gray-500 flex flex-wrap items-center gap-x-4 gap-y-1 pt-1">
            <span><strong className="text-gray-700">{selectedRun.failure_count}</strong> failures · {selectedRun.total_cases} total cases</span>
            <span>Golden set: <code className="text-violet-700">{selectedRun.golden_set_version}</code></span>
            <span>RAG: <code className="text-violet-700">{selectedRun.rag_version}</code></span>
            <span>{new Date(selectedRun.started_at).toLocaleString()}</span>
          </div>
        )}
      </section>

      {/* ── Step 2: review failures ────────────────────────────────────── */}
      <section className="bg-white border border-gray-200 rounded-xl">
        <div className="px-5 py-4 border-b border-gray-100">
          <SectionHeader
            step={2}
            title="Review the failures"
            subtitle="These are the (question · expected · generated) trios the model will learn from."
            trailing={
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500 flex items-center gap-1.5">
                  Samples
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={maxSamples}
                    onChange={(e) => setMaxSamples(Math.max(1, Math.min(20, Number(e.target.value))))}
                    className="w-14 px-2 py-1 text-xs border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                </label>
                {failuresLoading && <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />}
              </div>
            }
          />
        </div>

        {!selectedRunId ? (
          <EmptyState
            icon={<MessageSquareText className="w-8 h-8 text-gray-300" />}
            title="Pick a run to see failures"
          />
        ) : failuresLoading && !failuresData ? (
          <EmptyState
            icon={<Loader2 className="w-8 h-8 text-gray-400 animate-spin" />}
            title="Loading failures..."
          />
        ) : (failuresData?.returned ?? 0) === 0 ? (
          <EmptyState
            icon={<FileText className="w-8 h-8 text-gray-300" />}
            title="No failures in this run"
            subtitle="Either everything passed, or the run has no verdicted-fail rows. Try another run."
          />
        ) : (
          <FailureList failures={failuresData!.failures} totalFailures={failuresData!.total_failures} />
        )}
      </section>

      {/* ── Step 3: current prompt ─────────────────────────────────────── */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
        <SectionHeader
          step={3}
          title="Confirm or edit the current prompt"
          subtitle="The tuner will use this as the starting point. Edit here to ask the model to revise something specific."
          trailing={
            promptDirty && (
              <button
                onClick={() => setDraftPrompt(null)}
                className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                <RotateCcw className="w-3 h-3" />
                Revert
              </button>
            )
          }
        />

        <textarea
          value={currentPromptText}
          onChange={(e) => setDraftPrompt(e.target.value)}
          rows={10}
          spellCheck={false}
          placeholder={activePrompt ? "" : "No active prompt for this agent yet — paste one here, or visit Prompts & Models to set a default."}
          className="w-full p-3 text-xs font-mono text-gray-700 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 leading-relaxed"
        />
        <div className="flex items-center justify-between text-[11px] text-gray-400">
          <span>
            {currentPromptText.length} characters
            {activePrompt && (
              <> · current active v{activePrompt.version} · {new Date(activePrompt.created_at).toLocaleDateString()}</>
            )}
          </span>
          {promptDirty && (
            <span className="text-amber-600 font-medium">Using your edits as the starting point</span>
          )}
        </div>

        <div className="pt-1">
          <label className="text-xs font-medium text-gray-600 mb-1.5 block">
            Optional instructions for the tuner
          </label>
          <input
            type="text"
            value={userNotes}
            onChange={(e) => setUserNotes(e.target.value)}
            placeholder="e.g. be stricter about hallucinations, keep the JSON schema unchanged, shorten answers"
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          />
        </div>
      </section>

      {/* ── Step 4: generate ──────────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200 rounded-xl p-5">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-semibold text-gray-900">Ready to fine-tune?</p>
            <p className="text-xs text-gray-600 mt-0.5">
              The tuner will reuse this agent's LLM config (falling back to <strong>insights</strong> if its provider key isn't set) to rewrite the prompt based on {failuresData?.returned ?? 0} failure{(failuresData?.returned ?? 0) === 1 ? "" : "s"}.
            </p>
          </div>
          <button
            onClick={() => tuneMutation.mutate()}
            disabled={!canTune || tuneMutation.isPending}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg transition-colors shadow-sm",
              canTune && !tuneMutation.isPending
                ? "bg-violet-600 text-white hover:bg-violet-700"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            )}
          >
            {tuneMutation.isPending
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating improved prompt...</>
              : <><Sparkles className="w-4 h-4" /> Generate improved prompt</>
            }
          </button>
        </div>

        {tuneError && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg border border-red-200 bg-red-50">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
            <div className="text-xs text-red-700 whitespace-pre-wrap break-words">{tuneError}</div>
          </div>
        )}
      </section>

      {/* ── Step 5: improved prompt ───────────────────────────────────── */}
      {improved && (
        <ImprovedPromptCard
          improved={improved}
          isSaving={saveMutation.isPending}
          savedFlash={savedFlash}
          onSave={() => saveMutation.mutate(improved.improved_prompt)}
          onDiscard={() => setImproved(null)}
          onUseAsDraft={() => {
            setDraftPrompt(improved.improved_prompt);
            setImproved(null);
          }}
        />
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function SectionHeader({ step, title, subtitle, trailing }: {
  step: number; title: string; subtitle?: string; trailing?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-violet-100 text-violet-700 text-sm font-bold flex items-center justify-center shrink-0">
          {step}
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">{title}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {trailing && <div className="shrink-0">{trailing}</div>}
    </div>
  );
}

function AgentSelect({ agents, value, onChange }: {
  agents: TunableAgent[];
  value: string;
  onChange: (v: string) => void;
}) {
  const labelFor = (n: string) => ({
    agent1: "Summarizer (agent1)",
    agent2: "Generator (agent2)",
    agent3: "Ranker (agent3)",
    judge: "Judge",
    filter_generator: "Filter Generator",
    insights: "Insights",
    answer_generator: "Answer Generation",
  } as Record<string, string>)[n] ?? n;

  const selected = agents.find((a) => a.agent_name === value);

  return (
    <div>
      <label className="text-xs font-medium text-gray-600 mb-1.5 block">Agent prompt to tune</label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none pl-3 pr-8 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
        >
          {agents.map((a) => (
            <option key={a.agent_name} value={a.agent_name}>{labelFor(a.agent_name)}</option>
          ))}
        </select>
        <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>
      {selected?.description && (
        <p className="text-[11px] text-gray-500 mt-1.5 leading-relaxed">{selected.description}</p>
      )}
    </div>
  );
}

function RunSelect({ runs, value, onChange }: {
  runs: import("@/lib/api").PromptTunerRunSummary[];
  value: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 mb-1.5 block">Evaluation run (failures source)</label>
      <div className="relative">
        <select
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none pl-3 pr-8 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
        >
          {runs.length === 0 && <option value="">No evaluation runs yet</option>}
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id.slice(0, 8)} · {r.failure_count} fail / {r.total_cases} · {new Date(r.started_at).toLocaleDateString()}
            </option>
          ))}
        </select>
        <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>
      {runs.length === 0 && (
        <p className="text-[11px] text-gray-500 mt-1.5">Run an evaluation first to gather failures.</p>
      )}
    </div>
  );
}

function FailureList({ failures, totalFailures }: { failures: FailureSample[]; totalFailures: number }) {
  return (
    <div className="divide-y divide-gray-100 max-h-[520px] overflow-y-auto">
      <div className="px-5 py-2.5 bg-gray-50 text-xs text-gray-500 sticky top-0 z-10 border-b border-gray-100">
        Showing <strong className="text-gray-700">{failures.length}</strong> of {totalFailures} failed cases
      </div>
      {failures.map((f) => <FailureCard key={f.tc_id} failure={f} />)}
    </div>
  );
}

function FailureCard({ failure }: { failure: FailureSample }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="px-5 py-3.5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-start gap-2 w-full text-left group"
      >
        {open
          ? <ChevronDown className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
          : <ChevronRight className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-800 font-medium leading-snug line-clamp-2 group-hover:text-gray-900">
            {failure.question}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
            {failure.failure_category && failure.failure_category !== "none" && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-50 text-red-700 font-medium">
                {failure.failure_category}
              </span>
            )}
            {failure.question_type && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
                {failure.question_type}
              </span>
            )}
            {failure.case_id != null && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                Case {failure.case_id}
              </span>
            )}
            <code className="text-[10px] text-gray-400 font-mono">tc_id: {failure.tc_id.slice(0, 12)}</code>
          </div>
        </div>
      </button>

      {open && (
        <div className="mt-3 ml-6 grid gap-3 lg:grid-cols-2">
          <ResponseBlock
            label="Expected answer"
            tone="green"
            text={failure.expected_answer || "(none)"}
          />
          <ResponseBlock
            label="Generated answer"
            tone="red"
            text={failure.generated_answer || "(empty response)"}
          />
          {failure.judge_rationale && (
            <div className="lg:col-span-2">
              <ResponseBlock
                label="Judge rationale"
                tone="neutral"
                text={failure.judge_rationale}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResponseBlock({ label, text, tone }: {
  label: string; text: string;
  tone: "green" | "red" | "neutral";
}) {
  const toneCls = {
    green:   "border-green-200 bg-green-50/40",
    red:     "border-red-200 bg-red-50/40",
    neutral: "border-gray-200 bg-gray-50",
  }[tone];
  const labelCls = {
    green:   "text-green-700",
    red:     "text-red-700",
    neutral: "text-gray-600",
  }[tone];
  return (
    <div className={cn("rounded-lg border p-3", toneCls)}>
      <p className={cn("text-[11px] font-semibold mb-1.5", labelCls)}>{label}</p>
      <pre className="text-xs text-gray-700 whitespace-pre-wrap break-words font-sans leading-relaxed">
        {text}
      </pre>
    </div>
  );
}

function EmptyState({ icon, title, subtitle }: {
  icon: React.ReactNode; title: string; subtitle?: string;
}) {
  return (
    <div className="py-12 text-center">
      <div className="flex justify-center mb-3">{icon}</div>
      <p className="text-sm font-medium text-gray-600">{title}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}

function ImprovedPromptCard({
  improved, isSaving, savedFlash, onSave, onDiscard, onUseAsDraft,
}: {
  improved: PromptTunerFineTuneResponse;
  isSaving: boolean;
  savedFlash: boolean;
  onSave: () => void;
  onDiscard: () => void;
  onUseAsDraft: () => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyImproved = async () => {
    try {
      await navigator.clipboard.writeText(improved.improved_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  };

  return (
    <section className="bg-white border border-violet-300 rounded-xl overflow-hidden shadow-sm">
      <div className="px-5 py-4 border-b border-violet-100 bg-violet-50/60 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <Sparkles className="w-4 h-4 text-violet-600" />
          <p className="text-sm font-semibold text-gray-900">Improved prompt</p>
          <span className="text-[11px] font-mono text-gray-500">{improved.model}</span>
          {improved.llm_slot && improved.llm_slot !== improved.agent_name && (
            <span
              className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium"
              title={`The target agent's model wasn't usable, so the tuner borrowed the '${improved.llm_slot}' agent's LLM config to run.`}
            >
              via {improved.llm_slot}
            </span>
          )}
          <span className="text-[10px] text-gray-400">·</span>
          <span className="text-[11px] text-gray-500">{improved.samples_used} failures analysed</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={copyImproved}
            className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            onClick={onUseAsDraft}
            className="flex items-center gap-1 px-2.5 py-1 text-xs text-violet-700 border border-violet-200 rounded-lg hover:bg-violet-50"
          >
            <RefreshCw className="w-3 h-3" />
            Use as starting point
          </button>
          <button
            onClick={onSave}
            disabled={isSaving}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors",
              savedFlash
                ? "bg-green-500 text-white"
                : "bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-60"
            )}
          >
            {savedFlash ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
            {isSaving ? "Saving..." : savedFlash ? "Saved as new version" : "Save as new version"}
          </button>
          <button
            onClick={onDiscard}
            disabled={isSaving}
            className="px-2.5 py-1 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Discard
          </button>
        </div>
      </div>

      {improved.summary_of_changes && (
        <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/60">
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
            Summary of changes
          </p>
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">
            {improved.summary_of_changes}
          </p>
          {improved.failure_patterns?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {improved.failure_patterns.map((p, i) => (
                <span key={`${p}-${i}`} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-100">
        <div className="p-4">
          <div className="flex items-center gap-1.5 mb-2">
            <FileText className="w-3.5 h-3.5 text-gray-400" />
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Before</p>
          </div>
          <pre className="text-[11px] font-mono text-gray-600 whitespace-pre-wrap break-words leading-relaxed max-h-[480px] overflow-y-auto bg-gray-50 rounded p-3 border border-gray-100">
            {improved.current_prompt}
          </pre>
        </div>
        <div className="p-4 bg-violet-50/30">
          <div className="flex items-center gap-1.5 mb-2">
            <ArrowRight className="w-3.5 h-3.5 text-violet-500" />
            <p className="text-[11px] font-semibold text-violet-700 uppercase tracking-wider">After</p>
          </div>
          <pre className="text-[11px] font-mono text-gray-800 whitespace-pre-wrap break-words leading-relaxed max-h-[480px] overflow-y-auto bg-white rounded p-3 border border-violet-100">
            {improved.improved_prompt}
          </pre>
        </div>
      </div>

      <div className="px-5 py-2.5 border-t border-gray-100 bg-gray-50">
        <button
          onClick={() => setShowRaw((v) => !v)}
          className="text-[11px] text-gray-500 hover:text-gray-700 flex items-center gap-1"
        >
          {showRaw ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Raw LLM response (for debugging)
        </button>
        {showRaw && (
          <pre className="mt-2 p-3 text-[10px] font-mono bg-gray-900 text-green-300 rounded leading-relaxed max-h-48 overflow-y-auto">
            {improved.raw_response}
          </pre>
        )}
      </div>
    </section>
  );
}
