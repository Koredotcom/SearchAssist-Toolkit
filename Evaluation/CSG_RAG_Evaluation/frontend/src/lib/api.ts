import axios from "axios";
import { logger } from "@/lib/logger";

// In production set VITE_API_URL to your backend base (e.g. https://api.yourhost.com/api).
// In dev the Vite proxy forwards /api → http://localhost:8001, so no env var is needed.
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "/api" });

// ── Axios logging interceptors ────────────────────────────────────────────────
// Use a WeakMap to store per-request start times without mutating the config object.
import type { InternalAxiosRequestConfig } from "axios";
const _reqTimes = new WeakMap<InternalAxiosRequestConfig, number>();

api.interceptors.request.use((config) => {
  _reqTimes.set(config, performance.now());
  logger.debug("api", `→ ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

api.interceptors.response.use(
  (response) => {
    const t0 = _reqTimes.get(response.config);
    const ms = t0 != null ? Math.round(performance.now() - t0) : "?";
    logger.info("api", `← ${response.config.method?.toUpperCase()} ${response.config.url} ${response.status} (${ms}ms)`);
    return response;
  },
  (error) => {
    const cfg: InternalAxiosRequestConfig | undefined = error.config;
    const t0 = cfg != null ? _reqTimes.get(cfg) : undefined;
    const ms = t0 != null ? Math.round(performance.now() - t0) : "?";
    const status = error.response?.status ?? "network error";
    const detail = error.response?.data?.detail ?? error.message ?? "";
    logger.error("api", `✗ ${cfg?.method?.toUpperCase() ?? "?"} ${cfg?.url ?? "?"} ${status} (${ms}ms)`, { detail });
    return Promise.reject(error);
  },
);

// ── Types ────────────────────────────────────────────────────────────────────

export type AnswerMode = "answer_generation" | "extract_only";

export interface AppConfig {
  app_id: string;
  name: string;
  host_url: string;
  bot_id: string;
  stream_id: string | null;
  client_id: string;
  racl_entity_ids: string[];
  banned_topics: string[];
  answer_mode: AnswerMode;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // New Kore.ai Agent Platform fields
  process_id: string;
  cf_version_id: string;
  x_api_key_preview: string;  // masked last-4 only, never full key
  identity: string;

}

export interface AppConfigCreate {
  name: string;
  host_url?: string;
  bot_id?: string;
  stream_id?: string;
  client_id?: string;
  client_secret?: string;
  racl_entity_ids?: string[];
  banned_topics?: string[];
  answer_mode?: AnswerMode;
  // New Kore.ai Agent Platform fields
  process_id?: string;
  cf_version_id?: string;
  x_api_key?: string;
  identity?: string;

}

export interface Source {
  connector_id: string;
  name: string;
  type: string;
  is_active: boolean;
  records_count: number;
  size: number;
}

export interface ContentSource {
  source_id: string;
  name: string;
  sys_content_type: string; // "web" | "file"
  records_count: number;
  sample_url: string;
  base_url: string;
}

export interface LLMConfig {
  app_id: string;
  agent_name: string;
  model: string;
  temperature: number;
  max_tokens: number;
  updated_at: string;
}

export interface PromptConfig {
  id: string;
  app_id: string;
  agent_name: string;
  prompt_text: string;
  version: number;
  is_active: boolean;
  created_at: string;
}

export interface Job {
  job_id: string;
  app_id: string;
  job_type: string;
  status: "running" | "complete" | "failed" | "partial";
  progress: number;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoldenSet {
  version: string;
  app_id: string;
  created_at: string;
  frozen_at: string | null;
  notes: string | null;
  total_cases: number;
  kept_cases: number;
  borderline_cases: number;
}

export interface MatchSpecRule {
  field: string;
  value: string;
}

export interface TestCase {
  tc_id: string;
  question: string;
  expected_answer: string | null;
  expected_behavior: string;
  question_type: string | null;
  difficulty: number | null;
  reference_doc_ids: string[];
  reference_match_spec: MatchSpecRule[];
  human_validated: boolean;
  status: string;
  decision: string | null;
  scores: Record<string, number> | null;
}

export interface EvalRun {
  run_id: string;
  app_id: string;
  started_at: string;
  finished_at: string | null;
  rag_version: string;
  judge_model: string | null;
  golden_set_version: string;
  trigger: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  done_cases: number;  // live count of completed rows — updates mid-run
  pass_rate: number;
  avg_chunk_rank: number | null;
  identity: string;
  racl_entity_ids: string[];
  answer_mode: string;
}

export interface EvalResult {
  tc_id: string;
  question: string;
  expected_answer: string | null;
  expected_behavior: string;
  question_type: string | null;
  rag_response: string | null;
  retrieved_doc_ids: string[];
  reference_doc_ids: string[];
  scores: Record<string, number | boolean>;
  passed: boolean;
  failure_category: string | null;
  judge_rationale: string | null;
  latency_llm_ms: number | null;
  latency_retrieval_ms: number | null;
  doc_retrieved: boolean;
  search_payload?: Record<string, unknown> | null;
  // 4-case evaluation fields
  case_id: number | null;
  expected_doc_rank: number | null;
  recall_at_k: Record<string, number>;
  answer_similarity: number | null;
  verdict: "pass" | "fail" | null;
  verdict_source: string | null;
  chunk_signals: Array<{ chunkId: string | null; doc_id: string | null; recordTitle: string | null; normalized_score: number | null; [key: string]: unknown }>;
}

// ── API helpers ───────────────────────────────────────────────────────────────

export const appsApi = {
  list: () => api.get<AppConfig[]>("/apps").then((r) => r.data),
  get: (id: string) => api.get<AppConfig>(`/apps/${id}`).then((r) => r.data),
  create: (data: AppConfigCreate) => api.post<AppConfig>("/apps", data).then((r) => r.data),
  update: (id: string, data: Partial<AppConfigCreate>) =>
    api.put<AppConfig>(`/apps/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/apps/${id}`),
};

export const sourcesApi = {
  list: (appId: string) => api.get<Source[]>(`/apps/${appId}/sources`).then((r) => r.data),
  listWebCrawls: (appId: string) =>
    api.get<ContentSource[]>(`/apps/${appId}/sources/web-crawls`).then((r) => r.data),
  listDocuments: (appId: string) =>
    api.get<ContentSource[]>(`/apps/${appId}/sources/documents`).then((r) => r.data),
};

export const llmApi = {
  list: (appId: string) => api.get<LLMConfig[]>(`/apps/${appId}/llm-config`).then((r) => r.data),
  update: (appId: string, agentName: string, data: Partial<LLMConfig>) =>
    api.put<LLMConfig>(`/apps/${appId}/llm-config/${agentName}`, data).then((r) => r.data),
};

export const promptsApi = {
  list: (appId: string) => api.get<PromptConfig[]>(`/apps/${appId}/prompts`).then((r) => r.data),
  getActive: (appId: string, agentName: string) =>
    api.get<PromptConfig>(`/apps/${appId}/prompts/${agentName}/active`).then((r) => r.data),
  getDefaults: () => api.get<Record<string, string>>("/apps/any/prompts/defaults").then((r) => r.data),
  update: (appId: string, agentName: string, promptText: string) =>
    api.put<PromptConfig>(`/apps/${appId}/prompts/${agentName}`, { agent_name: agentName, prompt_text: promptText }).then((r) => r.data),
  reset: (appId: string, agentName: string) =>
    api.post<PromptConfig>(`/apps/${appId}/prompts/${agentName}/reset`).then((r) => r.data),
  upload: (appId: string, agentName: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<PromptConfig>(`/apps/${appId}/prompts/${agentName}/upload`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
};

export const generationApi = {
  start: (appId: string, data: {
    golden_set_version: string;
    connector_ids: string[];
    web_source_ids?: string[];
    file_source_ids?: string[];
    max_docs_per_source: number;
    max_questions_per_doc: number;
    filters: Record<string, unknown>;
  }) => api.post<Job>(`/apps/${appId}/generation/start`, data).then((r) => r.data),
  getJob: (appId: string, jobId: string) =>
    api.get<Job>(`/apps/${appId}/generation/jobs/${jobId}`).then((r) => r.data),
  listJobs: (appId: string) =>
    api.get<Job[]>(`/apps/${appId}/generation/jobs`).then((r) => r.data),
  freeze: (appId: string, version: string) =>
    api.post(`/apps/${appId}/generation/freeze/${version}`).then((r) => r.data),
  stop: (appId: string, jobId: string) =>
    api.post(`/apps/${appId}/generation/jobs/${jobId}/stop`).then((r) => r.data),
};

export type FilterMode = "none" | "auto_source" | "custom_prompt";
export type ScriptLang = "python" | "js";

export const evaluationApi = {
  start: (appId: string, data: {
    golden_set_version: string;
    rag_version: string;
    max_cases: number | null;
    sample_mode: "first" | "random";
    filter_mode: FilterMode;
    filter_prompt: string | null;
    enable_racl: boolean;
    user_email: string | null;
    identity: string | null;
    answer_mode_override: AnswerMode | null;
    question_types: string[] | null;
    racl_entity_ids_override: string[] | null;
  }) => api.post<Job>(`/apps/${appId}/evaluation/start`, data).then((r) => r.data),
  getJob: (appId: string, jobId: string) =>
    api.get<Job>(`/apps/${appId}/evaluation/jobs/${jobId}`).then((r) => r.data),
  listJobs: (appId: string) =>
    api.get<Job[]>(`/apps/${appId}/evaluation/jobs`).then((r) => r.data),
  stop: (appId: string, jobId: string) =>
    api.post<{ ok: boolean }>(`/apps/${appId}/evaluation/jobs/${jobId}/stop`).then((r) => r.data),
  testMapper: (appId: string, data: { script: string; lang: ScriptLang; llm_response: string }) =>
    api.post<{ output: unknown; error: string | null }>(`/apps/${appId}/evaluation/test-mapper`, data).then((r) => r.data),
  testFilterPrompt: (appId: string, data: { question: string; prompt_text?: string | null }) =>
    api.post<{ raw_response: string | null; error: string | null }>(`/apps/${appId}/evaluation/test-filter-prompt`, data).then((r) => r.data),
};

export interface QueryRequest {
  question: string;
  meta_filters?: Record<string, unknown>[];
  user_email?: string | null;
  answer_mode_override?: string | null;
}

export interface QueryResponse {
  answer: string;
  is_valid_answer: boolean;
  cited_doc_ids: string[];
  result_doc_ids: string[];
  answer_mode: string;
  latency_llm_ms: number | null;
  latency_retrieval_ms: number | null;
}

export const queryApi = {
  run: (appId: string, data: QueryRequest) =>
    api.post<QueryResponse>(`/apps/${appId}/query`, data).then((r) => r.data),
};

export interface GoldenSetDeleteImpact {
  version: string;
  frozen: boolean;
  test_cases_count: number;
  eval_runs_count: number;
}

export const goldenSetsApi = {
  list: (appId: string) => api.get<GoldenSet[]>(`/apps/${appId}/golden-sets`).then((r) => r.data),
  listTestCases: (appId: string, version: string) =>
    api.get<TestCase[]>(`/apps/${appId}/golden-sets/${version}/test-cases`).then((r) => r.data),
  upload: (appId: string, version: string, file: File) => {
    const form = new FormData();
    form.append("version", version);
    form.append("file", file);
    return api.post<{ imported: number; version: string; case_counts: Record<string, number> }>(
      `/apps/${appId}/golden-sets/upload`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((r) => r.data);
  },
  templateUrl: (appId: string) => `/api/apps/${appId}/golden-sets/template`,
  getDeleteImpact: (appId: string, version: string) =>
    api.get<GoldenSetDeleteImpact>(
      `/apps/${appId}/golden-sets/${encodeURIComponent(version)}/delete-impact`,
    ).then((r) => r.data),
  delete: (appId: string, version: string) =>
    api.delete<{ ok: boolean; version: string; test_cases_deleted: number; eval_runs_orphaned: number }>(
      `/apps/${appId}/golden-sets/${encodeURIComponent(version)}`,
    ).then((r) => r.data),
};

// ── Diagnostics (Phase 2) ────────────────────────────────────────────────────

export type RuleSeverity = "high" | "medium" | "low";

export interface FiredRule {
  rule_id: string;
  severity: RuleSeverity;
  title: string;
  description: string;
  impact_count: number;
  impact_pct: number;
  evidence_tc_ids: string[];
  recommendations: string[];
}

export interface RunDiagnostics {
  computed_at: string;
  engine_version: string;
  run_id: string;
  totals: {
    total: number;
    passed: number;
    failed: number;
    no_verdict: number;
    verdicted: number;
    pass_rate: number;
  };
  funnel: {
    queried: number;
    retrieved_any_doc: number;
    expected_doc_top10: number;
    expected_doc_top5: number;
    expected_doc_top1: number;
    expected_chunk_top5: number;
    answered: number;
    verdict_pass: number;
  };
  by_case: Record<string, {
    total: number;
    passed: number;
    failed: number;
    verdicted: number;
    no_verdict: number;
    pass_rate: number;
  }>;
  by_question_type: Record<string, {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  }>;
  by_failure_category: Record<string, number>;
  retrieval: {
    cases_with_chunk_rank: number;
    avg_chunk_rank: number | null;
    median_chunk_rank: number | null;
    cases_with_doc_rank: number;
    avg_doc_rank: number | null;
    median_doc_rank: number | null;
    recall_at_1: number | null;
    recall_at_3: number | null;
    recall_at_5: number | null;
    recall_at_10: number | null;
  };
  judge_metric_avgs: Record<string, number | null>;
  weakest_judge_metric: string | null;
  latency_ms: {
    llm_avg_ms: number | null;
    llm_p50_ms: number | null;
    llm_p95_ms: number | null;
    retrieval_avg_ms: number | null;
    retrieval_p50_ms: number | null;
    retrieval_p95_ms: number | null;
  };
  fired_rules: FiredRule[];
}

// ── AI Deep Dive (Phase 2 — Step 4 + 5) ─────────────────────────────────────

export interface AiInsightsResponse {
  markdown: string | null;
  model: string | null;
  generated_at: string | null;
  cached: boolean;
  warnings?: string[];
}

// ── Trends (Phase 2 — Step 3) ────────────────────────────────────────────────

export type TrendDirection = "better" | "worse" | "same";

export interface ScalarDelta {
  current: number | null;
  previous: number | null;
  delta: number | null;
  direction: TrendDirection;
  lower_is_better: boolean;
}

export interface RunTrends {
  run_id: string;
  previous_run_id: string | null;
  previous_run_date: string | null;
  golden_set_version: string;
  has_baseline: boolean;
  deltas: {
    pass_rate: ScalarDelta;
    total_cases: ScalarDelta;
    failed_cases: ScalarDelta;
    avg_chunk_rank: ScalarDelta;
    weakest_judge_metric: {
      current: string | null;
      previous: string | null;
      changed: boolean;
    };
    failures_by_category: Record<string, ScalarDelta>;
    judge_metric_avgs: Record<string, ScalarDelta>;
  };
}

export const resultsApi = {
  listRuns: (appId: string) => api.get<EvalRun[]>(`/apps/${appId}/results`).then((r) => r.data),
  getRun: (appId: string, runId: string) =>
    api.get<EvalRun>(`/apps/${appId}/results/${runId}/info`).then((r) => r.data),
  getResults: (appId: string, runId: string) =>
    api.get<EvalResult[]>(`/apps/${appId}/results/${runId}`).then((r) => r.data),
  getDiagnostics: (appId: string, runId: string, recompute = false) =>
    api.get<RunDiagnostics>(`/apps/${appId}/results/${runId}/diagnostics`, {
      params: recompute ? { recompute: true } : undefined,
    }).then((r) => r.data),
  getTrends: (appId: string, runId: string) =>
    api.get<RunTrends>(`/apps/${appId}/results/${runId}/trends`).then((r) => r.data),
  getAiInsights: (appId: string, runId: string) =>
    api.get<AiInsightsResponse>(`/apps/${appId}/results/${runId}/ai-insights`).then((r) => r.data),
  generateAiInsights: (appId: string, runId: string, regenerate = false) =>
    api.post<AiInsightsResponse>(
      `/apps/${appId}/results/${runId}/ai-insights`,
      undefined,
      { params: regenerate ? { regenerate: true } : undefined, timeout: 120_000 },
    ).then((r) => r.data),
  exportUrl: (appId: string, runId: string) =>
    `${import.meta.env.VITE_API_URL ?? "/api"}/apps/${appId}/results/${runId}/export`,
  reVerdictRun: (appId: string, runId: string) =>
    api.post(`/apps/${appId}/results/${runId}/re-verdict`).then((r) => r.data),
  reVerdictAll: (appId: string) =>
    api.post(`/apps/${appId}/results/re-verdict-all`).then((r) => r.data),
  delete: (appId: string, runId: string) =>
    api.delete<{ ok: boolean; run_id: string; results_deleted: number }>(
      `/apps/${appId}/results/${runId}`,
    ).then((r) => r.data),
};

export interface ApiKeyStatus {
  anthropic_key_set: boolean;
  anthropic_key_preview: string;
  anthropic_base_url: string;
  openai_key_set: boolean;
  openai_key_preview: string;
  openai_base_url: string;
  case1_threshold: number;
  case2_threshold: number;
}

export interface AppApiKeysUpdate {
  anthropic_key?: string;
  anthropic_base_url?: string;
  openai_key?: string;
  openai_base_url?: string;
  case1_threshold?: number;
  case2_threshold?: number;
}

export const appApiKeysApi = {
  get: (appId: string) => api.get<ApiKeyStatus>(`/apps/${appId}/api-keys`).then((r) => r.data),
  set: (appId: string, data: AppApiKeysUpdate) =>
    api.post<{ ok: boolean }>(`/apps/${appId}/api-keys`, data).then((r) => r.data),
  testAnthropic: (appId: string, key?: string, baseUrl?: string) =>
    api.post<{ ok: boolean; response: string }>(`/apps/${appId}/api-keys/test-anthropic`, { key: key || null, base_url: baseUrl || null }).then((r) => r.data),
  testOpenAI: (appId: string, key?: string, baseUrl?: string) =>
    api.post<{ ok: boolean; response: string }>(`/apps/${appId}/api-keys/test-openai`, { key: key || null, base_url: baseUrl || null }).then((r) => r.data),
};
