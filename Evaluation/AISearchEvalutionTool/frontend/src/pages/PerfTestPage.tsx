import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  appApiKeysApi, appsApi, goldenSetsApi, perfTestApi,
} from "@/lib/api";
import type {
  PerfRun, PerfStopMode, PerfTestStartRequest,
} from "@/lib/api";
import { Gauge, Loader2, Play, Clock, Hash, TrendingUp, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const STORAGE_KEY = (appId: string) => `perf-test:${appId}`;

interface LoadProfile {
  concurrency: number;
  stop_mode: PerfStopMode;
  iterations: number;
  duration_s: number;
  ramp_up_s: number;
  golden_set_version: string;
}

const DEFAULT_PROFILE: LoadProfile = {
  concurrency: 5,
  stop_mode: "iterations",
  iterations: 50,
  duration_s: 60,
  ramp_up_s: 0,
  golden_set_version: "",
};

export default function PerfTestPage() {
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<LoadProfile>(DEFAULT_PROFILE);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate load profile from localStorage on first render.
  useEffect(() => {
    if (!appId) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY(appId));
      if (raw) {
        const parsed = JSON.parse(raw);
        setProfile({ ...DEFAULT_PROFILE, ...parsed });
      }
    } catch { /* ignore */ }
    setHydrated(true);
  }, [appId]);

  // Persist whenever profile changes.
  useEffect(() => {
    if (!appId || !hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY(appId), JSON.stringify(profile));
    } catch { /* quota — ignore */ }
  }, [appId, profile, hydrated]);

  const { data: apps = [] } = useQuery({
    queryKey: ["apps"],
    queryFn: appsApi.list,
  });
  const currentApp = apps.find((a) => a.app_id === appId);

  const { data: goldenSets = [] } = useQuery({
    queryKey: ["golden-sets", appId],
    queryFn: () => goldenSetsApi.list(appId!),
    enabled: !!appId,
  });
  const frozenSets = useMemo(() => goldenSets.filter((g) => g.frozen_at !== null), [goldenSets]);

  // Default golden set on first hydration if user hasn't picked one.
  useEffect(() => {
    if (!hydrated || profile.golden_set_version) return;
    if (frozenSets.length > 0) {
      setProfile((p) => ({ ...p, golden_set_version: frozenSets[0].version }));
    }
  }, [hydrated, frozenSets, profile.golden_set_version]);

  const { data: apiKeyStatus } = useQuery({
    queryKey: ["app-api-keys", appId],
    queryFn: () => appApiKeysApi.get(appId!),
    enabled: !!appId,
  });

  const { data: runs = [] } = useQuery<PerfRun[]>({
    queryKey: ["perf-runs", appId],
    queryFn: () => perfTestApi.listRuns(appId!),
    enabled: !!appId,
    refetchInterval: 3000,
  });

  const startMutation = useMutation({
    mutationFn: () => {
      const body: PerfTestStartRequest = {
        golden_set_version: profile.golden_set_version,
        concurrency: profile.concurrency,
        stop_mode: profile.stop_mode,
        iterations: profile.stop_mode === "iterations" ? profile.iterations : null,
        duration_s: profile.stop_mode === "duration" ? profile.duration_s : null,
        ramp_up_s: profile.ramp_up_s,
      };
      return perfTestApi.start(appId!, body);
    },
    onSuccess: (resp) => {
      navigate(`/apps/${appId}/perf-test/${resp.run_id}`);
    },
  });

  const endpointUrl = currentApp
    ? `${currentApp.host_url}/api/public/bot/${currentApp.bot_id}/search/v2/advanced-search`
    : "";

  const jwtPreview = apiKeyStatus ? "configured" : "missing";

  const canStart = !!profile.golden_set_version && !startMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Gauge className="w-6 h-6 text-violet-600" /> Perf Test
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Fire the golden-set questions at the Kore.ai search endpoint in parallel and measure latency.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Request setup — Postman-style left pane */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-6 space-y-5">
          <h2 className="text-sm font-semibold text-gray-800">Request</h2>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Method &amp; URL</label>
            <div className="flex gap-2">
              <span className="inline-flex items-center px-2.5 py-1.5 text-xs font-mono font-bold text-orange-700 bg-orange-50 border border-orange-200 rounded-lg">
                POST
              </span>
              <input
                readOnly
                value={endpointUrl || "Configure host_url & bot_id on the app first"}
                className="flex-1 px-3 py-1.5 text-xs font-mono border border-gray-200 rounded-lg bg-gray-50 text-gray-600"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Headers</label>
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs font-mono space-y-1 text-gray-600">
              <p><span className="text-violet-600">auth</span>: {jwtPreview === "configured" ? "<JWT from app config>" : <span className="text-red-500">(no JWT configured)</span>}</p>
              <p><span className="text-violet-600">Content-Type</span>: application/json</p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Body (per request)</label>
            <pre className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs font-mono text-gray-700 overflow-x-auto">{`{
  "query": "<test-case question>",
  "answerSearch": true,
  "searchResults": true,
  "includeChunksInResponse": true,
  "maxNumOfChunks": 100${currentApp && (currentApp.racl_entity_ids?.length ?? 0) > 0 ? `,
  "raclEntityIds": ${JSON.stringify(currentApp.racl_entity_ids)}` : ""}
}`}</pre>
            <p className="text-[11px] text-gray-400 mt-1">
              The question for each request rotates through the active test cases of the selected golden set.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Golden Set</label>
            {frozenSets.length === 0 ? (
              <p className="text-xs text-amber-700 italic">No frozen golden sets — freeze one on the Generate page first.</p>
            ) : (
              <select
                value={profile.golden_set_version}
                onChange={(e) => setProfile((p) => ({ ...p, golden_set_version: e.target.value }))}
                className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
              >
                {frozenSets.map((g) => (
                  <option key={g.version} value={g.version}>
                    {g.version} — {g.kept_cases} cases
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* Load profile + Start */}
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-800">Load profile</h2>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Concurrency (parallel workers)</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={profile.concurrency}
                  onChange={(e) => setProfile((p) => ({ ...p, concurrency: Math.max(1, Math.min(200, Number(e.target.value) || 1)) }))}
                  className="w-20 px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={Math.min(profile.concurrency, 50)}
                  onChange={(e) => setProfile((p) => ({ ...p, concurrency: Number(e.target.value) }))}
                  className="flex-1 accent-violet-600"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Stop condition</label>
              <div className="flex gap-2 mb-3">
                {(["iterations", "duration"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setProfile((p) => ({ ...p, stop_mode: m }))}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-lg border",
                      profile.stop_mode === m
                        ? "border-violet-400 bg-violet-50 text-violet-700"
                        : "border-gray-200 text-gray-500 hover:border-gray-300"
                    )}
                  >
                    {m === "iterations" ? <Hash className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                    {m === "iterations" ? "Iterations" : "Duration"}
                  </button>
                ))}
              </div>
              {profile.stop_mode === "iterations" ? (
                <div>
                  <p className="text-[11px] text-gray-400 mb-1">Total request count</p>
                  <input
                    type="number"
                    min={1}
                    max={100000}
                    value={profile.iterations}
                    onChange={(e) => setProfile((p) => ({ ...p, iterations: Math.max(1, Number(e.target.value) || 1) }))}
                    className="w-full px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                </div>
              ) : (
                <div>
                  <p className="text-[11px] text-gray-400 mb-1">Duration (seconds)</p>
                  <input
                    type="number"
                    min={1}
                    max={3600}
                    value={profile.duration_s}
                    onChange={(e) => setProfile((p) => ({ ...p, duration_s: Math.max(1, Number(e.target.value) || 1) }))}
                    className="w-full px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Ramp-up (seconds)</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={0}
                  max={600}
                  value={profile.ramp_up_s}
                  onChange={(e) => setProfile((p) => ({ ...p, ramp_up_s: Math.max(0, Math.min(600, Number(e.target.value) || 0)) }))}
                  className="w-20 px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
                <p className="text-[11px] text-gray-400 flex-1">
                  0 = jump to full concurrency immediately. Otherwise scales 1 → {profile.concurrency} workers over this window.
                </p>
              </div>
            </div>

            <button
              onClick={() => startMutation.mutate()}
              disabled={!canStart}
              className={cn(
                "w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors",
                !canStart
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                  : "bg-violet-600 text-white hover:bg-violet-700"
              )}
            >
              {startMutation.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Starting…</>
              ) : (
                <><Play className="w-4 h-4" /> Start Run</>
              )}
            </button>
            {startMutation.isError && (
              <p className="text-xs text-red-600">{(startMutation.error as Error)?.message || "Failed to start"}</p>
            )}
          </div>

          {runs.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5" /> Recent runs
              </h3>
              <div className="space-y-1">
                {runs.slice(0, 10).map((r) => (
                  <button
                    key={r.run_id}
                    onClick={() => navigate(`/apps/${appId}/perf-test/${r.run_id}`)}
                    className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 text-left"
                  >
                    <StatusDot status={r.status} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-800 truncate">
                        {r.golden_set_version} · {r.concurrency}× · {r.stop_mode === "iterations" ? `${r.iterations} req` : `${r.duration_s}s`}
                      </p>
                      <p className="text-[11px] text-gray-400">
                        {r.p95_ms != null ? `p95 ${r.p95_ms.toFixed(0)}ms` : "—"}
                        {r.total_requests > 0 && ` · ${r.total_requests} req · ${r.error_count} err`}
                      </p>
                    </div>
                    <ChevronRight className="w-3 h-3 text-gray-300" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: PerfRun["status"] }) {
  return (
    <div className={cn(
      "w-2 h-2 rounded-full shrink-0",
      status === "complete" ? "bg-green-500" :
      status === "failed" ? "bg-red-500" :
      status === "stopped" ? "bg-amber-500" :
      "bg-violet-500 animate-pulse"
    )} />
  );
}
