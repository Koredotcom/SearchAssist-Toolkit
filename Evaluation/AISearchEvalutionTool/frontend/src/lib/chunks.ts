/** Per-chunk retrieval signal (matches backend koreai/search.py parser). */
export interface ChunkSignal {
  chunkId?: string | null;
  docId?: string | null;
  chunkText?: string | null;
  score?: number | null;
  vector_score?: number | null;
  keyword_score?: number | null;
  positional_score?: number | null;
  chunkQualified?: boolean | null;
  sentToLLM?: boolean | null;
  usedInAnswer?: boolean | null;
  recordUrl?: string | null;
  recordTitle?: string | null;
}

function safeDict(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

/** Parse template.chunk_result from a Kore.ai search_response (same logic as backend). */
export function chunkSignalsFromSearchResponse(
  raw: Record<string, unknown> | null | undefined,
): ChunkSignal[] {
  if (!raw || typeof raw !== "object") return [];
  const template = safeDict(raw.template);
  const chunkResult = template.chunk_result;
  if (!Array.isArray(chunkResult)) return [];

  const out: ChunkSignal[] = [];
  for (const chunk of chunkResult) {
    if (!chunk || typeof chunk !== "object") continue;
    const c = chunk as Record<string, unknown>;
    const src = safeDict(c._source);
    const chunkText =
      (src.chunkText as string | undefined) ??
      (src.chunkContent as string | undefined) ??
      (src.chunk_content as string | undefined) ??
      (src.content as string | undefined) ??
      (src.text as string | undefined) ??
      "";
    out.push({
      chunkId: (src.chunkId as string | null) ?? null,
      docId: ((src.docId ?? src.doc_id) as string | null) ?? null,
      chunkText: chunkText || null,
      score: typeof c._score === "number" ? c._score : null,
      vector_score: typeof c.vector_search_score === "number" ? c.vector_search_score : null,
      keyword_score: typeof c.keyword_search_score === "number" ? c.keyword_search_score : null,
      positional_score: typeof c.positional_score === "number" ? c.positional_score : null,
      chunkQualified: typeof src.chunkQualified === "boolean" ? src.chunkQualified : null,
      sentToLLM: typeof src.sentToLLM === "boolean" ? src.sentToLLM : null,
      usedInAnswer: typeof src.usedInAnswer === "boolean" ? src.usedInAnswer : null,
      recordUrl: (src.recordUrl as string | null) ?? null,
      recordTitle: (src.recordTitle as string | null) ?? null,
    });
  }
  return out;
}

export function resolveChunkSignals(
  stored: ChunkSignal[] | null | undefined,
  searchResponse: Record<string, unknown> | null | undefined,
): ChunkSignal[] {
  if (stored && stored.length > 0) return stored;
  return chunkSignalsFromSearchResponse(searchResponse);
}

/** Fields needed to show the evaluation-run snapshot in the live query panel. */
export interface EvalSnapshotInput {
  rag_response?: string | null;
  retrieved_doc_ids?: string[];
  search_response?: Record<string, unknown> | null;
  chunk_signals?: ChunkSignal[];
  latency_llm_ms?: number | null;
  latency_retrieval_ms?: number | null;
  search_payload?: Record<string, unknown> | null;
  answer_mode?: string;
}

export function evalSnapshotToQueryView(input: EvalSnapshotInput) {
  const chunks = resolveChunkSignals(input.chunk_signals, input.search_response ?? undefined);
  const raw = input.search_response ?? {};
  const hasRaw = Object.keys(raw).length > 0;
  const hasAnswer = Boolean(input.rag_response?.trim());
  if (!chunks.length && !hasRaw && !hasAnswer) return null;

  return {
    answer: input.rag_response ?? "",
    is_valid_answer: hasAnswer,
    cited_doc_ids: input.retrieved_doc_ids ?? [],
    result_doc_ids: input.retrieved_doc_ids ?? [],
    chunk_signals: chunks,
    answer_mode: input.answer_mode ?? "answer_generation",
    latency_llm_ms: input.latency_llm_ms ?? null,
    latency_retrieval_ms: input.latency_retrieval_ms ?? null,
    search_payload: input.search_payload ?? undefined,
    raw_response: raw,
  };
}

/** Normalize a live /query API response (fill chunks from raw if needed). */
export function normalizeQueryResponse(res: {
  answer: string;
  is_valid_answer: boolean;
  cited_doc_ids: string[];
  result_doc_ids: string[];
  chunk_signals?: ChunkSignal[];
  answer_mode: string;
  latency_llm_ms: number | null;
  latency_retrieval_ms: number | null;
  search_payload?: Record<string, unknown>;
  raw_response?: Record<string, unknown>;
}) {
  return {
    ...res,
    chunk_signals: resolveChunkSignals(res.chunk_signals, res.raw_response),
    raw_response: res.raw_response ?? {},
  };
}

/** chunkQualified=True rows in API order (extract scoring pool). */
export function qualifiedChunks(signals: ChunkSignal[]): ChunkSignal[] {
  return signals.filter((c) => c.chunkQualified === true);
}

/** 1-based rank among qualified chunks for row at ``apiIndex``, or null if not qualified. */
export function qualifiedRank(signals: ChunkSignal[], apiIndex: number): number | null {
  if (signals[apiIndex]?.chunkQualified !== true) return null;
  let rank = 0;
  for (let i = 0; i <= apiIndex; i++) {
    if (signals[i]?.chunkQualified === true) rank += 1;
  }
  return rank;
}
