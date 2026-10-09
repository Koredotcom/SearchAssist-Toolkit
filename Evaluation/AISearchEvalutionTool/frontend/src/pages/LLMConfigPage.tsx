import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { llmApi, appsApi } from "@/lib/api";
import type { LLMConfig } from "@/lib/api";
import { Save, ShieldAlert, X, Plus, Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { FEATURE_AI_DEEP_DIVE } from "@/lib/featureFlags";

const GENERATION_AGENTS = [
  { key: "agent1", tag: "A1", label: "Summarizer", description: "Extracts facts from documents" },
  { key: "agent2", tag: "A2", label: "Generator", description: "Creates Q&A test cases" },
  { key: "agent3", tag: "A3", label: "Ranker", description: "Scores and filters test cases" },
];

const EVALUATION_AGENTS = [
  { key: "judge", tag: "J", label: "Judge", description: "Scores RAG responses" },
  { key: "filter_generator", tag: "F", label: "Filter Generator", description: "Builds search filters" },
];

const INSIGHTS_AGENTS = [
  {
    key: "insights",
    tag: "I",
    label: "AI Deep Dive",
    description: "Writes the markdown root-cause narrative for an evaluation run",
  },
];

const CLAUDE_MODELS = [
  "claude-opus-4-7",
  "claude-sonnet-4-6",
  "claude-haiku-4-5-20251001",
];

const OPENAI_MODELS = [
  "gpt-4.1",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4o-mini",
  "gpt-5",
  "gpt-5-mini",
  "o3",
  "o3-mini",
  "o4-mini",
];

const GEMINI_MODELS = [
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-1.5-pro",
  "gemini-1.5-flash",
];

export default function LLMConfigPage() {
  const { appId } = useParams<{ appId: string }>();
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ["llm-config", appId],
    queryFn: () => llmApi.list(appId!),
    enabled: !!appId,
  });

  if (isLoading) {
    return <div className="text-center py-16 text-gray-400">Loading LLM config...</div>;
  }

  const getConfig = (key: string) => configs.find((c) => c.agent_name === key);

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">LLM Config</h1>
        <p className="text-sm text-gray-500 mt-1">
          Choose a model for each agent. Click any row to edit its settings.
        </p>
      </div>

      {/* Generation Pipeline */}
      <section>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-violet-600">Generation Pipeline</span>
          <span className="text-xs text-gray-400">— runs when you generate a golden set</span>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
          {GENERATION_AGENTS.map((agent) => (
            <AgentRow
              key={agent.key}
              appId={appId!}
              agent={agent}
              config={getConfig(agent.key)}
              tagColor="violet"
              isExpanded={expandedAgent === agent.key}
              onToggle={() => setExpandedAgent(expandedAgent === agent.key ? null : agent.key)}
            />
          ))}
        </div>
      </section>

      {/* Evaluation */}
      <section>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-amber-600">Evaluation</span>
          <span className="text-xs text-gray-400">— runs during evaluation runs</span>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
          {EVALUATION_AGENTS.map((agent) => (
            <AgentRow
              key={agent.key}
              appId={appId!}
              agent={agent}
              config={getConfig(agent.key)}
              tagColor="amber"
              isExpanded={expandedAgent === agent.key}
              onToggle={() => setExpandedAgent(expandedAgent === agent.key ? null : agent.key)}
            />
          ))}
        </div>
      </section>

      {/* Insights — AI Deep Dive narrative.
          Gated by FEATURE_AI_DEEP_DIVE; the agent row + prompt + backend code
          all remain seeded so toggling this flag back on is the only step. */}
      {FEATURE_AI_DEEP_DIVE && (
        <section>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-teal-600">Insights</span>
            <span className="text-xs text-gray-400">— runs on demand from the Run Detail page</span>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
            {INSIGHTS_AGENTS.map((agent) => (
              <AgentRow
                key={agent.key}
                appId={appId!}
                agent={agent}
                config={getConfig(agent.key)}
                tagColor="teal"
                isExpanded={expandedAgent === agent.key}
                onToggle={() => setExpandedAgent(expandedAgent === agent.key ? null : agent.key)}
              />
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1.5 px-1">
            Reasoning models (o-series, gpt-5) need ≥ 8000 max tokens — thinking tokens
            consume the budget before any visible output is emitted.
          </p>
        </section>
      )}

      {/* Banned Topics */}
      <BannedTopicsCard appId={appId!} />
    </div>
  );
}

function AgentRow({
  appId,
  agent,
  config,
  tagColor,
  isExpanded,
  onToggle,
}: {
  appId: string;
  agent: { key: string; tag: string; label: string; description: string };
  config: LLMConfig | undefined;
  tagColor: "violet" | "amber" | "teal";
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const qc = useQueryClient();
  const [model, setModel] = useState(config?.model ?? "claude-sonnet-4-6");
  const [customModel, setCustomModel] = useState("");
  const [temperature, setTemperature] = useState(config?.temperature ?? 0);
  const [maxTokens, setMaxTokens] = useState(config?.max_tokens ?? 4096);
  const [saved, setSaved] = useState(false);

  const effectiveModel = customModel.trim() || model;
  const isKnownModel = CLAUDE_MODELS.includes(effectiveModel) || OPENAI_MODELS.includes(effectiveModel) || GEMINI_MODELS.includes(effectiveModel);
  const isClaudeModel = CLAUDE_MODELS.includes(effectiveModel);
  const isGeminiModel = GEMINI_MODELS.includes(effectiveModel) || effectiveModel.startsWith("gemini-") || effectiveModel.startsWith("models/gemini-");

  useEffect(() => {
    if (config) {
      setModel(config.model);
      setTemperature(config.temperature);
      setMaxTokens(config.max_tokens);
      setCustomModel("");
    }
  }, [config]);

  const isDirty =
    effectiveModel !== config?.model ||
    temperature !== config?.temperature ||
    maxTokens !== config?.max_tokens;

  const saveMutation = useMutation({
    mutationFn: () =>
      llmApi.update(appId, agent.key, { model: effectiveModel, temperature, max_tokens: maxTokens }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm-config", appId] });
      setCustomModel("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const tagCls =
    tagColor === "violet" ? "bg-violet-100 text-violet-700" :
    tagColor === "amber"  ? "bg-amber-100 text-amber-700" :
                            "bg-teal-100 text-teal-700";

  const displayModel = config?.model ?? "—";
  const shortModel = displayModel.length > 28 ? displayModel.slice(0, 26) + "…" : displayModel;

  return (
    <div>
      {/* Summary row — always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors text-left"
      >
        <span className={cn("w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold shrink-0", tagCls)}>
          {agent.tag}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900">{agent.label}</p>
          <p className="text-xs text-gray-400">{agent.description}</p>
        </div>

        <div className="flex items-center gap-4 text-right shrink-0">
          {config?.model ? (
            <span className="text-xs font-mono text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
              {shortModel}
            </span>
          ) : (
            <span className="text-xs text-red-500 font-medium">Not configured</span>
          )}
          <span className={cn(
            "text-xs text-gray-400 transition-transform duration-200",
            isExpanded && "rotate-180"
          )}>
            <ChevronDown className="w-4 h-4" />
          </span>
        </div>
      </button>

      {/* Edit panel — expands inline */}
      {isExpanded && (
        <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Model */}
            <div className="sm:col-span-1">
              <label className="block text-xs font-medium text-gray-600 mb-1.5">Model</label>
              <div className="relative">
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
                  className="w-full appearance-none px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white pr-8"
                >
                  <optgroup label="Anthropic Claude">
                    {CLAUDE_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </optgroup>
                  <optgroup label="OpenAI">
                    {OPENAI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </optgroup>
                  <optgroup label="Google Gemini">
                    {GEMINI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </optgroup>
                  <option value="__custom__">Custom / Azure…</option>
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              {(!isKnownModel || customModel) && (
                <input
                  type="text"
                  value={customModel || (!isKnownModel ? model : "")}
                  onChange={(e) => setCustomModel(e.target.value)}
                  placeholder="deployment name or model ID"
                  className="mt-1.5 w-full px-3 py-1.5 text-sm border border-violet-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 font-mono placeholder:text-gray-300"
                />
              )}
              <p className="text-xs text-gray-400 mt-1">{isClaudeModel ? "Anthropic" : isGeminiModel ? "Gemini" : "OpenAI / Azure"}</p>
            </div>

            {/* Temperature */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                Temperature
                <span className="ml-2 font-semibold text-violet-700">{temperature.toFixed(1)}</span>
              </label>
              <input
                type="range"
                min={0} max={1} step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full accent-violet-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>

            {/* Max tokens */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">Max Tokens</label>
              <input
                type="number"
                min={256} max={32000} step={256}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
              />
              <p className="text-xs text-gray-400 mt-1">256 – 32,000</p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              onClick={onToggle}
              className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!isDirty || saveMutation.isPending}
              className={cn(
                "flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-colors",
                saved
                  ? "bg-green-500 text-white"
                  : isDirty
                  ? "bg-violet-600 text-white hover:bg-violet-700"
                  : "bg-gray-100 text-gray-400 cursor-not-allowed"
              )}
            >
              {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
              {saveMutation.isPending ? "Saving…" : saved ? "Saved!" : "Save"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function BannedTopicsCard({ appId }: { appId: string }) {
  const qc = useQueryClient();
  const { data: app } = useQuery({
    queryKey: ["app", appId],
    queryFn: () => appsApi.get(appId),
    enabled: !!appId,
  });

  const [topics, setTopics] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (app?.banned_topics) setTopics(app.banned_topics);
  }, [app?.banned_topics]);

  const updateMutation = useMutation({
    mutationFn: () => appsApi.update(appId, { banned_topics: topics }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["app", appId] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  function addTopic() {
    const t = input.trim();
    if (t && !topics.includes(t)) {
      setTopics([...topics, t]);
      setInput("");
    }
  }

  const isDirty =
    JSON.stringify(topics.slice().sort()) !== JSON.stringify((app?.banned_topics ?? []).slice().sort());

  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-red-500">Safety</span>
      </div>
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-md flex items-center justify-center bg-red-50 text-red-500">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Banned Topics</p>
              <p className="text-xs text-gray-400">
                The judge flags RAG answers that mention these topics
              </p>
            </div>
          </div>
          <button
            onClick={() => updateMutation.mutate()}
            disabled={!isDirty || updateMutation.isPending}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
              saved
                ? "bg-green-500 text-white"
                : isDirty
                ? "bg-violet-600 text-white hover:bg-violet-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed"
            )}
          >
            {saved ? <Check className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
            {updateMutation.isPending ? "Saving…" : saved ? "Saved!" : "Save"}
          </button>
        </div>

        <div className="p-5 space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTopic(); } }}
              placeholder="e.g. compensation, internal layoffs"
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
            <button
              onClick={addTopic}
              disabled={!input.trim()}
              className="flex items-center gap-1 px-3 py-2 text-sm font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              Add
            </button>
          </div>

          {topics.length === 0 ? (
            <p className="text-xs text-gray-400 italic">No banned topics — judge won't check for violations</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {topics.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs bg-red-50 text-red-700 border border-red-100 rounded-full"
                >
                  {t}
                  <button onClick={() => setTopics(topics.filter((x) => x !== t))} className="hover:text-red-900">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
