import { type JSX, useMemo } from "react";

/**
 * Minimal, dependency-free markdown renderer for trusted LLM output.
 *
 * Supports — only what the insights prompt produces:
 *   - ATX headings  (#, ##, ###)
 *   - Bullet lists  (- foo, * foo)
 *   - Ordered lists (1. foo)
 *   - Bold (**x**), italic (*x*), inline code (`x`)
 *   - Paragraphs
 *
 * Does NOT support: tables, fenced code blocks, blockquotes, links/images,
 * raw HTML. The system prompt explicitly outputs only the supported subset.
 *
 * The renderer is parser-style (not regex-replace) so nested inline emphasis
 * inside list items / headings works.
 */

interface MdProps {
  text: string;
  /** Optional extra Tailwind classes applied to the outer wrapper */
  className?: string;
}

export default function Markdown({ text, className }: MdProps) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  return (
    <div className={"prose-sm max-w-none text-sm text-gray-800 leading-relaxed " + (className ?? "")}>
      {blocks.map((b, i) => renderBlock(b, i))}
    </div>
  );
}

// ── Block model ──────────────────────────────────────────────────────────────

type Block =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] };

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }

    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) {
      blocks.push({
        kind: "heading",
        level: h[1].length as 1 | 2 | 3,
        text: h[2].trim(),
      });
      i++;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, "").trim());
        i++;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, "").trim());
        i++;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    // Paragraph — collect adjacent non-empty, non-block-starter lines
    const paraLines: string[] = [line];
    i++;
    while (
      i < lines.length
      && lines[i].trim()
      && !/^(#{1,3}\s|[-*]\s|\d+\.\s)/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    blocks.push({ kind: "paragraph", text: paraLines.join(" ") });
  }

  return blocks;
}

// ── Block renderers ──────────────────────────────────────────────────────────

function renderBlock(b: Block, key: number): JSX.Element {
  if (b.kind === "heading") {
    const sizeCls =
      b.level === 1 ? "text-base font-bold mt-4 mb-2"
      : b.level === 2 ? "text-sm font-bold mt-3 mb-1.5 text-gray-900 border-b border-gray-100 pb-1"
      : "text-sm font-semibold mt-2.5 mb-1 text-gray-700";
    return (
      <div key={key} className={sizeCls}>
        {renderInline(b.text)}
      </div>
    );
  }
  if (b.kind === "ul") {
    return (
      <ul key={key} className="list-disc pl-5 my-1.5 space-y-1">
        {b.items.map((it, i) => (
          <li key={i} className="text-sm text-gray-700">{renderInline(it)}</li>
        ))}
      </ul>
    );
  }
  if (b.kind === "ol") {
    return (
      <ol key={key} className="list-decimal pl-5 my-1.5 space-y-1">
        {b.items.map((it, i) => (
          <li key={i} className="text-sm text-gray-700">{renderInline(it)}</li>
        ))}
      </ol>
    );
  }
  return (
    <p key={key} className="text-sm text-gray-700 my-1.5 leading-relaxed">
      {renderInline(b.text)}
    </p>
  );
}

// ── Inline tokenizer (bold, italic, code) ────────────────────────────────────

type InlineToken =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "italic"; value: string }
  | { kind: "code"; value: string };

function tokeniseInline(text: string): InlineToken[] {
  const out: InlineToken[] = [];
  let i = 0;
  while (i < text.length) {
    if (text.startsWith("**", i)) {
      const end = text.indexOf("**", i + 2);
      if (end > i + 2) {
        out.push({ kind: "bold", value: text.slice(i + 2, end) });
        i = end + 2;
        continue;
      }
    }
    if (text[i] === "*") {
      const end = text.indexOf("*", i + 1);
      if (end > i + 1) {
        out.push({ kind: "italic", value: text.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    if (text[i] === "`") {
      const end = text.indexOf("`", i + 1);
      if (end > i + 1) {
        out.push({ kind: "code", value: text.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    // Coalesce a run of plain text up to the next special character
    let j = i + 1;
    while (j < text.length && !["*", "`"].includes(text[j])) j++;
    out.push({ kind: "text", value: text.slice(i, j) });
    i = j;
  }
  return out;
}

function renderInline(text: string): JSX.Element[] {
  const tokens = tokeniseInline(text);
  return tokens.map((t, i) => {
    if (t.kind === "bold")   return <strong key={i} className="font-semibold text-gray-900">{t.value}</strong>;
    if (t.kind === "italic") return <em key={i} className="italic text-gray-700">{t.value}</em>;
    if (t.kind === "code")   return (
      <code key={i} className="px-1 py-0.5 bg-gray-100 text-gray-800 rounded font-mono text-[0.85em]">
        {t.value}
      </code>
    );
    return <span key={i}>{t.value}</span>;
  });
}
