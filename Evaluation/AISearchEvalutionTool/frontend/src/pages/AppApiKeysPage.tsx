import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { appApiKeysApi } from "@/lib/api";
import type { AppApiKeysUpdate } from "@/lib/api";
import {
  CheckCircle, XCircle, Eye, EyeOff, Loader2, Send,
  Link as LinkIcon, Gauge, Terminal, ChevronDown, ChevronUp,
  AlertCircle, ArrowRight, Check, Save,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── cURL parser ──────────────────────────────────────────────────────────────

type CurlResult = { provider: "anthropic" | "openai" | null; apiKey: string; baseUrl: string; error: string | null };

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
  if (!apiKey) return { provider: null, apiKey: "", baseUrl: "", error: "No API key found (Authorization: Bearer, api-key, or x-api-key)" };
  let provider: "anthropic" | "openai" | null = null;
  let baseUrl = "";
  try {
    const p = new URL(rawUrl);
    const host = p.hostname.toLowerCase();
    if (host.includes("anthropic.com") || apiKey.startsWith("sk-ant-") || "anthropic-version" in headers) {
      provider = "anthropic";
      if (!host.includes("api.anthropic.com")) baseUrl = `${p.protocol}//${p.host}`;
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
  const [case1Threshold, setCase1Threshold] = useState(0.5);
  const [case2Threshold, setCase2Threshold] = useState(0.5);

  const [showAnthropic, setShowAnthropic] = useState(false);
  const [showOpenai, setShowOpenai] = useState(false);
  const [anthropicTest, setAnthropicTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [openaiTest, setOpenaiTest] = useState<{ ok: boolean; response: string } | null>(null);
  const [curlOpen, setCurlOpen] = useState(false);
  const [curlRaw, setCurlRaw] = useState("");
  const [curlResult, setCurlResult] = useState<CurlResult | null>(null);
  const [thresholdSaved, setThresholdSaved] = useState(false);
  const [anthropicSaved, setAnthropicSaved] = useState(false);
  const [openaiSaved, setOpenaiSaved] = useState(false);

  useEffect(() => {
    if (status) {
      setAnthropicUrl(status.anthropic_base_url || "");
      setOpenaiUrl(status.openai_base_url || "");
      setCase1Threshold(status.case1_threshold ?? 0.5);
      setCase2Threshold(status.case2_threshold ?? 0.5);
    }
  }, [status]);

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

  const saveThresholds = useMutation({
    mutationFn: () => appApiKeysApi.set(appId!, { case1_threshold: case1Threshold, case2_threshold: case2Threshold }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["app-api-keys", appId] }); setThresholdSaved(true); setTimeout(() => setThresholdSaved(false), 2000); },
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

  function applyCurl(r: CurlResult) {
    if (r.error) return;
    if (r.provider === "anthropic") { setAnthropicKey(r.apiKey); if (r.baseUrl) setAnthropicUrl(r.baseUrl); setAnthropicTest(null); }
    else { setOpenaiKey(r.apiKey); if (r.baseUrl) setOpenaiUrl(r.baseUrl); setOpenaiTest(null); }
    setCurlOpen(false); setCurlRaw(""); setCurlResult(null);
  }

  const anthropicDirty = anthropicKey.trim() || anthropicUrl !== (status?.anthropic_base_url ?? "");
  const openaiDirty = openaiKey.trim() || openaiUrl !== (status?.openai_base_url ?? "");
  const thresholdsDirty = case1Threshold !== (status?.case1_threshold ?? 0.5) || case2Threshold !== (status?.case2_threshold ?? 0.5);
  const canTestAnthropic = !!(anthropicKey.trim() || status?.anthropic_key_set);
  const canTestOpenai = !!(openaiKey.trim() || status?.openai_key_set);

  if (isLoading) return <div className="text-center py-16 text-gray-400">Loading...</div>;

  return (
    <div className="space-y-5 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
        <p className="text-sm text-gray-500 mt-1">Set keys for Anthropic and OpenAI. You can test before saving.</p>
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
                      <CheckCircle className="w-3.5 h-3.5" /> {curlResult.provider === "anthropic" ? "Anthropic" : "OpenAI / compatible"}
                    </div>
                    <div className="space-y-1 text-gray-700">
                      <p><span className="text-gray-400 mr-2">Key</span><span className="font-mono">{curlResult.apiKey.slice(0, 10)}{"•".repeat(8)}</span></p>
                      <p><span className="text-gray-400 mr-2">URL</span><span className="font-mono">{curlResult.baseUrl || <em className="not-italic text-gray-400">default</em>}</span></p>
                    </div>
                    <button onClick={() => applyCurl(curlResult)}
                      className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700"
                    >
                      <ArrowRight className="w-3.5 h-3.5" /> Apply to {curlResult.provider === "anthropic" ? "Anthropic" : "OpenAI"}
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
      </div>

      {/* Evaluation thresholds */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-violet-500" />
            <span className="text-sm font-semibold text-gray-900">Evaluation Thresholds</span>
          </div>
          <button onClick={() => saveThresholds.mutate()} disabled={!thresholdsDirty || saveThresholds.isPending}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
              thresholdSaved ? "bg-green-500 text-white"
                : thresholdsDirty ? "bg-violet-600 text-white hover:bg-violet-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed"
            )}
          >
            {thresholdSaved ? <Check className="w-3 h-3" /> : <Save className="w-3 h-3" />}
            {saveThresholds.isPending ? "Saving…" : thresholdSaved ? "Saved!" : "Save"}
          </button>
        </div>
        <p className="text-xs text-gray-400">Semantic similarity pass cutoff when no judge LLM is configured. Range 0–1, default 0.50.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <ThresholdInput label="Case 1 — Q↔A relevance" value={case1Threshold} onChange={setCase1Threshold} />
          <ThresholdInput label="Case 2 — Answer similarity" value={case2Threshold} onChange={setCase2Threshold} />
        </div>
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

// ── Threshold input ───────────────────────────────────────────────────────────

function ThresholdInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-gray-600">{label}</label>
        <input type="number" min={0} max={1} step={0.05} value={value.toFixed(2)}
          onChange={(e) => onChange(clamp(parseFloat(e.target.value) || 0))}
          className="w-16 text-right font-mono text-xs px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
      </div>
      <input type="range" min={0} max={1} step={0.05} value={value} onChange={(e) => onChange(clamp(parseFloat(e.target.value)))} className="w-full accent-violet-600" />
      <div className="flex gap-1">
        {[0.4, 0.5, 0.6, 0.7, 0.8].map((p) => (
          <button key={p} onClick={() => onChange(p)}
            className={cn("text-[10px] px-1.5 py-0.5 rounded border transition-colors flex-1",
              Math.abs(value - p) < 0.005 ? "border-violet-300 bg-violet-50 text-violet-700 font-medium" : "border-gray-200 text-gray-500 hover:bg-gray-50"
            )}
          >{p.toFixed(2)}</button>
        ))}
      </div>
    </div>
  );
}
