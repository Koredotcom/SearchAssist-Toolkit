"""One-off probe: Advance Search with answerSearch=false (extract mode)."""
from __future__ import annotations

import json
import sys

import httpx

from db.database import get_app
from koreai.client import get_headers
from koreai.search import query_rag

APP_ID = sys.argv[1] if len(sys.argv) > 1 else "app-7dc1d609-cf08-4eb3-90f5-e2716448bcd7"
QUESTION = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "What error is linked to a Backup Exec job failing 5 times over the last month?"
)


def main() -> None:
    app = get_app(APP_ID)
    if not app:
        print("App not found:", APP_ID)
        sys.exit(1)

    app = {**app, "answer_mode": "extract_only"}
    url = f"{app['host_url'].rstrip('/')}/api/public/bot/{app['bot_id']}/search/v2/advanced-search"
    payload = {
        "query": QUESTION,
        "answerSearch": False,
        "searchResults": True,
        "includeChunksInResponse": True,
        "maxNumOfChunks": 100,
    }
    print("POST", url)
    print("payload:", json.dumps(payload, indent=2))

    with httpx.Client(timeout=90.0) as client:
        r = client.post(url, json=payload, headers=get_headers(app["jwt_token"]))
        print("status:", r.status_code)
        if not r.is_success:
            print(r.text[:800])
            sys.exit(1)
        raw = r.json()

    template = raw.get("template") or {}
    chunks = template.get("chunk_result") or []
    print("\n=== Raw response summary ===")
    print("top-level keys:", list(raw.keys()))
    print("template keys:", list(template.keys()))
    print("chunk_result count:", len(chunks))
    print("llmResponseTime:", raw.get("llmResponseTime"))
    print("retrievalResponseTime:", raw.get("retrievalResponseTime"))

    ad = template.get("answer_details") or {}
    resp = ad.get("response") or {} if isinstance(ad, dict) else {}
    ans = (resp.get("answer") or "") if isinstance(resp, dict) else ""
    print("generated answer present:", bool(ans), "len:", len(ans))

    print("\n=== Top 5 chunks (API order = hierarchy) ===")
    for i, ch in enumerate(chunks[:5]):
        src = (ch.get("_source") or {}) if isinstance(ch, dict) else {}
        txt = src.get("chunkText") or ""
        print(f"[{i + 1}] docId={src.get('docId')} score={ch.get('_score')} "
              f"qualified={src.get('chunkQualified')} text_len={len(txt)}")

    parsed = query_rag(app, QUESTION)
    print("\n=== Our parser (query_rag) ===")
    print("cited_doc_ids[:5]:", (parsed.get("cited_doc_ids") or [])[:5])
    print("chunk_signals count:", len(parsed.get("chunk_signals") or []))
    sig0 = (parsed.get("chunk_signals") or [{}])[0]
    print("first signal keys:", list(sig0.keys()))
    print("answer preview:", repr((parsed.get("answer") or "")[:200]))


if __name__ == "__main__":
    main()
