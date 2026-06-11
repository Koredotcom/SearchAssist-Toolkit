import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { sourcesApi, generationApi, llmApi, goldenSetsApi } from "@/lib/api";
import type { ContentSource, Job } from "@/lib/api";
import {
  Zap, Database, ChevronRight, ChevronDown, Loader2, CheckCircle, XCircle,
  Lock, AlertTriangle, Square, AlertCircle, Globe, File, Search,
} from "lucide-react";
import { cn } from "@/lib/utils";

const LANGUAGE_OPTIONS = [
  "English", "Spanish", "French", "German", "Italian", "Portuguese", "Dutch",
  "Chinese (Simplified)", "Chinese (Traditional)", "Japanese", "Korean",
  "Hindi", "Bengali", "Urdu", "Punjabi", "Gujarati", "Marathi", "Tamil",
  "Telugu", "Kannada", "Malayalam", "Odia", "Assamese", "Nepali", "Sinhala",
  "Arabic", "Hebrew", "Persian", "Turkish", "Russian", "Ukrainian", "Polish",
  "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Serbian",
  "Croatian", "Bosnian", "Slovenian", "Macedonian", "Albanian", "Greek",
  "Swedish", "Norwegian", "Danish", "Finnish", "Icelandic", "Estonian",
  "Latvian", "Lithuanian", "Irish", "Welsh", "Basque", "Catalan", "Galician",
  "Malay", "Indonesian", "Filipino", "Thai", "Vietnamese", "Burmese",
  "Khmer", "Lao", "Mongolian", "Kazakh", "Uzbek", "Kyrgyz", "Tajik",
  "Azerbaijani", "Armenian", "Georgian", "Swahili", "Amharic", "Somali",
  "Yoruba", "Igbo", "Hausa", "Zulu", "Xhosa", "Afrikaans", "Sesotho",
  "Shona", "Kinyarwanda", "Malagasy", "Latin", "Esperanto", "Haitian Creole",
  "Luxembourgish", "Maltese", "Maori", "Samoan", "Tongan", "Fijian",
  "Inuktitut", "Cherokee", "Quechua", "Aymara", "Guarani",
].sort((a, b) => a.localeCompare(b));

export default function GeneratePage() {
  const { appId } = useParams<{ appId: string }>();
  const qc = useQueryClient();

  const [selectedConnectorIds, setSelectedConnectorIds] = useState<string[]>([]);
  const [selectedWebIds, setSelectedWebIds] = useState<string[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [maxDocs, setMaxDocs] = useState(10);
  const [allDocs, setAllDocs] = useState(false);
  const [maxQuestionsPerDoc, setMaxQuestionsPerDoc] = useState(5);
  const [targetLanguage, setTargetLanguage] = useState("English");
  const [languageQuery, setLanguageQuery] = useState("");
  const [languageOpen, setLanguageOpen] = useState(false);
  const [goldenSetVersion, setGoldenSetVersion] = useState("v1.0.0");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [freezeSavedVersion, setFreezeSavedVersion] = useState<string | null>(null);
  const [freezeError, setFreezeError] = useState<string | null>(null);

  const { data: sources = [] } = useQuery({
    queryKey: ["sources", appId],
    queryFn: () => sourcesApi.list(appId!),
    enabled: !!appId,
  });

  const { data: webCrawls = [], isLoading: webLoading } = useQuery({
    queryKey: ["sources-web", appId],
    queryFn: () => sourcesApi.listWebCrawls(appId!),
    enabled: !!appId,
    staleTime: 5 * 60 * 1000,
  });

  const { data: uploadedDocs = [], isLoading: docsLoading } = useQuery({
    queryKey: ["sources-docs", appId],
    queryFn: () => sourcesApi.listDocuments(appId!),
    enabled: !!appId,
    staleTime: 5 * 60 * 1000,
  });

  const totalSelected =
    selectedConnectorIds.length + selectedWebIds.length + selectedFileIds.length;
  const totalAvailable = sources.length + webCrawls.length + uploadedDocs.length;

  // Upper bound for "Max documents per source". The param is per-source, so the
  // ceiling is the largest record count among the selected sources (anything
  // higher has no effect). Before any selection, fall back to the largest source
  // overall so the control is still meaningful.
  const selectedRecordCounts = [
    ...sources.filter((s) => selectedConnectorIds.includes(s.connector_id)).map((s) => s.records_count),
    ...webCrawls.filter((s) => selectedWebIds.includes(s.source_id)).map((s) => s.records_count),
    ...uploadedDocs.filter((s) => selectedFileIds.includes(s.source_id)).map((s) => s.records_count),
  ];
  const allRecordCounts = [
    ...sources.map((s) => s.records_count),
    ...webCrawls.map((s) => s.records_count),
    ...uploadedDocs.map((s) => s.records_count),
  ];
  const recordCountPool = (selectedRecordCounts.length ? selectedRecordCounts : allRecordCounts)
    .filter((n) => Number.isFinite(n) && n > 0);
  const docCeiling = recordCountPool.length ? Math.max(...recordCountPool) : 50;
  const effMaxDocs = Math.min(maxDocs, docCeiling);
  const normalizedLanguageQuery = languageQuery.trim();
  const filteredLanguages = LANGUAGE_OPTIONS.filter((lang) =>
    lang.toLowerCase().includes(normalizedLanguageQuery.toLowerCase())
  );
  const canUseCustomLanguage =
    normalizedLanguageQuery.length > 0 &&
    !LANGUAGE_OPTIONS.some((lang) => lang.toLowerCase() === normalizedLanguageQuery.toLowerCase());

  const { data: llmConfigs = [] } = useQuery({
    queryKey: ["llm-configs", appId],
    queryFn: () => llmApi.list(appId!),
    enabled: !!appId,
  });

  const generationAgents = ["agent1", "agent2", "agent3"];
  const llmNotConfigured = generationAgents.some((agent) => {
    const cfg = llmConfigs.find((c) => c.agent_name === agent);
    return !cfg || !cfg.model;
  });

  const { data: jobs = [] } = useQuery({
    queryKey: ["gen-jobs", appId],
    queryFn: () => generationApi.listJobs(appId!),
    enabled: !!appId,
  });

  const { data: goldenSets = [] } = useQuery({
    queryKey: ["golden-sets", appId],
    queryFn: () => goldenSetsApi.list(appId!),
    enabled: !!appId,
  });

  const { data: activeJob } = useQuery({
    queryKey: ["gen-job", appId, activeJobId],
    queryFn: () => generationApi.getJob(appId!, activeJobId!),
    enabled: !!appId && !!activeJobId,
    refetchInterval: (query) => {
      const job = query.state.data;
      return job && (job.status === "running") ? 2000 : false;
    },
  });

  const startMutation = useMutation({
    mutationFn: () =>
      generationApi.start(appId!, {
        golden_set_version: goldenSetVersion,
        connector_ids: selectedConnectorIds,
        web_source_ids: selectedWebIds,
        file_source_ids: selectedFileIds,
        max_docs_per_source: allDocs ? 0 : effMaxDocs,
        max_questions_per_doc: maxQuestionsPerDoc,
        target_language: targetLanguage,
        filters: {},
      }),
    onSuccess: (job: Job) => setActiveJobId(job.job_id),
  });

  const freezeMutation = useMutation({
    mutationFn: (version: string) => generationApi.freeze(appId!, version),
    onMutate: () => {
      setFreezeError(null);
      setFreezeSavedVersion(null);
    },
    onSuccess: (_data, version) => {
      setFreezeSavedVersion(version);
      qc.invalidateQueries({ queryKey: ["golden-sets", appId] });
    },
    onError: (err: { response?: { data?: { detail?: string } }; message?: string }) => {
      setFreezeError(err.response?.data?.detail ?? err.message ?? "Failed to save golden set.");
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => generationApi.stop(appId!, activeJobId!),
  });

  function toggleId(list: string[], setter: (s: string[]) => void, id: string) {
    setter(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  const isRunning = activeJob?.status === "running";
  const isDone = activeJob?.status === "complete";
  const currentGoldenSet = goldenSets.find((g) => g.version === goldenSetVersion);
  const isFrozen = Boolean(currentGoldenSet?.frozen_at || freezeSavedVersion === goldenSetVersion);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Generate Test Cases</h1>
        <p className="text-sm text-gray-500 mt-1">
          Select sources and configure generation settings
        </p>
      </div>

      {/* LLM not configured warning */}
      {llmNotConfigured && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-800">LLM not configured</p>
            <p className="text-xs text-amber-700 mt-0.5">
              One or more generation agents (Agent 1, 2, or 3) have no LLM model assigned.
              Go to <strong>LLM Config</strong> to set up models before generating test cases.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left — config */}
        <div className="lg:col-span-2 space-y-5">
          {/* Source selection */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <Database className="w-4 h-4 text-violet-500" />
                Select Sources
              </h2>
              <span className="text-xs text-gray-400">
                {totalSelected} / {totalAvailable} selected
              </span>
            </div>

            {/* Connectors */}
            <SourcePickerSection
              title="Connectors"
              icon={Database}
              accentClass="text-violet-500"
              items={sources.map((s) => ({
                id: s.connector_id,
                primary: s.name,
                secondary: `${s.records_count.toLocaleString()} records`,
                badge: s.type,
              }))}
              selectedIds={selectedConnectorIds}
              onToggle={(id) => toggleId(selectedConnectorIds, setSelectedConnectorIds, id)}
              onSelectAll={(all) =>
                setSelectedConnectorIds(all ? sources.map((s) => s.connector_id) : [])
              }
              loading={false}
              emptyLabel="No connectors configured."
            />

            {/* Websites */}
            <SourcePickerSection
              title="Websites"
              icon={Globe}
              accentClass="text-sky-500"
              items={webCrawls.map((c: ContentSource) => ({
                id: c.source_id,
                primary: c.name,
                secondary: `${c.records_count.toLocaleString()} pages`,
                badge: c.sys_content_type,
              }))}
              selectedIds={selectedWebIds}
              onToggle={(id) => toggleId(selectedWebIds, setSelectedWebIds, id)}
              onSelectAll={(all) =>
                setSelectedWebIds(all ? webCrawls.map((c: ContentSource) => c.source_id) : [])
              }
              loading={webLoading}
              emptyLabel="No web crawls indexed."
            />

            {/* Documents */}
            <SourcePickerSection
              title="Documents"
              icon={File}
              accentClass="text-emerald-500"
              items={uploadedDocs.map((d: ContentSource) => ({
                id: d.source_id,
                primary: d.name,
                secondary: `${d.records_count.toLocaleString()} docs`,
                badge: d.sys_content_type,
              }))}
              selectedIds={selectedFileIds}
              onToggle={(id) => toggleId(selectedFileIds, setSelectedFileIds, id)}
              onSelectAll={(all) =>
                setSelectedFileIds(all ? uploadedDocs.map((d: ContentSource) => d.source_id) : [])
              }
              loading={docsLoading}
              emptyLabel="No uploaded documents."
            />
          </div>

          {/* Settings */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <h2 className="font-semibold text-gray-900">Settings</h2>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-gray-700">
                  Max documents per source
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={allDocs}
                    onChange={(e) => setAllDocs(e.target.checked)}
                    className="rounded accent-violet-600"
                  />
                  <span className="text-xs font-medium text-violet-700">All documents</span>
                </label>
              </div>
              {allDocs ? (
                <div className="flex items-center gap-2 px-3 py-2 bg-violet-50 border border-violet-200 rounded-lg">
                  <span className="text-sm font-semibold text-violet-700">No limit</span>
                  <span className="text-xs text-violet-500">— all documents in each source will be processed</span>
                </div>
              ) : (
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min={1}
                    max={docCeiling}
                    value={effMaxDocs}
                    onChange={(e) => setMaxDocs(Number(e.target.value))}
                    className="flex-1 accent-violet-600"
                  />
                  <input
                    type="number"
                    min={1}
                    max={docCeiling}
                    value={effMaxDocs}
                    onChange={(e) => setMaxDocs(Math.max(1, Math.min(docCeiling, Number(e.target.value) || 1)))}
                    className="w-24 px-2 py-1 text-sm font-semibold text-violet-700 text-right border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                </div>
              )}
              <p className="text-xs text-gray-400 mt-1">
                {allDocs
                  ? `All documents across ${totalSelected} selected source${totalSelected !== 1 ? "s" : ""}`
                  : `Up to ${effMaxDocs} per source — max ${docCeiling.toLocaleString()} available${
                      selectedRecordCounts.length ? " in the selected source(s)" : " across all sources"
                    }`}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Questions per document
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={1}
                  max={5}
                  step={1}
                  value={maxQuestionsPerDoc}
                  onChange={(e) => setMaxQuestionsPerDoc(Number(e.target.value))}
                  className="flex-1 accent-violet-600"
                />
                <span className="text-sm font-semibold text-violet-700 w-8 text-right">{maxQuestionsPerDoc}</span>
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>Min (1)</span>
                <span className="text-center text-gray-500">
                  {maxQuestionsPerDoc === 1 ? "1 type" :
                   maxQuestionsPerDoc === 2 ? "factual + multi-hop" :
                   maxQuestionsPerDoc === 3 ? "factual + multi-hop + refusal" :
                   maxQuestionsPerDoc === 4 ? "4 diverse types" :
                   "5 diverse types (recommended)"}
                </span>
                <span>Max (5)</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Golden Set Version
              </label>
              <input
                type="text"
                value={goldenSetVersion}
                onChange={(e) => setGoldenSetVersion(e.target.value)}
                placeholder="v1.0.0"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
              <p className="text-xs text-gray-400 mt-1">Semver string for this golden set batch</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Test Case Language
              </label>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => {
                    setLanguageOpen((v) => !v);
                    setLanguageQuery("");
                  }}
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  <span className="truncate">{targetLanguage}</span>
                  <ChevronDown className={cn("w-4 h-4 text-gray-400 transition-transform", languageOpen && "rotate-180")} />
                </button>
                {languageOpen && (
                  <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                    <div className="relative p-2 border-b border-gray-100">
                      <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
                      <input
                        autoFocus
                        value={languageQuery}
                        onChange={(e) => setLanguageQuery(e.target.value)}
                        placeholder="Search languages..."
                        className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-500"
                      />
                    </div>
                    <div className="max-h-60 overflow-y-auto py-1">
                      {canUseCustomLanguage && (
                        <button
                          type="button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            setTargetLanguage(normalizedLanguageQuery);
                            setLanguageOpen(false);
                            setLanguageQuery("");
                          }}
                          className="w-full text-left px-3 py-2 text-sm text-violet-700 bg-violet-50 hover:bg-violet-100 font-medium"
                        >
                          Use "{normalizedLanguageQuery}"
                        </button>
                      )}
                      {filteredLanguages.length === 0 && !canUseCustomLanguage ? (
                        <div className="px-3 py-2 text-sm text-gray-400">No languages found</div>
                      ) : (
                        filteredLanguages.map((lang) => (
                          <button
                            key={lang}
                            type="button"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              setTargetLanguage(lang);
                              setLanguageOpen(false);
                              setLanguageQuery("");
                            }}
                            className={cn(
                              "w-full text-left px-3 py-2 text-sm hover:bg-violet-50",
                              lang === targetLanguage ? "text-violet-700 bg-violet-50 font-medium" : "text-gray-700"
                            )}
                          >
                            {lang}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Questions, expected answers, and rationales will be generated in this language.
              </p>
            </div>
          </div>
        </div>

        {/* Right — status + actions */}
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Summary</h2>
            <div className="space-y-2 text-sm">
              <Row label="Sources selected" value={`${totalSelected} / ${totalAvailable}`} />
              <Row
                label="  · Connectors"
                value={`${selectedConnectorIds.length}`}
                muted
              />
              <Row
                label="  · Websites"
                value={`${selectedWebIds.length}`}
                muted
              />
              <Row
                label="  · Documents"
                value={`${selectedFileIds.length}`}
                muted
              />
              <Row label="Docs per source" value={allDocs ? "All" : String(effMaxDocs)} />
              <Row label="Total docs (max)" value={allDocs ? "All" : String(effMaxDocs * Math.max(totalSelected, 1))} />
              <Row label="Questions per doc" value={String(maxQuestionsPerDoc)} />
              <Row label="Language" value={targetLanguage} />
              <Row label="Est. total questions" value={allDocs ? "varies" : String(effMaxDocs * Math.max(totalSelected, 1) * maxQuestionsPerDoc)} />
              <Row label="Golden set" value={goldenSetVersion} />
            </div>

            <div className="mt-5 space-y-2">
              <button
                onClick={() => startMutation.mutate()}
                disabled={totalSelected === 0 || isRunning || startMutation.isPending || llmNotConfigured}
                className={cn(
                  "w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors",
                  totalSelected === 0 || llmNotConfigured
                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                    : "bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
                )}
              >
                {isRunning ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Generating...</>
                ) : (
                  <><Zap className="w-4 h-4" />Start Generation</>
                )}
              </button>

              {isRunning && (
                <button
                  onClick={() => stopMutation.mutate()}
                  disabled={stopMutation.isPending}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  <Square className="w-4 h-4" />
                  {stopMutation.isPending ? "Stopping..." : "Stop Generation"}
                </button>
              )}
            </div>
          </div>

          {/* Active job progress */}
          {activeJob && (
            <JobProgress job={activeJob} />
          )}

          {/* Save option (previously "Freeze") */}
          {isDone && activeJob && !(activeJob.result?.stopped_early as boolean) && (
            <div className={cn(
              "rounded-xl p-4 border",
              isFrozen ? "bg-green-50 border-green-200" : "bg-violet-50 border-violet-200"
            )}>
              <p className={cn(
                "text-sm font-medium mb-1",
                isFrozen ? "text-green-900" : "text-violet-900"
              )}>
                {isFrozen ? "Saved for evaluation" : "Ready to save for evaluation?"}
              </p>
              <p className={cn(
                "text-xs mb-3",
                isFrozen ? "text-green-700" : "text-violet-700"
              )}>
                {isFrozen
                  ? `${goldenSetVersion} is locked and can now be used for evaluation runs.`
                  : "Saving locks this golden set so it can be used for evaluation runs. You can still view it in the Draft state on the Golden Sets page."}
              </p>
              {freezeError && (
                <p className="text-xs text-red-600 mb-2">{freezeError}</p>
              )}
              <button
                onClick={() => freezeMutation.mutate(goldenSetVersion)}
                disabled={freezeMutation.isPending || isFrozen}
                className={cn(
                  "w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-lg disabled:opacity-70",
                  isFrozen
                    ? "bg-green-600 text-white cursor-default"
                    : "bg-violet-600 text-white hover:bg-violet-700"
                )}
              >
                {isFrozen ? <CheckCircle className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
                {freezeMutation.isPending ? "Saving..." : isFrozen ? `Saved & Locked ${goldenSetVersion}` : `Save & Lock ${goldenSetVersion}`}
              </button>
            </div>
          )}

          {/* Stopped early — draft saved */}
          {isDone && (activeJob?.result?.stopped_early as boolean) && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-sm font-medium text-amber-800 mb-1">Stopped — Draft Saved</p>
              <p className="text-xs text-amber-700 mb-3">
                Generation was stopped early. Processed test cases have been saved as a draft in <strong>{goldenSetVersion}</strong>. You can view or save them from the Golden Sets page.
              </p>
            </div>
          )}

          {/* Recent jobs */}
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

function JobProgress({ job }: { job: Job }) {
  const isRunning = job.status === "running";
  const isDone = job.status === "complete";
  const isFailed = job.status === "failed";

  return (
    <div className={cn(
      "rounded-xl border p-4",
      isDone ? "bg-green-50 border-green-200" :
      isFailed ? "bg-red-50 border-red-200" :
      "bg-violet-50 border-violet-200"
    )}>
      <div className="flex items-center gap-2 mb-2">
        {isRunning && <Loader2 className="w-4 h-4 animate-spin text-violet-600" />}
        {isDone && <CheckCircle className="w-4 h-4 text-green-600" />}
        {isFailed && <XCircle className="w-4 h-4 text-red-600" />}
        <span className={cn(
          "text-sm font-medium",
          isDone ? "text-green-800" : isFailed ? "text-red-800" : "text-violet-800"
        )}>
          {isRunning ? "Generating..." : isDone ? "Complete" : "Failed"}
        </span>
        <span className="ml-auto text-sm font-semibold text-gray-700">{job.progress}%</span>
      </div>

      <div className="w-full bg-white/60 rounded-full h-2 overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            isDone ? "bg-green-500" : isFailed ? "bg-red-500" : "bg-violet-500"
          )}
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {isFailed && (
        <div className="mt-2 space-y-2">
          {job.error && (
            <p className="text-xs text-red-600">{job.error}</p>
          )}
          {job.result && (() => {
            const r = job.result as Record<string, unknown>;
            const skippedDocs = Array.isArray(r.skipped_docs)
              ? (r.skipped_docs as { doc_id: string; title: string }[])
              : [];
            return skippedDocs.length > 0 ? <SkippedDocsPanel docs={skippedDocs} /> : null;
          })()}
        </div>
      )}
      {isDone && job.result && (
        <div className="text-xs text-green-700 mt-2 space-y-1">
          {(() => {
            const r = job.result as Record<string, unknown>;
            const skippedDocs = Array.isArray(r.skipped_docs)
              ? (r.skipped_docs as { doc_id: string; title: string }[])
              : [];
            return (
              <>
                <p>
                  {((r.kept as number) ?? 0) + ((r.borderline as number) ?? 0)} test cases in draft
                  {" "}({(r.kept as number) ?? 0} kept, {(r.borderline as number) ?? 0} borderline, {(r.dropped as number) ?? 0} dropped)
                  {(r.stopped_early as boolean) && <span className="ml-1 text-amber-600 font-medium">· stopped early</span>}
                </p>
                <p className="text-green-600">
                  {(r.docs_processed as number) ?? 0} docs processed · {(r.total_raw as number) ?? 0} raw cases evaluated
                </p>
                {skippedDocs.length > 0 && (
                  <SkippedDocsPanel docs={skippedDocs} />
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className={cn("flex justify-between", muted && "text-xs")}>
      <span className={muted ? "text-gray-400" : "text-gray-500"}>{label}</span>
      <span className={muted ? "text-gray-500" : "font-medium text-gray-800"}>{value}</span>
    </div>
  );
}

// ── Source picker section (collapsible) ────────────────────────────────────────
function SourcePickerSection({
  title,
  icon: Icon,
  accentClass,
  items,
  selectedIds,
  onToggle,
  onSelectAll,
  loading,
  emptyLabel,
}: {
  title: string;
  icon: typeof Database;
  accentClass: string;
  items: Array<{ id: string; primary: string; secondary: string; badge: string }>;
  selectedIds: string[];
  onToggle: (id: string) => void;
  onSelectAll: (all: boolean) => void;
  loading: boolean;
  emptyLabel: string;
}) {
  const [open, setOpen] = useState(true);
  const allChecked = items.length > 0 && selectedIds.length === items.length;
  const someChecked = selectedIds.length > 0 && selectedIds.length < items.length;

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-left"
      >
        {open ? (
          <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
        )}
        <Icon className={cn("w-3.5 h-3.5 shrink-0", accentClass)} />
        <span className="text-sm font-medium text-gray-800">{title}</span>
        <span className="text-xs text-gray-400">
          {loading ? "loading…" : items.length === 0 ? "none" : `${selectedIds.length}/${items.length}`}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-3 pt-1 space-y-1.5">
          {loading ? (
            <div className="py-3 flex items-center gap-2 text-xs text-gray-400 justify-center">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading {title.toLowerCase()}…
            </div>
          ) : items.length === 0 ? (
            <p className="text-xs text-gray-400 italic py-1">{emptyLabel}</p>
          ) : (
            <>
              <label className="flex items-center gap-2 text-xs text-gray-500 pb-1.5 border-b border-gray-100">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={(el) => { if (el) el.indeterminate = someChecked; }}
                  onChange={(e) => onSelectAll(e.target.checked)}
                  className="rounded accent-violet-600"
                />
                Select all {title.toLowerCase()}
              </label>
              {items.map((item) => (
                <label
                  key={item.id}
                  className={cn(
                    "flex items-center gap-2.5 p-2 rounded-md border cursor-pointer transition-colors text-xs",
                    selectedIds.includes(item.id)
                      ? "border-violet-300 bg-violet-50"
                      : "border-gray-100 hover:border-gray-200"
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => onToggle(item.id)}
                    className="rounded accent-violet-600"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{item.primary}</p>
                    <p className="text-[11px] text-gray-400">{item.secondary}</p>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded-full font-mono shrink-0">
                    {item.badge}
                  </span>
                </label>
              ))}
            </>
          )}
        </div>
      )}
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

function SkippedDocsPanel({ docs }: { docs: { doc_id: string; title: string }[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 w-full text-left"
      >
        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
        <span className="text-xs font-semibold text-amber-800">
          {docs.length} document{docs.length !== 1 ? "s" : ""} skipped — not found in chunks API
        </span>
        <ChevronRight className={cn(
          "w-3 h-3 text-amber-500 ml-auto transition-transform",
          open && "rotate-90"
        )} />
      </button>
      {open && (
        <div className="mt-2 space-y-1">
          {docs.map((d) => (
            <div key={d.doc_id} className="flex items-start gap-2 text-xs text-amber-800">
              <span className="shrink-0 mt-0.5">•</span>
              <div className="min-w-0">
                <p className="font-medium truncate">{d.title}</p>
                <p className="font-mono text-amber-600 text-[10px]">{d.doc_id}</p>
              </div>
            </div>
          ))}
          <p className="text-[10px] text-amber-600 mt-1.5 pt-1.5 border-t border-amber-200">
            These documents have no indexed chunks in Kore.ai. Ensure they are fully processed before regenerating.
          </p>
        </div>
      )}
    </div>
  );
}
