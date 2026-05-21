import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { sourcesApi } from "@/lib/api";
import type { ContentSource, Source } from "@/lib/api";
import {
  Database, FileText, HardDrive, CheckCircle, XCircle, Globe, File,
  Loader2, ExternalLink, ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function SourcesPage() {
  const { appId } = useParams<{ appId: string }>();

  return (
    <PageShell>
      <ConnectorsSection appId={appId!} />
      <WebsitesSection appId={appId!} />
      <DocumentsSection appId={appId!} />
    </PageShell>
  );
}

// ── Section: Connectors ────────────────────────────────────────────────────────
function ConnectorsSection({ appId }: { appId: string }) {
  const { data: sources = [], isLoading, error } = useQuery({
    queryKey: ["sources", appId],
    queryFn: () => sourcesApi.list(appId),
    enabled: !!appId,
  });

  return (
    <CollapsibleSection
      title="Connectors"
      subtitle="Third-party integrations (Jira, Confluence, Wolken, YouTube, …)"
      icon={Database}
      iconColor="text-violet-500"
      count={sources.length}
      isLoading={isLoading}
      error={error}
      emptyHint="No connectors configured in this Kore.ai app."
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {sources.map((source) => (
          <ConnectorCard key={source.connector_id} source={source} />
        ))}
      </div>
    </CollapsibleSection>
  );
}

// ── Section: Websites (web crawls) ─────────────────────────────────────────────
function WebsitesSection({ appId }: { appId: string }) {
  const { data: crawls = [], isLoading, error } = useQuery({
    queryKey: ["sources-web", appId],
    queryFn: () => sourcesApi.listWebCrawls(appId),
    enabled: !!appId,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <CollapsibleSection
      title="Websites"
      subtitle="Indexed web crawls"
      icon={Globe}
      iconColor="text-sky-500"
      count={crawls.length}
      isLoading={isLoading}
      error={error}
      emptyHint="No web crawls indexed for this app."
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {crawls.map((c) => (
          <ContentSourceCard key={c.source_id} source={c} kind="web" />
        ))}
      </div>
    </CollapsibleSection>
  );
}

// ── Section: Documents (uploaded files) ────────────────────────────────────────
function DocumentsSection({ appId }: { appId: string }) {
  const { data: docs = [], isLoading, error } = useQuery({
    queryKey: ["sources-docs", appId],
    queryFn: () => sourcesApi.listDocuments(appId),
    enabled: !!appId,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <CollapsibleSection
      title="Documents"
      subtitle="Uploaded files (PDFs, Word, plain text, …)"
      icon={File}
      iconColor="text-emerald-500"
      count={docs.length}
      isLoading={isLoading}
      error={error}
      emptyHint="No uploaded documents in this app."
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {docs.map((d) => (
          <ContentSourceCard key={d.source_id} source={d} kind="file" />
        ))}
      </div>
    </CollapsibleSection>
  );
}

// ── Compact cards ──────────────────────────────────────────────────────────────
function ConnectorCard({ source }: { source: Source }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <Database className="w-3.5 h-3.5 text-violet-500 shrink-0" />
          <h3 className="font-semibold text-gray-900 text-xs truncate" title={source.name}>
            {source.name}
          </h3>
        </div>
        {source.is_active ? (
          <CheckCircle className="w-3.5 h-3.5 text-green-500 shrink-0" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-gray-300 shrink-0" />
        )}
      </div>

      <div className="space-y-1 text-[11px] text-gray-500">
        <span className="inline-block px-1.5 py-0.5 bg-gray-100 rounded-full font-mono text-[10px]">
          {source.type}
        </span>
        <div className="flex items-center gap-1">
          <FileText className="w-3 h-3 text-gray-400" />
          <span>{source.records_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1">
          <HardDrive className="w-3 h-3 text-gray-400" />
          <span>{formatBytes(source.size)}</span>
        </div>
      </div>

      <p
        className="mt-1.5 pt-1.5 border-t border-gray-100 text-[10px] text-gray-400 font-mono truncate"
        title={source.connector_id}
      >
        {source.connector_id}
      </p>
    </div>
  );
}

function ContentSourceCard({
  source,
  kind,
}: {
  source: ContentSource;
  kind: "web" | "file";
}) {
  const Icon = kind === "web" ? Globe : File;
  const accent = kind === "web" ? "text-sky-500" : "text-emerald-500";
  const displayUrl = source.base_url || source.sample_url;
  const itemLabel = kind === "web" ? "pages" : "docs";

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className={`w-3.5 h-3.5 ${accent} shrink-0`} />
        <h3 className="font-semibold text-gray-900 text-xs truncate" title={source.name}>
          {source.name}
        </h3>
      </div>

      <div className="space-y-1 text-[11px] text-gray-500">
        <span className="inline-block px-1.5 py-0.5 bg-gray-100 rounded-full font-mono text-[10px]">
          {source.sys_content_type}
        </span>
        <div className="flex items-center gap-1">
          <FileText className="w-3 h-3 text-gray-400" />
          <span>{source.records_count.toLocaleString()} {itemLabel}</span>
        </div>
        {displayUrl && (
          <a
            href={displayUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-violet-600 hover:text-violet-800 hover:underline truncate"
            title={displayUrl}
          >
            <ExternalLink className="w-3 h-3 shrink-0" />
            <span className="truncate">{displayUrl}</span>
          </a>
        )}
      </div>

      <p
        className="mt-1.5 pt-1.5 border-t border-gray-100 text-[10px] text-gray-400 font-mono truncate"
        title={source.source_id}
      >
        {source.source_id}
      </p>
    </div>
  );
}

// ── Collapsible section wrapper ────────────────────────────────────────────────
function CollapsibleSection({
  title,
  subtitle,
  icon: Icon,
  iconColor,
  count,
  isLoading,
  error,
  emptyHint,
  children,
}: {
  title: string;
  subtitle: string;
  icon: typeof Database;
  iconColor: string;
  count: number;
  isLoading: boolean;
  error: unknown;
  emptyHint: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);

  return (
    <section className="space-y-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="group w-full flex items-baseline gap-3 text-left"
      >
        <ChevronDown
          className={cn(
            "w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 transition-transform shrink-0 self-center",
            !open && "-rotate-90"
          )}
        />
        <Icon className={`w-4 h-4 ${iconColor} self-center`} />
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {!isLoading && !error && (
          <span className="text-xs text-gray-400">
            {count === 0 ? "none" : `${count} ${count === 1 ? "source" : "sources"}`}
          </span>
        )}
        <p className="text-xs text-gray-400 hidden sm:inline">— {subtitle}</p>
      </button>

      {open && (
        isLoading ? (
          <div className="flex items-center gap-2 py-5 text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg justify-center">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading {title.toLowerCase()}…
          </div>
        ) : error ? (
          <SectionError error={error} />
        ) : count === 0 ? (
          <div className="text-center py-6 border-2 border-dashed border-gray-200 rounded-lg">
            <Icon className={`w-7 h-7 ${iconColor} opacity-30 mx-auto mb-1.5`} />
            <p className="text-xs text-gray-500">{emptyHint}</p>
          </div>
        ) : (
          children
        )
      )}
    </section>
  );
}

function SectionError({ error }: { error: unknown }) {
  const axiosError = error as { response?: { data?: { detail?: string }; status?: number }; message: string };
  const detail = axiosError.response?.data?.detail ?? axiosError.message;
  const status = axiosError.response?.status;
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 space-y-1">
      <p className="font-medium">
        {status === 502 ? "Could not reach the Kore.ai API" : "Failed to load"}
      </p>
      <p className="text-red-500">{detail}</p>
    </div>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
        <p className="text-sm text-gray-500 mt-1">
          Everything indexed by this Kore.ai app — connectors, web crawls, and uploaded files.
        </p>
      </div>
      {children}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
