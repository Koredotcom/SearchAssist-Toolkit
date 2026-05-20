import { useState, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { promptsApi, llmApi, evaluationApi } from "@/lib/api";
import type { PromptConfig, LLMConfig } from "@/lib/api";
import { Settings2, Upload, RotateCcw, Save, Check, ChevronDown, X, Code2, Play, Loader2, AlertCircle, CheckCircle, FlaskConical, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";

const MAPPER_PYTHON_STARTER = `def map_response(response: str) -> list:
    """Map raw LLM filter response to Kore.ai metaFilters.

    Return simple format:  [{"field": "sys_content_type", "value": "jiraServer"}]
    Return Kore.ai format: [{"condition": "AND", "rules": [...]}]
    Return []              for no filters.
    """
    import json
    try:
        data = json.loads(response)
        source = data.get("source") or data.get("sys_content_type")
        if source:
            return [{"field": "sys_content_type", "value": source}]
    except Exception:
        pass
    return []
`;

const MAPPER_JS_STARTER = `function mapResponse(response) {
  // Map raw LLM filter response to Kore.ai metaFilters.
  // Return [{field: "sys_content_type", value: "jiraServer"}] or []
  try {
    const data = JSON.parse(response);
    const source = data.source || data.sys_content_type;
    if (source) return [{ field: "sys_content_type", value: source }];
  } catch (e) {}
  return [];
}
`;

const AGENTS = [
  { key: "agent1", label: "Summarizer",       tag: "A1", sub: "Extracts facts from documents" },
  { key: "agent2", label: "Generator",        tag: "A2", sub: "Creates Q&A test cases" },
  { key: "agent3", label: "Ranker",           tag: "A3", sub: "Scores & filters test cases" },
  { key: "judge",  label: "Judge",            tag: "J",  sub: "Scores RAG responses" },
  { key: "filter_generator", label: "Filter Generator", tag: "F", sub: "Builds search filters" },
];

const CLAUDE_MODELS = [
  "claude-opus-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5-20251001",
];

const OPENAI_MODELS = [
  "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini",
  "gpt-5", "gpt-5-mini", "o3", "o3-mini", "o4-mini",
];

export default function PromptsPage() {
  const { appId } = useParams<{ appId: string }>();
  const qc = useQueryClient();
  const [activeAgent, setActiveAgent] = useState("agent1");
  const [draftText, setDraftText] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [mapperPrefill, setMapperPrefill] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: prompts = [] } = useQuery({
    queryKey: ["prompts", appId],
    queryFn: () => promptsApi.list(appId!),
    enabled: !!appId,
  });

  const { data: llmConfigs = [] } = useQuery({
    queryKey: ["llm-config", appId],
    queryFn: () => llmApi.list(appId!),
    enabled: !!appId,
  });

  const activePrompt = prompts.find((p) => p.agent_name === activeAgent && p.is_active);
  const activeLlm = llmConfigs.find((c) => c.agent_name === activeAgent);
  const currentText = draftText ?? activePrompt?.prompt_text ?? "";

  const updateMutation = useMutation({
    mutationFn: (text: string) => promptsApi.update(appId!, activeAgent, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      setDraftText(null);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => promptsApi.reset(appId!, activeAgent),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      setDraftText(null);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => promptsApi.upload(appId!, activeAgent, file),
    onSuccess: (data: PromptConfig) => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      setDraftText(data.prompt_text);
    },
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadMutation.mutate(file);
    e.target.value = "";
  }

  const isDirty = draftText !== null && draftText !== activePrompt?.prompt_text;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Prompts &amp; Models</h1>
        <p className="text-sm text-gray-500 mt-1">
          Configure the model and prompt for each agent
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Agent list */}
        <div className="space-y-1">
          {AGENTS.map((agent) => {
            const prompt = prompts.find((p) => p.agent_name === agent.key && p.is_active);
            const llm = llmConfigs.find((c) => c.agent_name === agent.key);
            return (
              <button
                key={agent.key}
                onClick={() => { setActiveAgent(agent.key); setDraftText(null); setSaveSuccess(false); setMapperPrefill(""); }}
                className={cn(
                  "w-full text-left px-3 py-2.5 rounded-lg transition-colors",
                  activeAgent === agent.key
                    ? "bg-violet-50 text-violet-700"
                    : "text-gray-600 hover:bg-gray-100"
                )}
              >
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "text-[10px] font-bold px-1.5 py-0.5 rounded",
                    activeAgent === agent.key ? "bg-violet-200 text-violet-800" : "bg-gray-100 text-gray-500"
                  )}>
                    {agent.tag}
                  </span>
                  <span className="text-sm font-medium">{agent.label}</span>
                </div>
                <div className="flex items-center gap-2 mt-0.5 pl-7">
                  {llm?.model ? (
                    <span className="text-[10px] font-mono text-gray-400 truncate max-w-[120px]">
                      {llm.model.length > 18 ? llm.model.slice(0, 16) + "…" : llm.model}
                    </span>
                  ) : (
                    <span className="text-[10px] text-red-400">no model</span>
                  )}
                  {prompt && (
                    <span className="text-[10px] text-gray-300">· v{prompt.version}</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Editor panel */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {/* LLM config bar */}
            <LlmConfigBar
              appId={appId!}
              agentKey={activeAgent}
              config={activeLlm}
            />

            {/* Prompt toolbar */}
            <div className="flex items-center justify-between px-4 py-2.5 border-t border-b border-gray-100 bg-gray-50">
              <div className="flex items-center gap-2">
                <Settings2 className="w-3.5 h-3.5 text-violet-500" />
                <span className="text-xs font-medium text-gray-600">Prompt</span>
                {activePrompt && (
                  <span className="text-xs text-gray-400">v{activePrompt.version}</span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input ref={fileInputRef} type="file" accept=".txt,.md" onChange={handleFileChange} className="hidden" />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadMutation.isPending}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  <Upload className="w-3 h-3" />
                  {uploadMutation.isPending ? "Uploading…" : "Upload .txt"}
                </button>
                <button
                  onClick={() => resetMutation.mutate()}
                  disabled={resetMutation.isPending}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  <RotateCcw className="w-3 h-3" />
                  {resetMutation.isPending ? "Resetting…" : "Reset"}
                </button>
                <button
                  onClick={() => updateMutation.mutate(currentText)}
                  disabled={!isDirty || updateMutation.isPending}
                  className={cn(
                    "flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg transition-colors",
                    saveSuccess
                      ? "bg-green-500 text-white"
                      : isDirty
                      ? "bg-violet-600 text-white hover:bg-violet-700"
                      : "bg-gray-100 text-gray-400 cursor-not-allowed"
                  )}
                >
                  {saveSuccess ? <Check className="w-3 h-3" /> : <Save className="w-3 h-3" />}
                  {updateMutation.isPending ? "Saving…" : saveSuccess ? "Saved!" : "Save"}
                </button>
              </div>
            </div>

            {/* Textarea */}
            <textarea
              value={currentText}
              onChange={(e) => setDraftText(e.target.value)}
              className="w-full h-[420px] p-4 text-sm font-mono text-gray-700 resize-none focus:outline-none"
              placeholder="No prompt configured. Click Reset to load the default, or paste / upload your own."
              spellCheck={false}
            />

            {isDirty && (
              <div className="px-4 py-2 border-t border-gray-100 bg-amber-50 text-xs text-amber-700">
                Unsaved changes — click Save to commit as a new version
              </div>
            )}
          </div>

          {activeAgent === "filter_generator" && (
            <>
              <FilterGenTestCard
                appId={appId!}
                currentPromptText={currentText}
                onRawResponse={setMapperPrefill}
              />
              <MapperCard appId={appId!} prefillInput={mapperPrefill} />
            </>
          )}
        </div>
      </div>

      {/* Version history */}
      {prompts.filter((p) => p.agent_name === activeAgent).length > 1 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Version History</h3>
          <div className="space-y-1">
            {prompts
              .filter((p) => p.agent_name === activeAgent)
              .sort((a, b) => b.version - a.version)
              .map((p) => (
                <div
                  key={p.id}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                  onClick={() => setDraftText(p.prompt_text)}
                >
                  <span className="text-xs font-medium text-gray-700 w-8">v{p.version}</span>
                  <span className="text-xs text-gray-400">{new Date(p.created_at).toLocaleString()}</span>
                  {p.is_active && (
                    <span className="ml-auto text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">Active</span>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

    </div>
  );
}

// ── LLM config bar ────────────────────────────────────────────────────────────

function LlmConfigBar({
  appId, agentKey, config,
}: {
  appId: string;
  agentKey: string;
  config: LLMConfig | undefined;
}) {
  const qc = useQueryClient();
  const [model, setModel] = useState(config?.model ?? "claude-sonnet-4-6");
  const [customModel, setCustomModel] = useState("");
  const [temperature, setTemperature] = useState(config?.temperature ?? 0);
  const [maxTokens, setMaxTokens] = useState(config?.max_tokens ?? 4096);
  const [saved, setSaved] = useState(false);

  const effectiveModel = customModel.trim() || model;
  const isKnownModel = CLAUDE_MODELS.includes(effectiveModel) || OPENAI_MODELS.includes(effectiveModel);
  const isClaudeModel = CLAUDE_MODELS.includes(effectiveModel);

  useEffect(() => {
    if (config) {
      setModel(config.model);
      setTemperature(config.temperature);
      setMaxTokens(config.max_tokens);
      setCustomModel("");
    }
  }, [config, agentKey]);

  const isDirty =
    effectiveModel !== config?.model ||
    temperature !== config?.temperature ||
    maxTokens !== config?.max_tokens;

  const saveMutation = useMutation({
    mutationFn: () =>
      llmApi.update(appId, agentKey, { model: effectiveModel, temperature, max_tokens: maxTokens }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-config", appId] });
      setCustomModel("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="px-4 py-3 bg-gray-50 border-b border-gray-100 space-y-2">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Model selector */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-xs font-medium text-gray-500 shrink-0">Model</span>
          <div className="relative flex-1 min-w-[160px] max-w-[260px]">
            <select
              value={isKnownModel ? model : "__custom__"}
              onChange={(e) => {
                if (e.target.value !== "__custom__") {
                  setModel(e.target.value);
                  setCustomModel("");
                } else {
                  setCustomModel(model);
                }
              }}
              className="w-full appearance-none pl-2.5 pr-7 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
            >
              <optgroup label="Anthropic Claude">
                {CLAUDE_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </optgroup>
              <optgroup label="OpenAI">
                {OPENAI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </optgroup>
              <option value="__custom__">Custom / Azure…</option>
            </select>
            <ChevronDown className="w-3 h-3 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
          <span className="text-[10px] text-gray-400 shrink-0">{isClaudeModel ? "Anthropic" : "OpenAI / Azure"}</span>
        </div>

        {/* Temperature */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-medium text-gray-500">Temp</span>
          <input
            type="range" min={0} max={1} step={0.1} value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-24 accent-violet-600"
          />
          <span className="text-xs font-semibold text-violet-700 w-6">{temperature.toFixed(1)}</span>
        </div>

        {/* Max tokens */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-medium text-gray-500">Tokens</span>
          <input
            type="number" min={256} max={32000} step={256} value={maxTokens}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-20 px-2 py-1 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
          />
        </div>

        {/* Save */}
        <button
          onClick={() => saveMutation.mutate()}
          disabled={!isDirty || saveMutation.isPending}
          className={cn(
            "flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors shrink-0",
            saved
              ? "bg-green-500 text-white"
              : isDirty
              ? "bg-violet-600 text-white hover:bg-violet-700"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          )}
        >
          {saved ? <Check className="w-3 h-3" /> : <Save className="w-3 h-3" />}
          {saveMutation.isPending ? "Saving…" : saved ? "Saved!" : "Save Model"}
        </button>
      </div>

      {/* Custom model input */}
      {(!isKnownModel || customModel) && (
        <input
          type="text"
          value={customModel || (!isKnownModel ? model : "")}
          onChange={(e) => setCustomModel(e.target.value)}
          placeholder="deployment name or model ID"
          className="w-full max-w-sm px-2.5 py-1 text-xs border border-violet-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 font-mono placeholder:text-gray-300"
        />
      )}
    </div>
  );
}

// ── Filter Prompt Test Card ───────────────────────────────────────────────────

function FilterGenTestCard({ appId, currentPromptText, onRawResponse }: {
  appId: string;
  currentPromptText: string;
  onRawResponse: (raw: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [useDraft, setUseDraft] = useState(false);
  const [rawResponse, setRawResponse] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function handleRun() {
    if (!question.trim()) return;
    setIsRunning(true);
    setRawResponse(null);
    setError(null);
    try {
      const result = await evaluationApi.testFilterPrompt(appId, {
        question: question.trim(),
        prompt_text: useDraft ? currentPromptText : null,
      });
      if (result.error) {
        setError(result.error);
      } else if (result.raw_response != null) {
        setRawResponse(result.raw_response);
        onRawResponse(result.raw_response);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="bg-white border border-violet-200 rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-violet-100 bg-violet-50/40 flex items-center gap-3">
        <div className="w-7 h-7 rounded-md flex items-center justify-center bg-violet-100 text-violet-600">
          <FlaskConical className="w-4 h-4" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">Test Prompt</p>
          <p className="text-xs text-gray-400">Run a question through the Filter Generator and see the raw LLM response</p>
        </div>
      </div>

      <div className="p-5 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => { setQuestion(e.target.value); setRawResponse(null); setError(null); }}
            onKeyDown={(e) => { if (e.key === "Enter") handleRun(); }}
            placeholder="e.g. How do I create a Jira ticket?"
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          />
          <button
            type="button"
            onClick={handleRun}
            disabled={!question.trim() || isRunning}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg border transition-colors whitespace-nowrap",
              !question.trim() || isRunning
                ? "border-gray-200 text-gray-400 cursor-not-allowed bg-white"
                : "border-violet-300 text-violet-700 bg-violet-50 hover:bg-violet-100"
            )}
          >
            {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            Run
          </button>
        </div>

        <label className="flex items-center gap-2 cursor-pointer w-fit">
          <input
            type="checkbox"
            checked={useDraft}
            onChange={(e) => setUseDraft(e.target.checked)}
            className="accent-violet-600"
          />
          <span className="text-xs text-gray-600">Use current (unsaved) prompt text</span>
        </label>

        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg border border-red-200 bg-red-50">
            <AlertCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 shrink-0" />
            <pre className="text-xs text-red-700 font-mono whitespace-pre-wrap break-words">{error}</pre>
          </div>
        )}

        {rawResponse !== null && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              <span className="text-xs font-semibold text-green-700">Raw LLM response</span>
              <span className="ml-auto text-[11px] text-violet-500 flex items-center gap-1">
                <ArrowDown className="w-3 h-3" />
                Sent to mapper below
              </span>
            </div>
            <pre className="p-3 text-xs font-mono bg-gray-900 text-green-300 rounded-lg whitespace-pre-wrap break-words leading-5 max-h-48 overflow-y-auto">
              {rawResponse}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Response Mapper Card ──────────────────────────────────────────────────────

function MapperCard({ appId, prefillInput }: { appId: string; prefillInput?: string }) {
  const qc = useQueryClient();
  const [lang, setLang] = useState<"python" | "js">("python");
  const [code, setCode] = useState(MAPPER_PYTHON_STARTER);
  const [isConfigured, setIsConfigured] = useState(false);
  const [testInput, setTestInput] = useState("");
  const [testOutput, setTestOutput] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    promptsApi.getActive(appId, "filter_mapper").then((p) => {
      if (p?.prompt_text?.trim()) {
        try {
          const data = JSON.parse(p.prompt_text) as { lang?: string; code?: string };
          if ((data.lang === "python" || data.lang === "js") && data.code) {
            setLang(data.lang);
            setCode(data.code);
            setIsConfigured(true);
            return;
          }
        } catch (_) {}
      }
      setIsConfigured(false);
    }).catch(() => setIsConfigured(false));
  }, [appId]);

  useEffect(() => {
    if (prefillInput) {
      setTestInput(prefillInput);
      setTestOutput(null);
      setTestError(null);
    }
  }, [prefillInput]);

  const saveMutation = useMutation({
    mutationFn: () => promptsApi.update(appId, "filter_mapper", JSON.stringify({ lang, code })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      setIsConfigured(true);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => promptsApi.update(appId, "filter_mapper", ""),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts", appId] });
      setIsConfigured(false);
      setCode(lang === "python" ? MAPPER_PYTHON_STARTER : MAPPER_JS_STARTER);
    },
  });

  async function handleTest() {
    if (!testInput.trim()) return;
    setIsTesting(true);
    setTestOutput(null);
    setTestError(null);
    try {
      const result = await evaluationApi.testMapper(appId, { script: code, lang, llm_response: testInput });
      if (result.error) {
        setTestError(result.error);
      } else {
        setTestOutput(JSON.stringify(result.output, null, 2));
      }
    } catch (e: unknown) {
      setTestError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsTesting(false);
    }
  }

  return (
    <div className="bg-white border border-amber-200 rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-amber-100 flex items-center justify-between bg-amber-50/50">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md flex items-center justify-center bg-amber-100 text-amber-600">
            <Code2 className="w-4 h-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">Response Mapper Script</p>
            <p className="text-xs text-gray-400">Normalizes raw Filter Generator output to Kore.ai metaFilters at eval time</p>
          </div>
        </div>
        {isConfigured ? (
          <span className="text-[11px] px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">Active</span>
        ) : (
          <span className="text-[11px] px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">Not configured</span>
        )}
      </div>

      <div className="p-5 space-y-4">
        <p className="text-xs text-gray-500">
          Write a script to convert the Filter Generator's raw LLM output to metaFilter groups.
          Leave unconfigured to use strict-JSON mode (LLM must output <code>&#123;"metaFilters": [...]&#125;</code>).
        </p>

        {/* Language tabs */}
        <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg w-fit">
          {(["python", "js"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => {
                setLang(l);
                setCode(l === "python" ? MAPPER_PYTHON_STARTER : MAPPER_JS_STARTER);
                setTestOutput(null);
                setTestError(null);
              }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                lang === l ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              )}
            >
              <Code2 className="w-3.5 h-3.5" />
              {l === "python" ? "Python" : "JavaScript"}
            </button>
          ))}
        </div>

        {/* Code editor */}
        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 border-b border-gray-700">
            <span className="text-[11px] font-mono text-gray-400">
              {lang === "python" ? "map_response(response: str) → list[dict]" : "mapResponse(response: string) → object[]"}
            </span>
            <span className="ml-auto text-[10px] text-gray-500">input = raw LLM response text</span>
          </div>
          <textarea
            value={code}
            onChange={(e) => { setCode(e.target.value); setTestOutput(null); setTestError(null); }}
            rows={14}
            spellCheck={false}
            className="w-full px-4 py-3 text-xs font-mono bg-gray-900 text-green-300 focus:outline-none resize-none leading-5"
          />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
              saved ? "bg-green-500 text-white" : "bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
            )}
          >
            {saved ? <Check className="w-3 h-3" /> : <Save className="w-3 h-3" />}
            {saveMutation.isPending ? "Saving…" : saved ? "Saved!" : "Save Mapper"}
          </button>
          {isConfigured && (
            <button
              type="button"
              onClick={() => clearMutation.mutate()}
              disabled={clearMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <X className="w-3 h-3" />
              {clearMutation.isPending ? "Clearing…" : "Clear mapper"}
            </button>
          )}
        </div>

        {/* Test console */}
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
          <p className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
            <Play className="w-3.5 h-3.5 text-green-600" />
            Test mapper — paste a sample LLM response
          </p>
          <textarea
            value={testInput}
            onChange={(e) => { setTestInput(e.target.value); setTestOutput(null); setTestError(null); }}
            rows={4}
            placeholder={"Paste the raw LLM response here, e.g.:\n{\"source\": \"jiraServer\", \"reason\": \"question about tickets\"}\nor: Use the Jira connector for this query"}
            className="w-full px-3 py-2 text-xs font-mono border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
          />
          <button
            type="button"
            onClick={handleTest}
            disabled={!testInput.trim() || isTesting}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border transition-colors",
              !testInput.trim() || isTesting
                ? "border-gray-200 text-gray-400 cursor-not-allowed bg-white"
                : "border-green-300 text-green-700 bg-green-50 hover:bg-green-100"
            )}
          >
            {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            Run mapper
          </button>

          {(testOutput !== null || testError !== null) && (
            <div className={cn(
              "rounded-lg border p-3",
              testError ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50"
            )}>
              <div className="flex items-center gap-1.5 mb-1.5">
                {testError
                  ? <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                  : <CheckCircle className="w-3.5 h-3.5 text-green-600" />}
                <span className={cn(
                  "text-[11px] font-semibold",
                  testError ? "text-red-700" : "text-green-700"
                )}>
                  {testError ? "Error" : "Mapped metaFilters"}
                </span>
              </div>
              <pre className={cn(
                "text-[11px] font-mono whitespace-pre-wrap break-words leading-relaxed",
                testError ? "text-red-700" : "text-green-800"
              )}>
                {testError ?? testOutput}
              </pre>
            </div>
          )}

          <p className="text-[11px] text-gray-400">
            Both <code>[&#123;field, value&#125;]</code> and full Kore.ai format are accepted — simple format is auto-promoted.
            {lang === "js" ? " JS runs via Node.js on the backend." : " Python runs on the backend."}
          </p>
        </div>
      </div>
    </div>
  );
}
