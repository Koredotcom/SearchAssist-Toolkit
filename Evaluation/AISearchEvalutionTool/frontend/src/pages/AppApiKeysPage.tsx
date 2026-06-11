import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { appApiKeysApi } from "@/lib/api";
import type { AppApiKeysUpdate } from "@/lib/api";
import {
  CheckCircle, XCircle, Eye, EyeOff, Loader2, Send,
  Link as LinkIcon, Terminal, ChevronDown, ChevronUp,
  AlertCircle, ArrowRight, Check, Save,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  CLAUDE_MODELS, OPENAI_MODELS, GEMINI_MODELS,
  CUSTOM_VALUE, AZURE_MODEL, isKnownModel, isAzureModel, providerLabel,
} from "@/lib/models";

// ── cURL parser ──────────────────────────────────────────────────────────────

type Provider = "anthropic" | "openai" | "gemini";
type CurlResult = { provider: Provider | null; apiKey: string; baseUrl: string; error: string | null };

function parseCurl(raw: string): CurlResult {
  const s = raw.replace(/\\\s*\n/g, " ").replace(/\r?\n/g, " ");
  const urlMatch = s.match(/curl\s[^|]*?(https?:\/\/[^\s'"]+)/i);
  const rawUrl = urlMatch?.[1]?.replace(/['"]/g, "") ?? "";
  const headers: Record<string, string> = {};
  const hRe = /(?:-H|--header)\s+['"]([^'"]+)['"]/gi;
  let m: RegExpExecArray | null;
  while ((m = hRe.exec(s)) !== null) {
    const c = m[1].indexOf(":");
    if (c > -1) headers[m[1].slice(0, c).trim().toLowerCase()] = m[1].slice(c + 1).trim();
  }
  let apiKey = "";
  if (headers["authorization"]?.toLowerCase().startsWith("bearer ")) apiKey = headers["authorization"].slice(7).trim();
  else if (headers["api-key"]) apiKey = headers["api-key"].trim();
  else if (headers["x-api-key"]) apiKey = headers["x-api-key"].trim();
  else if (headers["x-goog-api-key"]) apiKey = headers["x-goog-api-key"].trim();
  if (!apiKey) return { provider: null, apiKey: "", baseUrl: "", error: "No API key found (Authorization: Bearer, api-key, x-api-key, or x-goog-api-key)" };
  let provider: Provider | null = null;
  let baseUrl = "";
  try {
    const p = new URL(rawUrl);
    const host = p.hostname.toLowerCase();
    if (host.includes("anthropic.com") || apiKey.startsWith("sk-ant-") || "anthropic-version" in headers) {
      provider = "anthropic";
      if (!host.includes("api.anthropic.com")) baseUrl = `${p.protocol}//${p.host}`;
    } else if (host.includes("generativelanguage.googleapis.com")) {
      provider = "gemini";
      const modelsIndex = p.pathname.indexOf("/models/");
      baseUrl = modelsIndex > -1 ? `${p.protocol}//${p.host}${p.pathname.slice(0, modelsIndex)}` : `${p.protocol}//${p.host}`;
      if (baseUrl === "https://generativelanguage.googleapis.com/v1beta") baseUrl = "";
    } else {
      provider = "openai";
      const isAzure = host.endsWith(".openai.azure.com") || host.endsWith(".cognitiveservices.azure.com") || p.pathname.includes("/openai/deployments/");
      if (isAzure) { baseUrl = rawUrl; }
      else if (!host.includes("api.openai.com")) {
        const v1 = p.pathname.indexOf("/v1");
        baseUrl = v1 > -1 ? `${p.protocol}//${p.host}${p.pathname.slice(0, v1 + 3)}` : `${p.protocol}//${p.host}`;
      }
    }
  } catch { return { provider: null, apiKey, baseUrl: "", error: "Could not parse URL from the cURL command." }; }
  return { provider, apiKey, baseUrl, error: null };
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AppApiKeysPage() {
  const { appId } = useParams<{ appId: string }>();
  const qc = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["app-api-keys", appId],
    queryFn: () => appApiKeysApi.get(appId!),
    enabled: !!appId,
  });

  const [anthropicKey, setAnthropicKey] = useState("");
  const [anthropicUrl, setAnthropicUrl] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiUrl, setOpenaiUrl] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [geminiUrl, setGeminiUrl] = useState("");

  const [showAnthropic, setShowAnthropic] = useState(false);
  const [showOpenai, setShowOpenai] = useState(false);
  const [showGemini, setShowGemini] = useState(false);
  const [anthropicTest, setAnthropicTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [openaiTest, setOpenaiTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [geminiTest, setGeminiTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [curlOpen, setCurlOpen] = useState(false);
  const [curlRaw, setCurlRaw] = useState("");
  const [curlResult, setCurlResult] = useState<CurlResult | null>(null);
  const [anthropicSaved, setAnthropicSaved] = useState(false);
  const [openaiSaved, setOpenaiSaved] = useState(false);
  const [geminiSaved, setGeminiSaved] = useState(false);

  const [azureKey, setAzureKey] = useState("");
  const [azureEndpoint, setAzureEndpoint] = useState("");
  const [azureDeployment, setAzureDeployment] = useState("");
  const [azureApiVersion, setAzureApiVersion] = useState("");
  const [showAzure, setShowAzure] = useState(false);
  const [azureTest, setAzureTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [azureSaved, setAzureSaved] = useState(false);

  const [defaultModel, setDefaultModel] = useState("");
  const [customDefault, setCustomDefault] = useState("");
  const [defaultKind, setDefaultKind] = useState<"" | "custom">("");
  const [defaultSaved, setDefaultSaved] = useState(false);

  useEffect(() => {
    if (status) {
      setAnthropicUrl(status.anthropic_base_url || "");
      setOpenaiUrl(status.openai_base_url || "");
      setGeminiUrl(status.gemini_base_url || "");
      setAzureEndpoint(status.azure_endpoint || "");
      setAzureDeployment(status.azure_deployment || "");
      setAzureApiVersion(status.azure_api_version || "");
      setDefaultModel(status.default_model || "");
      setCustomDefault("");
      setDefaultKind("");
    }
  }, [status]);

  const effDefault = customDefault.trim() || defaultModel;
  const defaultKnown = isKnownModel(effDefault) || isAzureModel(effDefault);
  const defaultSelectValue = defaultKind ? CUSTOM_VALUE : defaultKnown ? defaultModel : effDefault ? CUSTOM_VALUE : "";
  const showDefaultInput = defaultKind === "custom" || (!defaultKnown && !!effDefault);
  const defaultDirty = effDefault !== (status?.default_model ?? "");

  const saveDefaultModel = useMutation({
    mutationFn: () => appApiKeysApi.set(appId!, { default_model: effDefault }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setDefaultSaved(true); setTimeout(() => setDefaultSaved(false), 2000); },
  });

  const saveAnthropic = useMutation({
    mutationFn: () => {
      const body: AppApiKeysUpdate = {};
      if (anthropicKey.trim()) body.anthropic_key = anthropicKey.trim();
      if (anthropicUrl !== (status?.anthropic_base_url ?? "")) body.anthropic_base_url = anthropicUrl.trim();
      return appApiKeysApi.set(appId!, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setAnthropicKey(""); setAnthropicSaved(true); setTimeout(() => setAnthropicSaved(false), 2000); },
  });

  const saveOpenai = useMutation({
    mutationFn: () => {
      const body: AppApiKeysUpdate = {};
      if (openaiKey.trim()) body.openai_key = openaiKey.trim();
      if (openaiUrl !== (status?.openai_base_url ?? "")) body.openai_base_url = openaiUrl.trim();
      return appApiKeysApi.set(appId!, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setOpenaiKey(""); setOpenaiSaved(true); setTimeout(() => setOpenaiSaved(false), 2000); },
  });

  const saveGemini = useMutation({
    mutationFn: () => {
      const body: AppApiKeysUpdate = {};
      if (geminiKey.trim()) body.gemini_key = geminiKey.trim();
      if (geminiUrl !== (status?.gemini_base_url ?? "")) body.gemini_base_url = geminiUrl.trim();
      return appApiKeysApi.set(appId!, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setGeminiKey(""); setGeminiSaved(true); setTimeout(() => setGeminiSaved(false), 2000); },
  });

  const testAnthropicMutation = useMutation({
    mutationFn: () => appApiKeysApi.testAnthropic(appId!, anthropicKey.trim() || undefined, anthropicUrl.trim() || undefined),
    onSuccess: (d) => setAnthropicTest(d),
    onError: (e: { response?: { data?: { detail?: string } } }) => setAnthropicTest({ ok: false, response: e.response?.data?.detail ?? "Test failed" }),
  });

  const testOpenaiMutation = useMutation({
    mutationFn: () => appApiKeysApi.testOpenAI(appId!, openaiKey.trim() || undefined, openaiUrl.trim() || undefined),
    onSuccess: (d) => setOpenaiTest(d),
    onError: (e: { response?: { data?: { detail?: string } } }) => setOpenaiTest({ ok: false, response: e.response?.data?.detail ?? "Test failed" }),
  });

  const testGeminiMutation = useMutation({
    mutationFn: () => appApiKeysApi.testGemini(appId!, geminiKey.trim() || undefined, geminiUrl.trim() || undefined),
    onSuccess: (d) => setGeminiTest(d),
    onError: (e: { response?: { data?: { detail?: string } } }) => setGeminiTest({ ok: false, response: e.response?.data?.detail ?? "Test failed" }),
  });

  const saveAzure = useMutation({
    mutationFn: () => {
      const body: AppApiKeysUpdate = {};
      if (azureKey.trim()) body.azure_key = azureKey.trim();
      if (azureEndpoint !== (status?.azure_endpoint ?? "")) body.azure_endpoint = azureEndpoint.trim();
      if (azureDeployment !== (status?.azure_deployment ?? "")) body.azure_deployment = azureDeployment.trim();
      if (azureApiVersion !== (status?.azure_api_version ?? "")) body.azure_api_version = azureApiVersion.trim();
      return appApiKeysApi.set(appId!, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setAzureKey(""); setAzureSaved(true); setTimeout(() => setAzureSaved(false), 2000); },
  });

  const testAzureMutation = useMutation({
    mutationFn: () => appApiKeysApi.testAzure(appId!, {
      key: azureKey.trim() || undefined,
      endpoint: azureEndpoint.trim(),
      deployment: azureDeployment.trim(),
      api_version: azureApiVersion.trim(),
    }),
    onSuccess: (d) => setAzureTest(d),
    onError: (e: { response?: { data?: { detail?: string } } }) => setAzureTest({ ok: false, response: e.response?.data?.detail ?? "Test failed" }),
  });

  function applyCurl(r: CurlResult) {
    if (r.error) return;
    if (r.provider === "anthropic") { setAnthropicKey(r.apiKey); if (r.baseUrl) setAnthropicUrl(r.baseUrl); setAnthropicTest(null); }
    else if (r.provider === "gemini") { setGeminiKey(r.apiKey); if (r.baseUrl) setGeminiUrl(r.baseUrl); setGeminiTest(null); }
    else { setOpenaiKey(r.apiKey); if (r.baseUrl) setOpenaiUrl(r.baseUrl); setOpenaiTest(null); }
    setCurlOpen(false); setCurlRaw(""); setCurlResult(null);
  }

  const anthropicDirty = anthropicKey.trim() || anthropicUrl !== (status?.anthropic_base_url ?? "");
  const openaiDirty = openaiKey.trim() || openaiUrl !== (status?.openai_base_url ?? "");
  const geminiDirty = geminiKey.trim() || geminiUrl !== (status?.gemini_base_url ?? "");
  const azureDirty = azureKey.trim()
    || azureEndpoint !== (status?.azure_endpoint ?? "")
    || azureDeployment !== (status?.azure_deployment ?? "")
    || azureApiVersion !== (status?.azure_api_version ?? "");
  const canTestAnthropic = !!(anthropicKey.trim() || status?.anthropic_key_set);
  const canTestOpenai = !!(openaiKey.trim() || status?.openai_key_set);
  const canTestGemini = !!(geminiKey.trim() || status?.gemini_key_set);
  const canTestAzure = !!((azureKey.trim() || status?.azure_key_set) && azureEndpoint.trim() && azureDeployment.trim());

  if (isLoading) return <div className="text-center py-16 text-gray-400">Loading...</div>;

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
        <p className="text-sm text-gray-500 mt-1">Set keys for Anthropic, OpenAI, Gemini, and Azure OpenAI. You can test before saving.</p>
      </div>

      {/* Default model — the LLM every agent inherits unless overridden */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Default model</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              The LLM every agent uses unless overridden on the LLM Config / Prompts pages.
              For Azure, enter the deployment name here and set the Azure endpoint on the OpenAI row below.
            </p>
          </div>
          {effDefault && <span className="text-xs text-gray-400 shrink-0 mt-0.5">{providerLabel(effDefault)}</span>}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative">
            <select
              value={defaultSelectValue}
              onChange={(e) => {
                const v = e.target.value;
                if (v === CUSTOM_VALUE) {
                  setDefaultKind("custom");
                  setCustomDefault(customDefault || (defaultKnown ? "" : defaultModel));
                } else {
                  setDefaultKind("");
                  setDefaultModel(v);
                  setCustomDefault("");
                }
              }}
              className="appearance-none pl-3 pr-8 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white min-w-[220px]"
            >
              <option value="">None — built-in per-agent defaults</option>
              <option value={AZURE_MODEL}>Azure OpenAI (configured below)</option>
              <optgroup label="Anthropic Claude">
                {CLAUDE_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </optgroup>
              <optgroup label="OpenAI">
                {OPENAI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </optgroup>
              <optgroup label="Google Gemini">
                {GEMINI_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </optgroup>
              <option value={CUSTOM_VALUE}>Custom…</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
          {showDefaultInput && (
            <input
              type="text"
              value={customDefault || (!defaultKnown ? defaultModel : "")}
              onChange={(e) => setCustomDefault(e.target.value)}
              placeholder="model ID or Azure deployment name"
              className="px-3 py-2 text-sm border border-violet-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 font-mono placeholder:text-gray-300 min-w-[220px]"
            />
          )}
          <button
            onClick={() => saveDefaultModel.mutate()}
            disabled={!defaultDirty || saveDefaultModel.isPending}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
              defaultSaved ? "bg-green-500 text-white"
                : defaultDirty ? "bg-violet-600 text-white hover:bg-violet-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed"
            )}
          >
            {defaultSaved ? <Check className="w-3.5 h-3.5" /> : saveDefaultModel.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saveDefaultModel.isPending ? "Saving…" : defaultSaved ? "Saved!" : "Save"}
          </button>
        </div>
      </div>

      {/* cURL import */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <button onClick={() => setCurlOpen((v) => !v)}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
        >
          <Terminal className="w-4 h-4 text-gray-500 shrink-0" />
          <span className="text-sm text-gray-700 flex-1">Import from cURL</span>
          {curlOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </button>
        {curlOpen && (
          <div className="border-t border-gray-100 p-4 bg-gray-50 space-y-3">
            <textarea value={curlRaw} onChange={(e) => { setCurlRaw(e.target.value); setCurlResult(null); }} rows={4} spellCheck={false}
              placeholder={`curl https://api.openai.com/v1/chat/completions \\\n  -H "Authorization: Bearer sk-..." \\\n  -d '{...}'`}
              className="w-full px-3 py-2 text-xs font-mono border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white placeholder:text-gray-300 resize-none"
            />
            <div className="flex items-center gap-2">
              <button onClick={() => setCurlResult(parseCurl(curlRaw.trim()))} disabled={!curlRaw.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40"
              >
                <Terminal className="w-3.5 h-3.5" /> Parse
              </button>
              {curlResult && <button onClick={() => { setCurlRaw(""); setCurlResult(null); }} className="text-xs text-gray-400 hover:text-gray-600">Clear</button>}
            </div>
            {curlResult && (
              <div className={cn("rounded-lg border p-3 text-xs space-y-2", curlResult.error ? "bg-red-50 border-red-200" : "bg-green-50 border-green-200")}>
                {curlResult.error ? (
                  <div className="flex items-start gap-2 text-red-700"><AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{curlResult.error}</div>
                ) : (
                  <>
                    <div className="flex items-center gap-1.5 text-green-700 font-semibold">
                      <CheckCircle className="w-3.5 h-3.5" /> {curlResult.provider === "anthropic" ? "Anthropic" : curlResult.provider === "gemini" ? "Gemini" : "OpenAI / compatible"}
                    </div>
                    <div className="space-y-1 text-gray-700">
                      <p><span className="text-gray-400 mr-2">Key</span><span className="font-mono">{curlResult.apiKey.slice(0, 10)}{"•".repeat(8)}</span></p>
                      <p><span className="text-gray-400 mr-2">URL</span><span className="font-mono">{curlResult.baseUrl || <em className="not-italic text-gray-400">default</em>}</span></p>
                    </div>
                    <button onClick={() => applyCurl(curlResult)}
                      className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700"
                    >
                      <ArrowRight className="w-3.5 h-3.5" /> Apply to {curlResult.provider === "anthropic" ? "Anthropic" : curlResult.provider === "gemini" ? "Gemini" : "OpenAI"}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Provider rows */}
      <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100 overflow-hidden">
        <ProviderRow
          label="Anthropic"
          hint="Agents 1–3 (generation)"
          isSet={status?.anthropic_key_set ?? false}
          preview={status?.anthropic_key_preview ?? ""}
          keyValue={anthropicKey}
          urlValue={anthropicUrl}
          urlPlaceholder="https://api.anthropic.com"
          keyPlaceholder="sk-ant-api03-..."
          show={showAnthropic}
          onToggleShow={() => setShowAnthropic((v) => !v)}
          onKeyChange={(v) => { setAnthropicKey(v); setAnthropicTest(null); }}
          onUrlChange={(v) => { setAnthropicUrl(v); setAnthropicTest(null); }}
          isDirty={!!anthropicDirty}
          isSaving={saveAnthropic.isPending}
          saved={anthropicSaved}
          onSave={() => saveAnthropic.mutate()}
          canTest={canTestAnthropic}
          isTesting={testAnthropicMutation.isPending}
          onTest={() => { setAnthropicTest(null); testAnthropicMutation.mutate(); }}
          testResult={anthropicTest}
        />
        <ProviderRow
          label="OpenAI"
          hint="Judge (evaluation)"
          isSet={status?.openai_key_set ?? false}
          preview={status?.openai_key_preview ?? ""}
          keyValue={openaiKey}
          urlValue={openaiUrl}
          urlPlaceholder="https://api.openai.com/v1"
          keyPlaceholder="sk-..."
          show={showOpenai}
          onToggleShow={() => setShowOpenai((v) => !v)}
          onKeyChange={(v) => { setOpenaiKey(v); setOpenaiTest(null); }}
          onUrlChange={(v) => { setOpenaiUrl(v); setOpenaiTest(null); }}
          isDirty={!!openaiDirty}
          isSaving={saveOpenai.isPending}
          saved={openaiSaved}
          onSave={() => saveOpenai.mutate()}
          canTest={canTestOpenai}
          isTesting={testOpenaiMutation.isPending}
          onTest={() => { setOpenaiTest(null); testOpenaiMutation.mutate(); }}
          testResult={openaiTest}
        />
        <ProviderRow
          label="Gemini"
          hint="Generation, judge, or insights"
          isSet={status?.gemini_key_set ?? false}
          preview={status?.gemini_key_preview ?? ""}
          keyValue={geminiKey}
          urlValue={geminiUrl}
          urlPlaceholder="https://generativelanguage.googleapis.com/v1beta"
          keyPlaceholder="AIza..."
          show={showGemini}
          onToggleShow={() => setShowGemini((v) => !v)}
          onKeyChange={(v) => { setGeminiKey(v); setGeminiTest(null); }}
          onUrlChange={(v) => { setGeminiUrl(v); setGeminiTest(null); }}
          isDirty={!!geminiDirty}
          isSaving={saveGemini.isPending}
          saved={geminiSaved}
          onSave={() => saveGemini.mutate()}
          canTest={canTestGemini}
          isTesting={testGeminiMutation.isPending}
          onTest={() => { setGeminiTest(null); testGeminiMutation.mutate(); }}
          testResult={geminiTest}
        />
        <AzureRow
          isSet={status?.azure_key_set ?? false}
          preview={status?.azure_key_preview ?? ""}
          keyValue={azureKey}
          endpoint={azureEndpoint}
          deployment={azureDeployment}
          apiVersion={azureApiVersion}
          show={showAzure}
          onToggleShow={() => setShowAzure((v) => !v)}
          onKeyChange={(v) => { setAzureKey(v); setAzureTest(null); }}
          onEndpointChange={(v) => { setAzureEndpoint(v); setAzureTest(null); }}
          onDeploymentChange={(v) => { setAzureDeployment(v); setAzureTest(null); }}
          onApiVersionChange={(v) => { setAzureApiVersion(v); setAzureTest(null); }}
          isDirty={!!azureDirty}
          isSaving={saveAzure.isPending}
          saved={azureSaved}
          onSave={() => saveAzure.mutate()}
          canTest={canTestAzure}
          isTesting={testAzureMutation.isPending}
          onTest={() => { setAzureTest(null); testAzureMutation.mutate(); }}
          testResult={azureTest}
        />
      </div>

    </div>
  );
}

// ── Provider row ──────────────────────────────────────────────────────────────

function ProviderRow({
  label, hint, isSet, preview,
  keyValue, urlValue, urlPlaceholder, keyPlaceholder,
  show, onToggleShow, onKeyChange, onUrlChange,
  isDirty, isSaving, saved, onSave,
  canTest, isTesting, onTest, testResult,
}: {
  label: string; hint: string; isSet: boolean; preview: string;
  keyValue: string; urlValue: string; urlPlaceholder: string; keyPlaceholder: string;
  show: boolean; onToggleShow: () => void; onKeyChange: (v: string) => void; onUrlChange: (v: string) => void;
  isDirty: boolean; isSaving: boolean; saved: boolean; onSave: () => void;
  canTest: boolean; isTesting: boolean; onTest: () => void;
  testResult: { ok: boolean; response: string } | null;
}) {
  return (
    <div className="p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900">{label}</span>
          <span className="text-xs text-gray-400">{hint}</span>
          {isSet
            ? <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" />Set</span>
            : <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full"><XCircle className="w-3 h-3" />Not set</span>
          }
          {isSet && preview && <span className="text-xs font-mono text-gray-400">{preview}</span>}
        </div>
      </div>

      {/* Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="relative">
          <input type={show ? "text" : "password"} value={keyValue} onChange={(e) => onKeyChange(e.target.value)}
            placeholder={isSet ? "Enter new key to replace" : keyPlaceholder}
            className="w-full px-3 py-2 pr-9 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
          />
          <button type="button" onClick={onToggleShow} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        <div className="relative">
          <input type="url" value={urlValue} onChange={(e) => onUrlChange(e.target.value)} placeholder={urlPlaceholder}
            className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
          />
          <LinkIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
          {urlValue && (
            <button type="button" onClick={() => onUrlChange("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-gray-600">✕</button>
          )}
        </div>
      </div>

      {/* Actions row */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={onTest} disabled={isTesting || !canTest}
          title={!canTest ? "Enter a key first" : "Test the current key (uses typed value if present)"}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors",
            canTest ? "border-gray-200 text-gray-600 hover:bg-gray-50" : "border-gray-100 text-gray-300 cursor-not-allowed"
          )}
        >
          {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          {isTesting ? "Testing…" : "Test"}
        </button>

        <button onClick={onSave} disabled={!isDirty || isSaving}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
            saved ? "bg-green-500 text-white"
              : isDirty ? "bg-violet-600 text-white hover:bg-violet-700"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          )}
        >
          {saved ? <Check className="w-3.5 h-3.5" /> : isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          {isSaving ? "Saving…" : saved ? "Saved!" : "Save"}
        </button>

        {testResult && (
          <div className={cn("flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg", testResult.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600")}>
            {testResult.ok ? <CheckCircle className="w-3.5 h-3.5 shrink-0" /> : <XCircle className="w-3.5 h-3.5 shrink-0" />}
            <span className="font-mono">{testResult.response}</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Azure OpenAI row (key + endpoint + deployment + api version) ───────────────

function AzureRow({
  isSet, preview, keyValue, endpoint, deployment, apiVersion,
  show, onToggleShow, onKeyChange, onEndpointChange, onDeploymentChange, onApiVersionChange,
  isDirty, isSaving, saved, onSave, canTest, isTesting, onTest, testResult,
}: {
  isSet: boolean; preview: string;
  keyValue: string; endpoint: string; deployment: string; apiVersion: string;
  show: boolean; onToggleShow: () => void;
  onKeyChange: (v: string) => void; onEndpointChange: (v: string) => void;
  onDeploymentChange: (v: string) => void; onApiVersionChange: (v: string) => void;
  isDirty: boolean; isSaving: boolean; saved: boolean; onSave: () => void;
  canTest: boolean; isTesting: boolean; onTest: () => void;
  testResult: { ok: boolean; response: string } | null;
}) {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-gray-900">Azure OpenAI</span>
        <span className="text-xs text-gray-400">Agents set to “Azure OpenAI”</span>
        {isSet
          ? <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" />Set</span>
          : <span className="flex items-center gap-1 text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full"><XCircle className="w-3 h-3" />Not set</span>
        }
        {isSet && preview && <span className="text-xs font-mono text-gray-400">{preview}</span>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* API key */}
        <div className="relative">
          <input type={show ? "text" : "password"} value={keyValue} onChange={(e) => onKeyChange(e.target.value)}
            placeholder={isSet ? "Enter new key to replace" : "Azure API key"}
            className="w-full px-3 py-2 pr-9 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
          />
          <button type="button" onClick={onToggleShow} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        {/* Endpoint */}
        <div className="relative">
          <input type="url" value={endpoint} onChange={(e) => onEndpointChange(e.target.value)}
            placeholder="https://<resource>.openai.azure.com"
            className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
          />
          <LinkIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
        </div>
        {/* Deployment */}
        <input type="text" value={deployment} onChange={(e) => onDeploymentChange(e.target.value)}
          placeholder="deployment name (e.g. gpt-4o)"
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
        />
        {/* API version */}
        <input type="text" value={apiVersion} onChange={(e) => onApiVersionChange(e.target.value)}
          placeholder="api version (default 2024-02-01)"
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500 placeholder:text-gray-300 font-mono"
        />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={onTest} disabled={isTesting || !canTest}
          title={!canTest ? "Enter key, endpoint, and deployment first" : "Test the Azure deployment"}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors",
            canTest ? "border-gray-200 text-gray-600 hover:bg-gray-50" : "border-gray-100 text-gray-300 cursor-not-allowed"
          )}
        >
          {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          {isTesting ? "Testing…" : "Test"}
        </button>

        <button onClick={onSave} disabled={!isDirty || isSaving}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
            saved ? "bg-green-500 text-white"
              : isDirty ? "bg-violet-600 text-white hover:bg-violet-700"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          )}
        >
          {saved ? <Check className="w-3.5 h-3.5" /> : isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          {isSaving ? "Saving…" : saved ? "Saved!" : "Save"}
        </button>

        {testResult && (
          <div className={cn("flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg", testResult.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600")}>
            {testResult.ok ? <CheckCircle className="w-3.5 h-3.5 shrink-0" /> : <XCircle className="w-3.5 h-3.5 shrink-0" />}
            <span className="font-mono">{testResult.response}</span>
          </div>
        )}
      </div>
    </div>
  );
}

