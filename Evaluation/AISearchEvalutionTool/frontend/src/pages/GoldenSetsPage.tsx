import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goldenSetsApi, generationApi } from "@/lib/api";
import type { GoldenSet, TestCase } from "@/lib/api";
import {
  BookOpen, Lock, ChevronDown, ChevronRight, CheckCircle, Clock,
  Upload, X, FileText, Download, Loader2, AlertCircle, Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import ConfirmDialog from "@/components/ConfirmDialog";

type CaseCount = Record<string, number>;

const COLUMN_REFERENCE: Array<{
  name: string;
  required: boolean;
  cases: string;
  example: string;
}> = [
  { name: "question",            required: true,  cases: "1 / 2 / 3 / 4", example: "How long does shipping take?" },
  { name: "expected_answer",     required: false, cases: "2 / 4",         example: "Standard shipping takes 3–5 business days." },
  { name: "doc_id  (or docId)",  required: false, cases: "3 / 4",         example: "doc-abc-123" },
  { name: "recordUrl",           required: false, cases: "3 / 4",         example: "https://docs.example.com/refunds" },
  { name: "record_title",        required: false, cases: "3 / 4",         example: "Laptop Warranty Policy" },
  { name: "<any custom column>", required: false, cases: "3 / 4",         example: "matches chunk['<column>'] in retrieved JSON" },
  { name: "expected_behavior",   required: false, cases: "optional",      example: "ANSWER | REFUSE | CLARIFY" },
  { name: "question_type",       required: false, cases: "optional",      example: "factual, policy, procedural" },
  { name: "difficulty",          required: false, cases: "optional",      example: "1, 2, or 3" },
];

const CASE_GUIDE: Array<{ id: number; title: string; desc: string }> = [
  { id: 1, title: "Question only",
    desc: "Observation + LLM self-eval. Without judge: semantic Q↔Answer similarity drives pass/fail." },
  { id: 2, title: "Question + expected answer",
    desc: "Answer correctness. With judge: LLM verdict. Without: semantic similarity ≥ threshold." },
  { id: 3, title: "Question + reference doc",
    desc: "Retrieval eval. Pass = expected doc in top 5; rank + Recall@K recorded. Reference can be doc_id, recordUrl, recordTitle, or any custom chunk field." },
  { id: 4, title: "All fields",
    desc: "Full evaluation — answer correctness + retrieval metrics." },
];

const REF_PRIORITY = [
  "doc_id / docId",
  "recordUrl",
  "record_title / recordTitle",
  "any other column → chunk[<column>]",
];

export default function GoldenSetsPage() {
  const { appId } = useParams<{ appId: string }>();
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [saveConfirm, setSaveConfirm] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<GoldenSet | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: goldenSets = [], isLoading } = useQuery({
    queryKey: ["golden-sets", appId],
    queryFn: () => goldenSetsApi.list(appId!),
    enabled: !!appId,
  });

  const { data: testCases = [], isFetching: loadingTCs } = useQuery({
    queryKey: ["test-cases", appId, expanded],
    queryFn: () => goldenSetsApi.listTestCases(appId!, expanded!),
    enabled: !!appId && !!expanded,
  });

  const { data: deleteImpact } = useQuery({
    queryKey: ["golden-set-delete-impact", appId, deleteTarget?.version],
    queryFn: () => goldenSetsApi.getDeleteImpact(appId!, deleteTarget!.version),
    enabled: !!appId && !!deleteTarget,
  });

  const freezeMutation = useMutation({
    mutationFn: (version: string) => generationApi.freeze(appId!, version),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["golden-sets", appId] });
      setSaveConfirm(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (version: string) => goldenSetsApi.delete(appId!, version),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["golden-sets", appId] });
      if (deleteTarget && expanded === deleteTarget.version) setExpanded(null);
      setDeleteTarget(null);
      setDeleteError(null);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail
        ?? (err as Error)?.message
        ?? "Failed to delete golden set.";
      setDeleteError(msg);
    },
  });

  if (isLoading) {
    return <div className="text-center py-16 text-gray-400">Loading golden sets...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Golden Sets</h1>
          <p className="text-sm text-gray-500 mt-1">
            Versioned test case collections for evaluation
          </p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700"
        >
          <Upload className="w-4 h-4" />
          Upload Test Cases
        </button>
      </div>

      {goldenSets.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-gray-200 rounded-xl">
          <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No golden sets yet</p>
          <p className="text-gray-400 text-sm mt-1">
            Run test case generation or upload a CSV/Excel file
          </p>
          <button
            onClick={() => setShowUpload(true)}
            className="mt-4 flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-violet-600 border border-violet-200 rounded-lg hover:bg-violet-50 mx-auto"
          >
            <Upload className="w-3.5 h-3.5" /> Upload CSV / Excel
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {goldenSets.map((gs) => (
            <div key={gs.version} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-4">
                <button
                  onClick={() => setExpanded(expanded === gs.version ? null : gs.version)}
                  className="flex items-center gap-2 flex-1 min-w-0"
                >
                  {expanded === gs.version ? (
                    <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
                  )}
                  <span className="font-semibold text-gray-900">{gs.version}</span>
                  {gs.frozen_at ? (
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                      <Lock className="w-3 h-3" />
                      Saved
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
                      <Clock className="w-3 h-3" />
                      Draft
                    </span>
                  )}
                </button>

                <div className="flex items-center gap-4 text-sm text-gray-500 shrink-0">
                  <span>{gs.kept_cases} / {gs.total_cases} cases</span>
                  {gs.borderline_cases > 0 && (
                    <span className="text-amber-600">{gs.borderline_cases} borderline</span>
                  )}
                  {!gs.frozen_at && (
                    <button
                      onClick={() => setSaveConfirm(gs.version)}
                      className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700"
                    >
                      <Lock className="w-3 h-3" />
                      Save
                    </button>
                  )}
                  <button
                    onClick={() => { setDeleteError(null); setDeleteTarget(gs); }}
                    title="Delete golden set"
                    className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {gs.notes && (
                <div className="px-5 pb-2 text-xs text-gray-400">{gs.notes}</div>
              )}

              {expanded === gs.version && (
                <div className="border-t border-gray-100">
                  {loadingTCs ? (
                    <div className="py-8 text-center text-gray-400 text-sm">Loading test cases...</div>
                  ) : testCases.length === 0 ? (
                    <div className="py-8 text-center text-gray-400 text-sm">No test cases</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 text-left">
                            <th className="px-5 py-2.5 font-medium text-gray-500 text-xs">Question</th>
                            <th className="px-5 py-2.5 font-medium text-gray-500 text-xs">Type</th>
                            <th className="px-5 py-2.5 font-medium text-gray-500 text-xs">Difficulty</th>
                            <th className="px-5 py-2.5 font-medium text-gray-500 text-xs">Status</th>
                            <th className="px-5 py-2.5 font-medium text-gray-500 text-xs">Decision</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {testCases.map((tc) => (
                            <TestCaseRow key={tc.tc_id} tc={tc} />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Save confirm modal */}
      {saveConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">Save &amp; Lock {saveConfirm}?</h3>
            <p className="text-sm text-gray-500 mb-4">
              Saving locks this golden set so it can be used for evaluation runs. It can no longer be modified after saving.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setSaveConfirm(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                Cancel
              </button>
              <button
                onClick={() => freezeMutation.mutate(saveConfirm)}
                disabled={freezeMutation.isPending}
                className="px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
              >
                {freezeMutation.isPending ? "Saving..." : "Save & Lock"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload modal */}
      {showUpload && (
        <UploadModal
          appId={appId!}
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["golden-sets", appId] });
            setShowUpload(false);
          }}
        />
      )}

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete golden set "${deleteTarget?.version ?? ""}"?`}
        description={
          <>
            This permanently removes all test cases in this golden set and any
            agent scores attached to them. This action cannot be undone.
          </>
        }
        confirmLabel="Delete golden set"
        loading={deleteMutation.isPending}
        error={deleteError}
        onCancel={() => {
          if (deleteMutation.isPending) return;
          setDeleteTarget(null);
          setDeleteError(null);
        }}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.version)}
      >
        {deleteTarget && (
          <div className="space-y-2 text-xs">
            <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-gray-700">
              <div className="flex items-center justify-between">
                <span className="font-mono">{deleteTarget.version}</span>
                {deleteTarget.frozen_at && (
                  <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded-full">
                    <Lock className="w-3 h-3" /> Saved
                  </span>
                )}
              </div>
              <div className="text-gray-500 mt-1">
                {deleteImpact
                  ? `${deleteImpact.test_cases_count} test case${deleteImpact.test_cases_count !== 1 ? "s" : ""} will be removed`
                  : `${deleteTarget.total_cases} test case${deleteTarget.total_cases !== 1 ? "s" : ""} will be removed`}
              </div>
            </div>
            {deleteImpact && deleteImpact.eval_runs_count > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
                <strong>{deleteImpact.eval_runs_count}</strong> existing evaluation
                run{deleteImpact.eval_runs_count !== 1 ? "s" : ""} reference this golden set.
                Those runs will remain but their golden-set link will become a dangling reference.
              </div>
            )}
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}

// ── Upload Modal ───────────────────────────────────────────────────────────────
function UploadModal({
  appId,
  onClose,
  onSuccess,
}: {
  appId: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [version, setVersion] = useState(`uploaded-${today}`);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ imported: number; version: string; case_counts: CaseCount } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleUpload = async () => {
    if (!file || !version.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await goldenSetsApi.upload(appId, version.trim(), file);
      setResult(res);
      onSuccess();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Upload failed. Check file format and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-violet-600" />
            <h3 className="font-semibold text-gray-900">Upload Test Cases</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 2-column body */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1.1fr] gap-0 overflow-y-auto">
          {/* LEFT: uploader */}
          <div className="px-6 py-5 space-y-4 md:border-r border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Golden Set Version Name
              </label>
              <input
                type="text"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="e.g. uploaded-2025-05-17"
                className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                If this version already exists (as a draft), new cases will be added to it.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                File (CSV or Excel)
              </label>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                  dragOver ? "border-violet-400 bg-violet-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                />
                {file ? (
                  <div className="flex items-center justify-center gap-2">
                    <FileText className="w-5 h-5 text-violet-500" />
                    <div className="text-left">
                      <p className="text-sm font-medium text-gray-700">{file.name}</p>
                      <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      className="ml-2 text-gray-400 hover:text-gray-600"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">Drop CSV or Excel file here</p>
                    <p className="text-xs text-gray-400 mt-1">or click to browse</p>
                  </div>
                )}
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {error}
              </div>
            )}

            {result && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">
                  <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                  Imported <strong className="mx-0.5">{result.imported}</strong> test cases into <strong className="mx-0.5">{result.version}</strong>.
                </div>
                {result.case_counts && (
                  <div className="grid grid-cols-4 gap-2">
                    {[1, 2, 3, 4].map((c) => {
                      const n = result.case_counts[String(c)] ?? 0;
                      return (
                        <div key={c} className={cn(
                          "rounded-lg border px-3 py-2 text-center",
                          n > 0 ? "bg-violet-50 border-violet-100" : "bg-gray-50 border-gray-100"
                        )}>
                          <div className="text-[10px] font-medium text-gray-500">Case {c}</div>
                          <div className={cn(
                            "text-lg font-semibold",
                            n > 0 ? "text-violet-700" : "text-gray-400"
                          )}>{n}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* RIGHT: column reference */}
          <div className="px-6 py-5 bg-gray-50/40 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-gray-800">Column Reference</h4>
              <a
                href={goldenSetsApi.templateUrl(appId)}
                className="flex items-center gap-1.5 text-xs font-medium text-violet-700 hover:text-violet-900 px-2.5 py-1 border border-violet-200 rounded-md bg-white hover:bg-violet-50"
              >
                <Download className="w-3 h-3" /> Download template (.xlsx)
              </a>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr className="text-left text-gray-500">
                    <th className="px-3 py-2 font-medium">Column</th>
                    <th className="px-3 py-2 font-medium">Required</th>
                    <th className="px-3 py-2 font-medium">Cases</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {COLUMN_REFERENCE.map((c) => (
                    <tr key={c.name}>
                      <td className="px-3 py-2">
                        <div className="font-mono text-gray-800">{c.name}</div>
                        <div className="text-gray-400 text-[11px] mt-0.5">{c.example}</div>
                      </td>
                      <td className="px-3 py-2">
                        {c.required ? (
                          <span className="inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-rose-50 text-rose-700">required</span>
                        ) : (
                          <span className="text-gray-400">optional</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{c.cases}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2">
              <p className="text-[11px] font-semibold text-amber-900 mb-1">Expected-document priority (per row)</p>
              <ol className="text-[11px] text-amber-800 space-y-0.5 list-decimal list-inside">
                {REF_PRIORITY.map((p) => (
                  <li key={p}><span className="font-mono">{p}</span></li>
                ))}
              </ol>
              <p className="text-[10px] text-amber-700 mt-1">The highest priority column present in a row wins; the rest are ignored.</p>
            </div>

            <div>
              <h5 className="text-xs font-semibold text-gray-700 mb-2">Four Evaluation Cases</h5>
              <div className="grid grid-cols-1 gap-2">
                {CASE_GUIDE.map((c) => (
                  <div key={c.id} className="rounded-lg border border-gray-200 bg-white px-3 py-2">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-violet-100 text-violet-700 text-[10px] font-bold">
                        {c.id}
                      </span>
                      <span className="text-xs font-semibold text-gray-800">{c.title}</span>
                    </div>
                    <p className="text-[11px] text-gray-500 leading-snug">{c.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
          >
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={handleUpload}
              disabled={loading || !file || !version.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Importing...</>
              ) : (
                <><Upload className="w-3.5 h-3.5" /> Import</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function TestCaseRow({ tc }: { tc: TestCase }) {
  const [showDetail, setShowDetail] = useState(false);

  return (
    <>
      <tr
        className="hover:bg-gray-50 cursor-pointer"
        onClick={() => setShowDetail(!showDetail)}
      >
        <td className="px-5 py-3 max-w-xs">
          <p className="truncate text-gray-700">{tc.question}</p>
        </td>
        <td className="px-5 py-3">
          <span className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full">
            {tc.question_type ?? "—"}
          </span>
        </td>
        <td className="px-5 py-3 text-gray-500">
          {tc.difficulty != null ? (
            <DifficultyBar level={tc.difficulty} />
          ) : "—"}
        </td>
        <td className="px-5 py-3">
          <StatusBadge status={tc.status} />
        </td>
        <td className="px-5 py-3">
          <DecisionBadge decision={tc.decision} />
        </td>
      </tr>
      {showDetail && (
        <tr>
          <td colSpan={5} className="px-5 py-4 bg-gray-50">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <p className="font-medium text-gray-600 mb-1">Expected Answer</p>
                <p className="text-gray-500 whitespace-pre-wrap">
                  {tc.expected_answer || <span className="italic text-gray-400">— (not provided)</span>}
                </p>
              </div>
              <div>
                <p className="font-medium text-gray-600 mb-1">Expected Behavior</p>
                <p className="text-gray-500">{tc.expected_behavior}</p>
                {tc.reference_doc_ids.length > 0 && (
                  <>
                    <p className="font-medium text-gray-600 mt-3 mb-1">Reference Docs</p>
                    <div className="flex flex-wrap gap-1">
                      {tc.reference_doc_ids.map((id) => (
                        <span key={id} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded font-mono">{id}</span>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function DifficultyBar({ level }: { level: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className={cn(
            "w-2.5 h-3 rounded-sm",
            i <= level ? "bg-violet-500" : "bg-gray-200"
          )}
        />
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    kept: "bg-green-100 text-green-700",
    borderline: "bg-amber-100 text-amber-700",
    dropped: "bg-red-100 text-red-600",
    active: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded-full", colors[status] ?? "bg-gray-100 text-gray-600")}>
      {status}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) return <span className="text-gray-300">—</span>;
  const colors: Record<string, string> = {
    KEEP: "bg-green-100 text-green-700",
    keep: "bg-green-100 text-green-700",
    BORDERLINE: "bg-amber-100 text-amber-700",
    borderline: "bg-amber-100 text-amber-700",
    DROP: "bg-red-100 text-red-600",
    drop: "bg-red-100 text-red-600",
  };
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded-full", colors[decision] ?? "bg-gray-100 text-gray-600")}>
      {decision}
    </span>
  );
}
