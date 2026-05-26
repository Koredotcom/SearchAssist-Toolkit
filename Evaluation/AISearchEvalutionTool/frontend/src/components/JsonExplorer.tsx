import {
  useState, useMemo, useEffect, useCallback, type ReactNode,
} from "react";
import {
  Check, Copy, Maximize2, Minimize2, Search, ChevronUp, ChevronDown, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { findMatchIndices, jsonSubtreeMatches } from "@/lib/jsonSearch";

type ViewMode = "tree" | "text";

function HighlightText({
  text,
  query,
  active,
}: {
  text: string;
  query: string;
  active?: boolean;
}) {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  const parts: ReactNode[] = [];
  let pos = 0;
  let key = 0;
  while (pos < text.length) {
    const i = lower.indexOf(needle, pos);
    if (i === -1) {
      parts.push(<span key={key++}>{text.slice(pos)}</span>);
      break;
    }
    if (i > pos) parts.push(<span key={key++}>{text.slice(pos, i)}</span>);
    parts.push(
      <mark
        key={key++}
        className={cn(
          "rounded-sm px-0.5",
          active ? "bg-amber-400 text-gray-900" : "bg-yellow-500/40 text-inherit",
        )}
      >
        {text.slice(i, i + needle.length)}
      </mark>,
    );
    pos = i + needle.length;
  }
  return <>{parts}</>;
}

function JsonNode({
  value,
  depth,
  maxInitialDepth,
  searchQuery,
  isLast,
  pathId,
  activePathId,
}: {
  value: unknown;
  depth: number;
  maxInitialDepth: number;
  searchQuery: string;
  isLast?: boolean;
  pathId: string;
  activePathId: string | null;
}) {
  const q = searchQuery.trim();
  const hasSearch = q.length > 0;
  const subtreeHit = hasSearch ? jsonSubtreeMatches(value, q) : true;
  const [collapsed, setCollapsed] = useState(
    () => depth > maxInitialDepth && !(hasSearch && subtreeHit),
  );

  useEffect(() => {
    if (hasSearch && subtreeHit) setCollapsed(false);
    else if (!hasSearch) setCollapsed(depth > maxInitialDepth);
  }, [hasSearch, subtreeHit, depth, maxInitialDepth]);

  const comma = !isLast ? <span className="text-gray-500">,</span> : null;
  const isActive = activePathId === pathId;

  if (value === null) {
    return (
      <span id={pathId} className={cn(isActive && "ring-1 ring-amber-400/80 rounded")}>
        <span className="text-gray-400">null</span>
        {comma}
      </span>
    );
  }
  if (typeof value === "boolean") {
    return (
      <span id={pathId} className={cn(isActive && "ring-1 ring-amber-400/80 rounded")}>
        <span className="text-blue-300">{String(value)}</span>
        {comma}
      </span>
    );
  }
  if (typeof value === "number") {
    return (
      <span id={pathId} className={cn(isActive && "ring-1 ring-amber-400/80 rounded")}>
        <span className="text-yellow-300">{value}</span>
        {comma}
      </span>
    );
  }
  if (typeof value === "string") {
    return (
      <span id={pathId} className={cn(isActive && "ring-1 ring-amber-400/80 rounded")}>
        <span className="text-emerald-300 break-all">
          "<HighlightText text={value} query={q} active={isActive} />"
        </span>
        {comma}
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <span>
          <span className="text-gray-400">[]</span>
          {comma}
        </span>
      );
    }
    if (hasSearch && !subtreeHit) return null;

    return (
      <span id={pathId}>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="text-gray-500 hover:text-white mr-0.5 select-none leading-none"
        >
          {collapsed ? "▶" : "▼"}
        </button>
        <span className="text-gray-300">[</span>
        {collapsed ? (
          <>
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="mx-1 text-[10px] text-gray-400 hover:text-gray-200 italic"
            >
              {value.length} items
            </button>
            <span className="text-gray-300">]</span>
            {comma}
          </>
        ) : (
          <>
            <div className="ml-4 border-l border-gray-700 pl-2">
              {value.map((v, i) => (
                <div key={i}>
                  <JsonNode
                    value={v}
                    depth={depth + 1}
                    maxInitialDepth={maxInitialDepth}
                    searchQuery={searchQuery}
                    isLast={i === value.length - 1}
                    pathId={`${pathId}[${i}]`}
                    activePathId={activePathId}
                  />
                </div>
              ))}
            </div>
            <span className="text-gray-300">]</span>
            {comma}
          </>
        )}
      </span>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return (
        <span>
          <span className="text-gray-400">{"{}"}</span>
          {comma}
        </span>
      );
    }
    if (hasSearch && !subtreeHit) return null;

    return (
      <span id={pathId}>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="text-gray-500 hover:text-white mr-0.5 select-none leading-none"
        >
          {collapsed ? "▶" : "▼"}
        </button>
        <span className="text-gray-300">{"{"}</span>
        {collapsed ? (
          <>
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="mx-1 text-[10px] text-gray-400 hover:text-gray-200 italic"
            >
              {entries.length} keys
            </button>
            <span className="text-gray-300">{"}"}</span>
            {comma}
          </>
        ) : (
          <>
            <div className="ml-4 border-l border-gray-700 pl-2">
              {entries.map(([k, v], i) => {
                const childPath = `${pathId}.${k}`;
                const keyHit = hasSearch && k.toLowerCase().includes(q.toLowerCase());
                const childHit = hasSearch && jsonSubtreeMatches(v, q);
                if (hasSearch && !keyHit && !childHit) return null;
                return (
                  <div key={k} className="flex flex-wrap gap-x-1 items-start">
                    <span className={cn("shrink-0", keyHit ? "text-amber-300" : "text-sky-300")}>
                      "<HighlightText text={k} query={q} active={activePathId === childPath} />"
                    </span>
                    <span className="text-gray-500 shrink-0">:</span>
                    <span className="min-w-0">
                      <JsonNode
                        value={v}
                        depth={depth + 1}
                        maxInitialDepth={maxInitialDepth}
                        searchQuery={searchQuery}
                        isLast={i === entries.length - 1}
                        pathId={childPath}
                        activePathId={activePathId}
                      />
                    </span>
                  </div>
                );
              })}
            </div>
            <span className="text-gray-300">{"}"}</span>
            {comma}
          </>
        )}
      </span>
    );
  }

  return <span className="text-gray-300">{String(value)}</span>;
}

function TextViewWithSearch({
  text,
  query,
  activeIndex,
}: {
  text: string;
  query: string;
  activeIndex: number;
}) {
  const indices = useMemo(() => findMatchIndices(text, query), [text, query]);
  const q = query.trim();

  const content = useMemo(() => {
    if (!q || indices.length === 0) return text;
    const needle = q.toLowerCase();
    const nodes: ReactNode[] = [];
    let pos = 0;
    let matchNum = 0;
    for (const start of indices) {
      if (start > pos) nodes.push(text.slice(pos, start));
      nodes.push(
        <mark
          key={start}
          id={`json-match-${matchNum}`}
          className={cn(
            "rounded-sm",
            matchNum === activeIndex
              ? "bg-amber-400 text-gray-900 ring-2 ring-amber-300"
              : "bg-yellow-500/50 text-gray-900",
          )}
        >
          {text.slice(start, start + needle.length)}
        </mark>,
      );
      matchNum += 1;
      pos = start + needle.length;
    }
    if (pos < text.length) nodes.push(text.slice(pos));
    return nodes;
  }, [text, q, indices, activeIndex]);

  useEffect(() => {
    if (indices.length === 0) return;
    document.getElementById(`json-match-${activeIndex}`)?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
  }, [activeIndex, indices.length]);

  return (
    <pre className="p-3 text-[11px] font-mono leading-relaxed whitespace-pre-wrap break-all text-gray-100">
      {content}
    </pre>
  );
}

function collectTreeMatchPathIds(value: unknown, query: string, prefix = "$"): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: string[] = [];

  function visit(val: unknown, path: string) {
    if (val === null || val === undefined) {
      if ("null".includes(q)) out.push(path);
      return;
    }
    if (typeof val === "string") {
      if (val.toLowerCase().includes(q)) out.push(path);
      return;
    }
    if (typeof val === "number" || typeof val === "boolean") {
      if (String(val).toLowerCase().includes(q)) out.push(path);
      return;
    }
    if (Array.isArray(val)) {
      val.forEach((item, i) => visit(item, `${path}[${i}]`));
      return;
    }
    if (typeof val === "object") {
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        const p = `${path}.${k}`;
        if (k.toLowerCase().includes(q)) out.push(p);
        visit(v, p);
      }
    }
  }

  visit(value, prefix);
  return out;
}

function ExplorerBody({
  data,
  theme,
  maxHeight,
  fullscreen,
}: {
  data: unknown;
  theme: "dark" | "light";
  maxHeight: string;
  fullscreen: boolean;
}) {
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("tree");
  const [matchIndex, setMatchIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [viewKey, setViewKey] = useState(0);
  const [initDepth, setInitDepth] = useState(1);

  const pretty = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const textMatches = useMemo(() => findMatchIndices(pretty, search), [pretty, search]);
  const treePaths = useMemo(
    () => collectTreeMatchPathIds(data, search),
    [data, search],
  );
  const matchCount = viewMode === "text" ? textMatches.length : treePaths.length;

  useEffect(() => {
    setMatchIndex(0);
  }, [search, viewMode]);

  const goPrev = useCallback(() => {
    if (matchCount === 0) return;
    setMatchIndex((i) => (i - 1 + matchCount) % matchCount);
  }, [matchCount]);

  const goNext = useCallback(() => {
    if (matchCount === 0) return;
    setMatchIndex((i) => (i + 1) % matchCount);
  }, [matchCount]);

  useEffect(() => {
    if (viewMode !== "tree" || treePaths.length === 0) return;
    document.getElementById(treePaths[matchIndex] ?? "")?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
  }, [matchIndex, treePaths, viewMode]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(pretty);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  const isDark = theme === "dark";
  const toolbarBg = isDark ? "bg-gray-900 border-gray-700" : "bg-gray-50 border-gray-200";
  const toolbarText = isDark ? "text-gray-300" : "text-gray-600";
  const inputCls = isDark
    ? "bg-gray-800 border-gray-600 text-gray-100 placeholder:text-gray-500"
    : "bg-white border-gray-300 text-gray-900 placeholder:text-gray-400";

  return (
    <div className={cn("flex flex-col min-h-0", fullscreen && "flex-1")}>
      <div className={cn("flex flex-wrap items-center gap-2 px-3 py-2 border-b shrink-0", toolbarBg)}>
        <div className="flex items-center gap-1.5 flex-1 min-w-[200px]">
          <Search className={cn("w-3.5 h-3.5 shrink-0", isDark ? "text-gray-500" : "text-gray-400")} />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (e.shiftKey) goPrev();
                else goNext();
              }
            }}
            placeholder="Search JSON… (Enter / Shift+Enter)"
            className={cn(
              "flex-1 text-[11px] px-2 py-1 rounded border focus:outline-none focus:ring-1 focus:ring-violet-500 font-mono",
              inputCls,
            )}
          />
          {search.trim() && (
            <span className={cn("text-[10px] font-mono shrink-0", toolbarText)}>
              {matchCount === 0 ? (
                <span className="text-red-400">0</span>
              ) : (
                <>
                  <span className="text-amber-400">{matchIndex + 1}</span>
                  <span className="text-gray-500">/{matchCount}</span>
                </>
              )}
            </span>
          )}
          <button
            type="button"
            onClick={goPrev}
            disabled={matchCount === 0}
            title="Previous match (Shift+Enter)"
            className={cn(
              "p-1 rounded border disabled:opacity-30",
              isDark
                ? "border-gray-600 text-gray-400 hover:text-white"
                : "border-gray-300 text-gray-500 hover:text-gray-800",
            )}
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={goNext}
            disabled={matchCount === 0}
            title="Next match (Enter)"
            className={cn(
              "p-1 rounded border disabled:opacity-30",
              isDark
                ? "border-gray-600 text-gray-400 hover:text-white"
                : "border-gray-300 text-gray-500 hover:text-gray-800",
            )}
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <div
            className={cn(
              "inline-flex rounded border overflow-hidden text-[10px]",
              isDark ? "border-gray-600" : "border-gray-300",
            )}
          >
            {(["tree", "text"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setViewMode(m)}
                className={cn(
                  "px-2 py-0.5 capitalize",
                  viewMode === m
                    ? "bg-violet-600 text-white"
                    : isDark
                      ? "bg-gray-800 text-gray-400 hover:text-gray-200"
                      : "bg-white text-gray-600 hover:bg-gray-100",
                )}
              >
                {m}
              </button>
            ))}
          </div>
          {viewMode === "tree" && (
            <>
              <button
                type="button"
                onClick={() => { setInitDepth(999); setViewKey((k) => k + 1); }}
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded border",
                  isDark ? "border-gray-600 text-gray-400" : "border-gray-300 text-gray-600",
                )}
              >
                Expand all
              </button>
              <button
                type="button"
                onClick={() => { setInitDepth(-1); setViewKey((k) => k + 1); }}
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded border",
                  isDark ? "border-gray-600 text-gray-400" : "border-gray-300 text-gray-600",
                )}
              >
                Collapse all
              </button>
            </>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className={cn(
              "flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border",
              isDark
                ? "border-gray-600 text-gray-400 bg-gray-800"
                : "border-gray-300 text-gray-600 bg-white",
            )}
          >
            {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <div
        className={cn("overflow-auto bg-gray-900 min-h-0", fullscreen ? "flex-1" : "")}
        style={fullscreen ? undefined : { maxHeight }}
      >
        {viewMode === "text" ? (
          <TextViewWithSearch text={pretty} query={search} activeIndex={matchIndex} />
        ) : (
          <div key={viewKey} className="p-3 text-[11px] font-mono leading-relaxed">
            <JsonNode
              value={data}
              depth={0}
              maxInitialDepth={search.trim() ? 999 : initDepth}
              searchQuery={search}
              pathId="$"
              activePathId={treePaths[matchIndex] ?? null}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export interface JsonExplorerProps {
  data: unknown;
  title?: string;
  theme?: "dark" | "light";
  className?: string;
  maxHeight?: string;
}

export default function JsonExplorer({
  data,
  title,
  theme = "dark",
  className,
  maxHeight = "520px",
}: JsonExplorerProps) {
  const [fullscreen, setFullscreen] = useState(false);
  const pretty = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const sizeKb = (pretty.length / 1024).toFixed(1);
  const isDark = theme === "dark";
  const borderCls = isDark ? "border-gray-700" : "border-gray-200";

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [fullscreen]);

  const header = (fs: boolean) => (
    <div
      className={cn(
        "flex items-center justify-between px-3 py-1.5 border-b shrink-0 text-[11px]",
        isDark ? "bg-gray-900 border-gray-700 text-gray-400" : "bg-gray-50 border-gray-200 text-gray-500",
      )}
    >
      <span className="font-medium truncate pr-2">
        {title ?? "JSON"}
        {fs && <span className="text-violet-400 ml-2 font-normal">· Fullscreen</span>}
      </span>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-gray-500 font-mono">{sizeKb} KB</span>
        <button
          type="button"
          onClick={() => setFullscreen((v) => !v)}
          className={cn(
            "flex items-center gap-1 px-2 py-0.5 rounded border transition-colors",
            isDark
              ? "border-gray-600 text-gray-400 hover:text-white"
              : "border-gray-300 text-gray-600 hover:text-gray-800 bg-white",
          )}
        >
          {fs ? (
            <><Minimize2 className="w-3 h-3" /> Exit</>
          ) : (
            <><Maximize2 className="w-3 h-3" /> Fullscreen</>
          )}
        </button>
        {fs && (
          <button
            type="button"
            onClick={() => setFullscreen(false)}
            className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );

  const panel = (fs: boolean) => (
    <div className={cn("flex flex-col min-h-0", fs && "flex-1")}>
      {header(fs)}
      <ExplorerBody data={data} theme={theme} maxHeight={maxHeight} fullscreen={fs} />
    </div>
  );

  return (
    <>
      <div className={cn("rounded-lg border overflow-hidden flex flex-col", borderCls, className)}>
        {panel(false)}
      </div>

      {fullscreen && (
        <div
          className="fixed inset-0 z-[100] flex flex-col bg-gray-950/95 backdrop-blur-sm p-3 md:p-6"
          role="dialog"
          aria-modal="true"
          aria-label={title ?? "JSON explorer"}
        >
          <div className={cn("flex flex-col flex-1 min-h-0 rounded-xl border overflow-hidden shadow-2xl", borderCls)}>
            {panel(true)}
          </div>
          <p className="text-center text-[10px] text-gray-500 mt-2 shrink-0">
            Press <kbd className="px-1 py-0.5 rounded bg-gray-800 text-gray-400">Esc</kbd> to exit
          </p>
        </div>
      )}
    </>
  );
}
