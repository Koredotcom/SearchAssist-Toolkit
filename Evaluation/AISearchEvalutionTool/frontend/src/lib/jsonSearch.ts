/** All start indices of case-insensitive matches in text. */
export function findMatchIndices(text: string, query: string): number[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const lower = text.toLowerCase();
  const indices: number[] = [];
  let pos = 0;
  while (pos < lower.length) {
    const i = lower.indexOf(q, pos);
    if (i === -1) break;
    indices.push(i);
    pos = i + 1;
  }
  return indices;
}

export function jsonSubtreeMatches(value: unknown, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (value === null || value === undefined) return "null".includes(q);
  if (typeof value === "string") return value.toLowerCase().includes(q);
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value).toLowerCase().includes(q);
  }
  if (Array.isArray(value)) return value.some((v) => jsonSubtreeMatches(v, query));
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).some(
      ([k, v]) => k.toLowerCase().includes(q) || jsonSubtreeMatches(v, query),
    );
  }
  return false;
}
