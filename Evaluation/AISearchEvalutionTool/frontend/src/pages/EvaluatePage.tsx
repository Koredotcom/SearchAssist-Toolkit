import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goldenSetsApi, evaluationApi, appsApi, appApiKeysApi } from "@/lib/api";
import type {
  Job, AnswerMode, FilterMode, JudgeMode, ChunkScoringMode, SavedEvaluateSettings,
} from "@/lib/api";
import { FlaskConical, Loader2, CheckCircle, XCircle, ChevronRight, Filter, UserCircle, Zap, FileText, Square, Info, ChevronDown, ChevronUp, Scale, Sparkles, SlidersHorizontal, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export default function EvaluatePage() {
  const { appId } = useParams<{ appId: string }>();
  const [selectedVersion, setSelectedVersion] = useState("");
  const [ragVersion, setRagVersion] = useState("latest");
  const [limitCases, setLimitCases] = useState(false);
  const [maxCases, setMaxCases] = useState(10);
  const [sampleMode, setSampleMode] = useState<"first" | "random">("first");
  // Advanced filters
  const [filterMode, setFilterMode] = useState<FilterMode>("none");
  const [filterFields, setFilterFields] = useState<string[]>([]);
  const [enableRacl, setEnableRacl] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  // Answer mode: null = inherit from app config, otherwise an explicit override for this run
  const [answerModeOverride, setAnswerModeOverride] = useState<AnswerMode | null>(null);
  // Question type filter: empty = all types
  const [selectedQTypes, setSelectedQTypes] = useState<string[]>([]);
  const [showCasesPanel, setShowCasesPanel] = useState(false);
  // Verdict configuration overrides (per-run)
  const [showVerdictPanel, setShowVerdictPanel] = useState(false);
  const [judgeMode, setJudgeMode] = useState<JudgeMode>("auto");
  const [case1Threshold, setCase1Threshold] = useState<number | null>(null);
  const [case2Threshold, setCase2Threshold] = useState<number | null>(null);
  const [topKPass, setTopKPass] = useState<number | null>(null);
  const [chunkScoringMode, setChunkScoringMode] = useState<ChunkScoringMode>("qualified_only");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const ALL_QUESTION_TYPES = [
    { value: "factual",     label: "Factual" },
    { value: "multi_hop",   label: "Multi-hop" },
    { value: "comparative", label: "Comparative" },
    { value: "boundary",    label: "Boundary" },
    { value: "follow_up",   label: "Follow-up" },
  ];

  const { data: apps = [] } = useQuery({
    queryKey: ["apps"],
    queryFn: appsApi.list,
  });
  const currentApp = apps.find((a) => a.app_id === appId);
  const appAnswerMode: AnswerMode = currentApp?.answer_mode ?? "answer_generation";
  // Effective mode shown in UI: override takes precedence, else use app default
  const effectiveAnswerMode: AnswerMode = answerModeOverride ?? appAnswerMode;

  const { data: goldenSets = [] } = useQuery({
    queryKey: ["golden-sets", appId],
    queryFn: () => goldenSetsApi.list(appId!),
    enabled: !!appId,
  });

  // Filter field options for the selected golden set (only needed in field_filters mode)
  const { data: filterOptions } = useQuery({
    queryKey: ["filter-options", appId, selectedVersion],
    queryFn: () => goldenSetsApi.filterOptions(appId!, selectedVersion),
    enabled: !!appId && !!selectedVersion && filterMode === "field_filters",
    staleTime: 30_000,
  });
  const availableFilterFields = filterOptions?.fields ?? [];

  // App-level thresholds (used as the placeholder/default for overrides)
  const { data: apiKeyStatus } = useQuery({
    queryKey: ["app-api-keys", appId],
    queryFn: () => appApiKeysApi.get(appId!),
    enabled: !!appId,
  });
  const appCase1 = apiKeyStatus?.case1_threshold ?? 0.5;
  const appCase2 = apiKeyStatus?.case2_threshold ?? 0.5;
  const judgeKeySet =
    apiKeyStatus?.anthropic_key_set || apiKeyStatus?.openai_key_set || apiKeyStatus?.gemini_key_set;
  const effectiveCase1 = case1Threshold ?? appCase1;
  const effectiveCase2 = case2Threshold ?? appCase2;
  const effectiveTopK = topKPass ?? 5;
  const verdictOverrideCount =
    (judgeMode !== "auto" ? 1 : 0) +
    (case1Threshold !== null ? 1 : 0) +
    (case2Threshold !== null ? 1 : 0) +
    (topKPass !== null ? 1 : 0) +
    (effectiveAnswerMode === "extract_only" && chunkScoringMode !== "qualified_only" ? 1 : 0);

  const { data: jobs = [] } = useQuery({
    queryKey: ["eval-jobs", appId],
    queryFn: () => evaluationApi.listJobs(appId!),
    enabled: !!appId,
  });

  // ── Auto-saved settings ────────────────────────────────────────────
  // Hydrate on first load, then debounce-save the full state on any change.
  const hydratedRef = useRef(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: savedSettings } = useQuery({
    queryKey: ["evaluate-settings", appId],
    queryFn: () => evaluationApi.getSettings(appId!),
    enabled: !!appId,
    staleTime: Infinity,
  });

  useEffect(() => {
    if (hydratedRef.current || !savedSettings) return;
    const s = savedSettings.settings;
    if (!s) {
      hydratedRef.current = true;
      return;
    }
    setSelectedVersion(s.selectedVersion ?? "");
    setRagVersion(s.ragVersion ?? "latest");
    setLimitCases(!!s.limitCases);
    setMaxCases(typeof s.maxCases === "number" ? s.maxCases : 10);
    setSampleMode(s.sampleMode ?? "first");
    setFilterMode(s.filterMode ?? "none");
    setFilterFields(Array.isArray(s.filterFields) ? s.filterFields : []);
    setEnableRacl(!!s.enableRacl);
    setUserEmail(s.userEmail ?? "");
    setAnswerModeOverride(s.answerModeOverride ?? null);
    setSelectedQTypes(Array.isArray(s.selectedQTypes) ? s.selectedQTypes : []);
    setJudgeMode(s.judgeMode ?? "auto");
    setCase1Threshold(s.case1Threshold ?? null);
    setCase2Threshold(s.case2Threshold ?? null);
    setTopKPass(s.topKPass ?? null);
    setChunkScoringMode(s.chunkScoringMode ?? "qualified_only");
    hydratedRef.current = true;
  }, [savedSettings]);

  const saveSettingsMutation = useMutation({
    mutationFn: (s: SavedEvaluateSettings) => evaluationApi.saveSettings(appId!, s),
    onMutate: () => setSaveStatus("saving"),
    onSuccess: () => {
      setSaveStatus("saved");
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
      savedTimerRef.current = setTimeout(() => setSaveStatus("idle"), 1500);
    },
    onError: () => setSaveStatus("idle"),
  });

  useEffect(() => {
    if (!appId || !hydratedRef.current) return;
    const snapshot: SavedEvaluateSettings = {
      selectedVersion, ragVersion, limitCases, maxCases, sampleMode,
      filterMode, filterFields, enableRacl, userEmail,
      answerModeOverride, selectedQTypes,
      judgeMode, case1Threshold, case2Threshold, topKPass, chunkScoringMode,
    };
    const handle = setTimeout(() => saveSettingsMutation.mutate(snapshot), 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    appId, selectedVersion, ragVersion, limitCases, maxCases, sampleMode,
    filterMode, filterFields, enableRacl, userEmail,
    answerModeOverride, selectedQTypes,
    judgeMode, case1Threshold, case2Threshold, topKPass, chunkScoringMode,
  ]);

  const { data: activeJob } = useQuery({
    queryKey: ["eval-job", appId, activeJobId],
    queryFn: () => evaluationApi.getJob(appId!, activeJobId!),
    enabled: !!appId && !!activeJobId,
    refetchInterval: (query) => {
      const job = query.state.data;
      return job?.status === "running" ? 2000 : false;
    },
  });

  const frozenSets = goldenSets.filter((g) => g.frozen_at !== null);
  const selectedSet = frozenSets.find((g) => g.version === selectedVersion);
  const totalAvailable = selectedSet?.kept_cases ?? 0;
  const effectiveCases = limitCases ? Math.min(maxCases, totalAvailable) : totalAvailable;

  const stopMutation = useMutation({
    mutationFn: () => evaluationApi.stop(appId!, activeJobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["eval-job", appId, activeJobId] });
    },
  });

  const startMutation = useMutation({
    mutationFn: () =>
      evaluationApi.start(appId!, {
        golden_set_version: selectedVersion,
        rag_version: ragVersion,
        max_cases: limitCases ? maxCases : null,
        sample_mode: sampleMode,
        filter_mode: filterMode,
        filter_prompt: null,
        filter_fields: filterMode === "field_filters" && filterFields.length > 0 ? filterFields : null,
        enable_racl: enableRacl,
        user_email: enableRacl && userEmail.trim() ? userEmail.trim() : null,
        answer_mode_override: answerModeOverride,
        question_types: selectedQTypes.length > 0 ? selectedQTypes : null,
        judge_mode: judgeMode,
        case1_threshold: case1Threshold,
        case2_threshold: case2Threshold,
        top_k_pass: topKPass,
        chunk_scoring_mode:
          effectiveAnswerMode === "extract_only" ? chunkScoringMode : null,
      }),
    onSuccess: (job: Job) => setActiveJobId(job.job_id),
  });

  const isRunning = activeJob?.status === "running";

  const raclMissingEmail = enableRacl && !userEmail.trim();
  const canStart = !!selectedVersion && !isRunning && !raclMissingEmail;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Evaluate</h1>
          <p className="text-sm text-gray-500 mt-1">
            Run evaluation against a frozen golden set
          </p>
        </div>
        <div className="text-xs text-gray-400 pt-1.5 min-w-[80px] text-right">
          {saveStatus === "saving" && (
            <span className="inline-flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" />Saving…</span>
          )}
          {saveStatus === "saved" && (
            <span className="inline-flex items-center gap-1 text-green-600"><Check className="w-3 h-3" />Saved</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-6 space-y-5">

          {/* ── Evaluation Cases Reference ───────────────────── */}
          <div className="rounded-lg border border-violet-100 bg-violet-50/50">
            <button
              type="button"
              onClick={() => setShowCasesPanel((v) => !v)}
              className="flex items-center justify-between w-full text-left px-4 py-3 group"
            >
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-violet-500" />
                <span className="text-sm font-semibold text-violet-800 group-hover:text-violet-900">
                  How are test cases evaluated?
                </span>
              </div>
              {showCasesPanel
                ? <ChevronUp className="w-4 h-4 text-violet-400" />
                : <ChevronDown className="w-4 h-4 text-violet-400" />}
            </button>

            {showCasesPanel && (
              <div className="px-4 pb-4 space-y-2">
                {([
                  {
                    id: 1,
                    label: "Question only",
                    inputs: ["Question"],
                    ag: {
                      judge: "Coherence + Fluency ≥ 3 (LLM judge)",
                      noJudge: "Q↔Answer relevance ≥ threshold (semantic)",
                    },
                    eo: {
                      rule: "Q↔Answer relevance ≥ threshold (semantic)",
                      note: "No reference doc — falls back to semantic similarity",
                    },
                  },
                  {
                    id: 2,
                    label: "Question + Expected Answer",
                    inputs: ["Question", "Expected Answer"],
                    ag: {
                      judge: "Ground-truth relevance + Completeness ≥ 3 (LLM judge)",
                      noJudge: "Answer↔Expected similarity ≥ threshold (semantic)",
                    },
                    eo: {
                      rule: "Answer↔Expected similarity ≥ threshold (semantic)",
                      note: "No reference doc — uses answer similarity",
                    },
                  },
                  {
                    id: 3,
                    label: "Question + Reference Doc",
                    inputs: ["Question", "Reference Doc"],
                    ag: {
                      judge: "Groundedness + Query relevance ≥ 3 (LLM judge)",
                      noJudge: "Q↔Answer relevance ≥ threshold (semantic)",
                    },
                    eo: {
                      rule: "Expected chunk in top-K scoring pool (see Verdict Configuration)",
                      note: "Qualified-only or raw chunk list — pass if match rank ≤ top-K",
                    },
                  },
                  {
                    id: 4,
                    label: "Full: Question + Answer + Reference Doc",
                    inputs: ["Question", "Expected Answer", "Reference Doc"],
                    ag: {
                      judge: "Groundedness + Relevance + Ground-truth + Completeness ≥ 3",
                      noJudge: "Answer↔Expected similarity ≥ threshold (semantic)",
                    },
                    eo: {
                      rule: "Expected chunk in top-K scoring pool (see Verdict Configuration)",
                      note: "Qualified-only or raw chunk list — pass if match rank ≤ top-K",
                    },
                  },
                ] as const).map(({ id, label, inputs, ag, eo }) => {
                  const isExtract = effectiveAnswerMode === "extract_only";
                  const primaryRule = isExtract ? eo.rule : ag.judge;
                  const secondaryNote = isExtract ? eo.note : `Fallback without judge: ${ag.noJudge}`;
                  return (
                    <div key={id} className="rounded-lg border border-white bg-white p-3">
                      <div className="flex items-start gap-3">
                        <span className={cn(
                          "shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mt-0.5",
                          isExtract ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"
                        )}>
                          {id}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-gray-800 mb-1.5">{label}</p>
                          <div className="flex flex-wrap gap-1 mb-2">
                            {inputs.map((inp) => (
                              <span
                                key={inp}
                                className="text-[10px] px-1.5 py-0.5 bg-gray-50 border border-gray-200 rounded text-gray-500"
                              >
                                {inp}
                              </span>
                            ))}
                          </div>
                          <p className={cn(
                            "text-[11px] font-medium leading-relaxed",
                            isExtract ? "text-amber-700" : "text-blue-700"
                          )}>
                            {primaryRule}
                          </p>
                          <p className="text-[11px] text-gray-400 mt-0.5 leading-relaxed">{secondaryNote}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
                <p className="text-[11px] text-gray-500 pt-1">
                  <strong>Judge</strong> requires an LLM key in <strong>API Keys</strong>.
                  Without it, semantic similarity is used as fallback.
                  Logic above reflects the currently selected answer mode.
                </p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Golden Set Version <span className="text-red-500">*</span>
            </label>
            {frozenSets.length === 0 ? (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
                No frozen golden sets found. Go to <strong>Generate</strong> to create and freeze one first.
              </div>
            ) : (
              <div className="space-y-2 max-h-[128px] overflow-y-auto pr-1">
                {frozenSets.map((gs) => (
                  <label
                    key={gs.version}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                      selectedVersion === gs.version
                        ? "border-violet-300 bg-violet-50"
                        : "border-gray-100 hover:border-gray-200"
                    )}
                  >
                    <input
                      type="radio"
                      name="golden-set"
                      value={gs.version}
                      checked={selectedVersion === gs.version}
                      onChange={() => setSelectedVersion(gs.version)}
                      className="mt-0.5 accent-violet-600"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-800">{gs.version}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {gs.kept_cases} test cases · frozen {new Date(gs.frozen_at!).toLocaleDateString()}
                        {gs.notes && ` · ${gs.notes}`}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              RAG Version Label
            </label>
            <input
              type="text"
              value={ragVersion}
              onChange={(e) => setRagVersion(e.target.value)}
              placeholder="e.g. latest, v2.1, experiment-a"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              A label to identify this RAG configuration in results
            </p>
          </div>

          {/* Question type categories */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">Question Categories</label>
              {selectedQTypes.length > 0 && (
                <button
                  onClick={() => setSelectedQTypes([])}
                  className="text-xs text-violet-600 hover:text-violet-800"
                >
                  Clear (all types)
                </button>
              )}
            </div>
            <p className="text-xs text-gray-400 mb-2">
              {selectedQTypes.length === 0
                ? "All question types will be evaluated"
                : `Only: ${selectedQTypes.join(", ")}`}
            </p>
            <div className="flex flex-wrap gap-2">
              {ALL_QUESTION_TYPES.map((qt) => {
                const active = selectedQTypes.includes(qt.value);
                return (
                  <button
                    key={qt.value}
                    onClick={() =>
                      setSelectedQTypes((prev) =>
                        active ? prev.filter((v) => v !== qt.value) : [...prev, qt.value]
                      )
                    }
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-full border transition-colors",
                      active
                        ? "border-violet-500 bg-violet-50 text-violet-700"
                        : "border-gray-200 text-gray-500 hover:border-gray-300"
                    )}
                  >
                    {qt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Case limit */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">Questions to Evaluate</label>
              <button
                onClick={() => setLimitCases((v) => !v)}
                className={cn(
                  "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                  limitCases ? "bg-violet-600" : "bg-gray-200"
                )}
              >
                <span className={cn(
                  "inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform",
                  limitCases ? "translate-x-4.5" : "translate-x-0.5"
                )} />
              </button>
            </div>

            {!limitCases ? (
              <p className="text-sm text-gray-500">
                All <span className="font-semibold text-gray-800">{totalAvailable}</span> questions from the selected golden set
              </p>
            ) : (
              <div className="space-y-3">
                <div>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min={1}
                      max={totalAvailable || 9999}
                      value={maxCases}
                      onChange={(e) => setMaxCases(Math.max(1, Number(e.target.value)))}
                      className="w-24 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                    />
                    <span className="text-sm text-gray-400">
                      of {totalAvailable || "?"} available
                      {totalAvailable > 0 && maxCases >= totalAvailable && (
                        <span className="ml-1 text-amber-500">(will use all)</span>
                      )}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={Math.max(totalAvailable, 1)}
                    value={Math.min(maxCases, Math.max(totalAvailable, 1))}
                    onChange={(e) => setMaxCases(Number(e.target.value))}
                    className="w-full mt-2 accent-violet-600"
                    disabled={totalAvailable === 0}
                  />
                </div>

                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1.5">Sampling strategy</p>
                  <div className="flex gap-2">
                    {(["first", "random"] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setSampleMode(mode)}
                        className={cn(
                          "px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors",
                          sampleMode === mode
                            ? "border-violet-400 bg-violet-50 text-violet-700"
                            : "border-gray-200 text-gray-500 hover:border-gray-300"
                        )}
                      >
                        {mode === "first" ? "First N" : "Random sample"}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {sampleMode === "first"
                      ? "Takes the first questions by insertion order — deterministic, same each run"
                      : "Random sample — better coverage across question types"}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* ── Answer Configuration ──────────────────────────── */}
          <div className="pt-2 border-t border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {effectiveAnswerMode === "answer_generation"
                  ? <Zap className="w-4 h-4 text-blue-500" />
                  : <FileText className="w-4 h-4 text-amber-500" />}
                <h3 className="text-sm font-semibold text-gray-800">Answer Configuration</h3>
              </div>
              {answerModeOverride && (
                <button
                  onClick={() => setAnswerModeOverride(null)}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Reset to app default
                </button>
              )}
            </div>

            {/* App default hint */}
            {!answerModeOverride && (
              <p className="text-xs text-gray-400 mb-3">
                Using app default: <span className={cn(
                  "font-medium",
                  appAnswerMode === "answer_generation" ? "text-blue-600" : "text-amber-600"
                )}>
                  {appAnswerMode === "answer_generation" ? "Answer Generation" : "Extraction"}
                </span>. Select below to override for this run only.
              </p>
            )}

            <div className="grid grid-cols-2 gap-3">
              {([
                {
                  mode: "answer_generation" as AnswerMode,
                  icon: Zap,
                  title: "Answer Generation",
                  desc: "Kore.ai LLM generates a natural language answer from retrieved documents",
                  color: "blue",
                },
                {
                  mode: "extract_only" as AnswerMode,
                  icon: FileText,
                  title: "Extraction",
                  desc: "answerSearch=false — retrieval only; pass = expected chunk in top-K; chunk LLM scores optional",
                  color: "amber",
                },
              ]).map(({ mode, icon: Icon, title, desc, color }) => {
                const isSelected = effectiveAnswerMode === mode;
                const isOverridden = answerModeOverride === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setAnswerModeOverride(answerModeOverride === mode && appAnswerMode === mode ? null : mode)}
                    className={cn(
                      "text-left p-3 rounded-lg border-2 transition-all",
                      isSelected
                        ? color === "blue"
                          ? "border-blue-400 bg-blue-50"
                          : "border-amber-400 bg-amber-50"
                        : "border-gray-100 hover:border-gray-200 bg-white"
                    )}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className={cn(
                        "w-3.5 h-3.5",
                        isSelected
                          ? color === "blue" ? "text-blue-600" : "text-amber-600"
                          : "text-gray-400"
                      )} />
                      <span className={cn(
                        "text-xs font-semibold",
                        isSelected
                          ? color === "blue" ? "text-blue-700" : "text-amber-700"
                          : "text-gray-600"
                      )}>
                        {title}
                        {isOverridden && <span className="ml-1 text-[10px] opacity-70">(override)</span>}
                        {!isOverridden && appAnswerMode === mode && <span className="ml-1 text-[10px] opacity-60">(app default)</span>}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-400 leading-relaxed">{desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Verdict Configuration ───────────────────────── */}
          <div className="pt-2 border-t border-gray-100">
            <button
              type="button"
              onClick={() => setShowVerdictPanel((v) => !v)}
              className="flex items-center justify-between w-full text-left group mb-3"
            >
              <div className="flex items-center gap-2">
                <Scale className="w-4 h-4 text-violet-500" />
                <h3 className="text-sm font-semibold text-gray-800 group-hover:text-gray-900">
                  Verdict Configuration
                </h3>
                {verdictOverrideCount > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded-full font-semibold">
                    {verdictOverrideCount} override{verdictOverrideCount > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              {showVerdictPanel
                ? <ChevronUp className="w-4 h-4 text-gray-400" />
                : <ChevronDown className="w-4 h-4 text-gray-400" />}
            </button>

            {showVerdictPanel && (
              <div className="space-y-5">
                {/* Judge mode */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                      <p className="text-xs font-semibold text-gray-700">Judge mode</p>
                    </div>
                    {judgeMode !== "auto" && (
                      <button
                        onClick={() => setJudgeMode("auto")}
                        className="text-[11px] text-gray-400 hover:text-gray-600 underline"
                      >
                        Reset to auto
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-400 mb-2">
                    Controls whether the LLM judge scores each answer.
                    {!judgeKeySet && (
                      <span className="block text-amber-600 mt-1">
                        No LLM API key found for any provider — judge can't run, falls back to semantic similarity.
                      </span>
                    )}
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { id: "auto",       label: "Auto",       desc: "Judge if API key is configured" },
                      { id: "force_on",   label: "Always on",  desc: "Require LLM judge — fails if no key" },
                      { id: "force_off",  label: "Never",      desc: "Skip judge, semantic only" },
                    ] as const).map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setJudgeMode(m.id)}
                        className={cn(
                          "text-left p-2.5 rounded-lg border-2 transition-all",
                          judgeMode === m.id
                            ? "border-violet-400 bg-violet-50"
                            : "border-gray-100 hover:border-gray-200 bg-white"
                        )}
                      >
                        <p className={cn(
                          "text-xs font-semibold",
                          judgeMode === m.id ? "text-violet-700" : "text-gray-600"
                        )}>{m.label}</p>
                        <p className="text-[11px] text-gray-400 mt-0.5 leading-snug">{m.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Thresholds — only meaningful when judge isn't running */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-violet-500" />
                    <p className="text-xs font-semibold text-gray-700">Semantic-similarity thresholds</p>
                    <span className="text-[10px] text-gray-400">
                      (used when judge is off or unavailable)
                    </span>
                  </div>

                  <ThresholdRow
                    label="Case 1 / 3 — Q ↔ Answer relevance"
                    helpText="Cases without an expected answer pass when relevance ≥ threshold."
                    value={effectiveCase1}
                    isOverride={case1Threshold !== null}
                    appDefault={appCase1}
                    onChange={(v) => setCase1Threshold(v)}
                    onReset={() => setCase1Threshold(null)}
                  />
                  <ThresholdRow
                    label="Case 2 / 4 — Answer ↔ Expected similarity"
                    helpText="Cases with an expected answer pass when similarity ≥ threshold."
                    value={effectiveCase2}
                    isOverride={case2Threshold !== null}
                    appDefault={appCase2}
                    onChange={(v) => setCase2Threshold(v)}
                    onReset={() => setCase2Threshold(null)}
                  />
                </div>

                {/* Top-K — retrieval verdict threshold (extract_only mode) */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <SlidersHorizontal className="w-3.5 h-3.5 text-violet-500" />
                      <p className="text-xs font-semibold text-gray-700">Retrieval top-K pass threshold</p>
                    </div>
                    {topKPass !== null && (
                      <button
                        onClick={() => setTopKPass(null)}
                        className="text-[11px] text-gray-400 hover:text-gray-600 underline"
                      >
                        Reset to 5
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-400 mb-2">
                    For <strong>extract_only</strong> (Cases 3 &amp; 4): pass if the expected match is in the top {effectiveTopK}{" "}
                    {chunkScoringMode === "qualified_only" ? "qualified" : "raw"} chunks — same rule as Recall@{effectiveTopK}.
                  </p>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={effectiveTopK}
                      onChange={(e) => setTopKPass(Math.max(1, Math.min(50, Number(e.target.value))))}
                      className="w-20 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                    />
                    <input
                      type="range"
                      min={1}
                      max={20}
                      value={Math.min(effectiveTopK, 20)}
                      onChange={(e) => setTopKPass(Number(e.target.value))}
                      className="flex-1 accent-violet-600"
                    />
                  </div>
                </div>

                {effectiveAnswerMode === "extract_only" && (
                  <div>
                    <p className="text-xs font-semibold text-gray-700 mb-2">Chunk scoring pool</p>
                    <p className="text-[11px] text-gray-400 mb-2">
                      Choose which rows from Advance Search count for rank, pass/fail, and Recall@K.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {([
                        {
                          id: "qualified_only" as const,
                          label: "Qualified only",
                          desc: "Only chunkQualified=true rows (Kore.ai retrieval pool). Default.",
                        },
                        {
                          id: "raw" as const,
                          label: "Raw chunk list",
                          desc: "All chunk_result rows in API order (positions 1…N).",
                        },
                      ]).map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => setChunkScoringMode(opt.id)}
                          className={cn(
                            "text-left p-3 rounded-lg border transition-colors",
                            chunkScoringMode === opt.id
                              ? "border-violet-400 bg-violet-50"
                              : "border-gray-100 hover:border-gray-200 bg-white",
                          )}
                        >
                          <p className={cn(
                            "text-xs font-semibold",
                            chunkScoringMode === opt.id ? "text-violet-700" : "text-gray-600",
                          )}>
                            {opt.label}
                          </p>
                          <p className="text-[11px] text-gray-400 mt-0.5 leading-snug">{opt.desc}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {verdictOverrideCount > 0 && (
                  <button
                    onClick={() => {
                      setJudgeMode("auto");
                      setCase1Threshold(null);
                      setCase2Threshold(null);
                      setTopKPass(null);
                      setChunkScoringMode("qualified_only");
                    }}
                    className="text-xs text-gray-500 hover:text-gray-700 underline"
                  >
                    Clear all verdict overrides
                  </button>
                )}
              </div>
            )}
          </div>

          {/* ── Advanced filters / RACL ──────────────────────── */}
          <div className="pt-2 border-t border-gray-100">
            <div className="flex items-center gap-2 mb-3">
              <Filter className="w-4 h-4 text-violet-500" />
              <h3 className="text-sm font-semibold text-gray-800">Advanced Filters</h3>
            </div>

            {/* Filter mode */}
            <div className="space-y-2 mb-4">
              <p className="text-xs font-medium text-gray-600">Meta-filter strategy</p>
              {([
                {
                  id: "none" as FilterMode,
                  label: "No filters",
                  desc: "Only the question is sent — no metaFilter is attached to the RAG query",
                },
                {
                  id: "field_filters" as FilterMode,
                  label: "Filters",
                  desc: "Apply filters from the golden set columns — choose which fields to include below",
                },
                {
                  id: "custom_prompt" as FilterMode,
                  label: "Custom prompt",
                  desc: "Use the Filter Generator LLM to produce metaFilters per question (configure prompt & mapper in Prompts & Models)",
                },
              ]).map((m) => (
                <label
                  key={m.id}
                  className={cn(
                    "flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors",
                    filterMode === m.id
                      ? "border-violet-300 bg-violet-50"
                      : "border-gray-100 hover:border-gray-200"
                  )}
                >
                  <input
                    type="radio"
                    name="filter-mode"
                    value={m.id}
                    checked={filterMode === m.id}
                    onChange={() => {
                      setFilterMode(m.id);
                      if (m.id !== "field_filters") setFilterFields([]);
                    }}
                    className="mt-0.5 accent-violet-600"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{m.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{m.desc}</p>
                  </div>
                </label>
              ))}
            </div>

            {/* Field picker — shown when "Filters" mode is active */}
            {filterMode === "field_filters" && (
              <div className="mb-4 rounded-lg border border-violet-100 bg-violet-50/40 p-3 space-y-2">
                {!selectedVersion ? (
                  <p className="text-xs text-gray-400 italic">Select a golden set above to see available filter fields.</p>
                ) : availableFilterFields.length === 0 ? (
                  <p className="text-xs text-amber-700 italic">
                    No filterable columns found in this golden set.
                    Add a <code className="text-xs bg-amber-100 px-1 rounded">sys_content_type</code> column or custom columns to the sheet before uploading.
                  </p>
                ) : (
                  <>
                    <p className="text-xs font-medium text-gray-700">
                      Pick which fields to apply as metaFilters.
                      Filters are only applied to test cases that have a value for that field.
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {availableFilterFields.map((f) => {
                        const active = filterFields.includes(f.name);
                        return (
                          <button
                            key={f.name}
                            type="button"
                            onClick={() =>
                              setFilterFields((prev) =>
                                active ? prev.filter((x) => x !== f.name) : [...prev, f.name]
                              )
                            }
                            className={cn(
                              "flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full border transition-colors",
                              active
                                ? "border-violet-500 bg-violet-100 text-violet-800"
                                : "border-gray-200 bg-white text-gray-600 hover:border-violet-300"
                            )}
                          >
                            <span>{f.label}</span>
                            <span className={cn("text-[10px] px-1 rounded", active ? "text-violet-500" : "text-gray-400")}>
                              {f.count}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    {filterFields.length === 0 && (
                      <p className="text-xs text-amber-600 pt-1">Select at least one field — otherwise no filters will be applied.</p>
                    )}
                  </>
                )}
              </div>
            )}

            {filterMode === "custom_prompt" && (
              <div className="mb-4">
                <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                  <Info className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                  <p className="text-xs text-blue-700">
                    Uses the <strong>Filter Generator</strong> prompt configured in{" "}
                    <strong>Prompts &amp; Models</strong>. Edit the prompt and response mapper script there to change what filters are generated.
                  </p>
                </div>
              </div>
            )}

            {/* RACL */}
            <div className="pt-3 mt-3 border-t border-gray-100">
              <div className="flex items-center justify-between mb-2">
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <UserCircle className="w-4 h-4 text-blue-500" />
                  Use RACL user context
                </label>
                <button
                  onClick={() => setEnableRacl((v) => !v)}
                  className={cn(
                    "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                    enableRacl ? "bg-violet-600" : "bg-gray-200"
                  )}
                >
                  <span className={cn(
                    "inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform",
                    enableRacl ? "translate-x-4.5" : "translate-x-0.5"
                  )} />
                </button>
              </div>

              {!enableRacl ? (
                <p className="text-xs text-gray-400">
                  Queries run with no user context. Enable to send <code>customData.userContext.userId</code> on every query.
                </p>
              ) : (
                <div>
                  <input
                    type="email"
                    value={userEmail}
                    onChange={(e) => setUserEmail(e.target.value)}
                    placeholder="user@company.com"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                  {raclMissingEmail && (
                    <p className="text-xs text-red-600 mt-1">Email is required when RACL is enabled</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Actions + status */}
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Summary</h2>
            <div className="space-y-2 text-sm">
              <Row label="Golden set" value={selectedVersion || "—"} />
              <Row label="Available questions" value={totalAvailable ? String(totalAvailable) : "—"} />
              <Row
                label="Questions to run"
                value={selectedVersion ? `${effectiveCases}${limitCases && sampleMode === "random" ? " (random)" : ""}` : "—"}
              />
              <Row label="RAG version" value={ragVersion || "—"} />
              <div className="flex items-center justify-between py-0.5">
                <span className="text-gray-500">Answer config</span>
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded-full font-medium",
                  effectiveAnswerMode === "answer_generation" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"
                )}>
                  {effectiveAnswerMode === "answer_generation" ? "⚡ Answer Generation" : "📄 Extraction"}
                  {answerModeOverride && <span className="ml-1 opacity-60">(override)</span>}
                </span>
              </div>
              <Row
                label="Filter mode"
                value={
                  filterMode === "none" ? "None"
                  : filterMode === "field_filters"
                    ? filterFields.length > 0
                      ? `Fields: ${filterFields.join(", ")}`
                      : "Filters (no fields selected)"
                    : "Custom prompt"
                }
              />
              <Row
                label="Q. Types"
                value={selectedQTypes.length === 0 ? "All" : selectedQTypes.join(", ")}
              />
              <Row
                label="RACL"
                value={enableRacl ? (userEmail.trim() || "(missing email)") : "Off"}
              />
              <Row
                label="Judge mode"
                value={
                  judgeMode === "force_on" ? "Always on" :
                  judgeMode === "force_off" ? "Never" :
                  judgeKeySet ? "Auto (on)" : "Auto (off — no key)"
                }
              />
              <Row
                label="Thresholds"
                value={`C1:${effectiveCase1.toFixed(2)} · C2:${effectiveCase2.toFixed(2)} · top-K:${effectiveTopK}`}
              />
            </div>

            <button
              onClick={() => startMutation.mutate()}
              disabled={!canStart || startMutation.isPending}
              className={cn(
                "w-full mt-5 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors",
                !canStart
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                  : "bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
              )}
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Evaluating...
                </>
              ) : (
                <>
                  <FlaskConical className="w-4 h-4" />
                  Start Evaluation
                </>
              )}
            </button>
          </div>

          {activeJob && (
            <JobProgress
              job={activeJob}
              onStop={() => stopMutation.mutate()}
              isStopping={stopMutation.isPending}
            />
          )}

          {jobs.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Recent Jobs</h3>
              <div className="space-y-2">
                {jobs.slice(0, 5).map((job) => (
                  <div
                    key={job.job_id}
                    onClick={() => setActiveJobId(job.job_id)}
                    className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                  >
                    <StatusDot status={job.status} />
                    <span className="text-xs text-gray-600 font-mono truncate">{job.job_id.slice(0, 12)}...</span>
                    <span className="text-xs text-gray-400 ml-auto">{job.progress}%</span>
                    <ChevronRight className="w-3 h-3 text-gray-300" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function JobProgress({
  job,
  onStop,
  isStopping,
}: {
  job: Job;
  onStop: () => void;
  isStopping: boolean;
}) {
  const isRunning = job.status === "running";
  const isDone = job.status === "complete";
  const isStopped = job.status === "partial";
  const isFailed = job.status === "failed";

  const r = job.result as Record<string, number> | null;
  const done = r?.done ?? 0;
  const total = r?.total ?? 0;
  const passed = r?.passed ?? 0;
  const verdicted = r?.verdicted ?? 0;
  const pending = total > 0 ? total - done : 0;

  const passRate = verdicted > 0
    ? ((passed / verdicted) * 100).toFixed(1)
    : total > 0 && r?.pass_rate != null
      ? (r.pass_rate * 100).toFixed(1)
      : null;

  return (
    <div className={cn(
      "rounded-xl border p-4",
      isDone ? "bg-green-50 border-green-200" :
      isFailed ? "bg-red-50 border-red-200" :
      isStopped ? "bg-amber-50 border-amber-200" :
      "bg-violet-50 border-violet-200"
    )}>
      <div className="flex items-center gap-2 mb-2">
        {isRunning && <Loader2 className="w-4 h-4 animate-spin text-violet-600" />}
        {isDone && <CheckCircle className="w-4 h-4 text-green-600" />}
        {isFailed && <XCircle className="w-4 h-4 text-red-600" />}
        {isStopped && <XCircle className="w-4 h-4 text-amber-600" />}
        <span className={cn(
          "text-sm font-medium",
          isDone ? "text-green-800" :
          isFailed ? "text-red-800" :
          isStopped ? "text-amber-800" :
          "text-violet-800"
        )}>
          {isRunning ? "Evaluating..." : isDone ? "Complete" : isStopped ? "Stopped early" : "Failed"}
        </span>
        <span className="ml-auto text-sm font-semibold text-gray-700">{job.progress}%</span>
        {isRunning && (
          <button
            onClick={onStop}
            disabled={isStopping}
            title="Stop evaluation after current case"
            className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStopping
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <Square className="w-3 h-3 fill-current" />}
            Stop
          </button>
        )}
      </div>

      <div className="w-full bg-white/60 rounded-full h-2 overflow-hidden mb-3">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            isDone ? "bg-green-500" :
            isFailed ? "bg-red-500" :
            isStopped ? "bg-amber-500" :
            "bg-violet-500"
          )}
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {/* Live counts */}
      {total > 0 && (
        <div className="grid grid-cols-3 gap-2 text-center mb-2">
          <div className="bg-white/70 rounded-lg px-2 py-1.5">
            <p className="text-lg font-bold text-violet-700">{done}</p>
            <p className="text-[10px] text-gray-500">Done</p>
          </div>
          <div className="bg-white/70 rounded-lg px-2 py-1.5">
            <p className="text-lg font-bold text-gray-400">{pending}</p>
            <p className="text-[10px] text-gray-500">Pending</p>
          </div>
          <div className="bg-white/70 rounded-lg px-2 py-1.5">
            <p className="text-lg font-bold text-green-700">{passed}</p>
            <p className="text-[10px] text-gray-500">Passed</p>
          </div>
        </div>
      )}

      {isFailed && job.error && (
        <p className="text-xs text-red-600 mt-1">{job.error}</p>
      )}
      {(isDone || isStopped) && passRate !== null && (
        <p className={cn(
          "text-xs font-medium mt-1",
          isDone ? "text-green-700" : "text-amber-700"
        )}>
          Pass rate: {passRate}%
          {isStopped && <span className="text-gray-500 font-normal ml-1">(partial — {done}/{total} cases evaluated)</span>}
        </p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-800">{value}</span>
    </div>
  );
}

function ThresholdRow({
  label, helpText, value, isOverride, appDefault, onChange, onReset,
}: {
  label: string;
  helpText: string;
  value: number;
  isOverride: boolean;
  appDefault: number;
  onChange: (v: number) => void;
  onReset: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-medium text-gray-700">{label}</p>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-semibold text-violet-700">
            {value.toFixed(2)}
          </span>
          {isOverride ? (
            <button
              onClick={onReset}
              className="text-[11px] text-gray-400 hover:text-gray-600 underline"
              title={`Reset to app default (${appDefault.toFixed(2)})`}
            >
              Reset
            </button>
          ) : (
            <span className="text-[10px] text-gray-300">app default</span>
          )}
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-violet-600"
      />
      <p className="text-[11px] text-gray-400 mt-0.5">{helpText}</p>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  return (
    <div className={cn(
      "w-2 h-2 rounded-full shrink-0",
      status === "complete" ? "bg-green-500" :
      status === "failed" ? "bg-red-500" :
      "bg-violet-500 animate-pulse"
    )} />
  );
}
