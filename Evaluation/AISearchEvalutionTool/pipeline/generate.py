from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.progress import track

from agents.generator import generate_test_cases
from agents.ranker import rank_test_cases
from agents.summarizer import summarize_document
from db.database import (
    create_golden_set,
    insert_agent_scores,
    insert_source_document,
    insert_test_case,
)
from koreai.content import fetch_documents

console = Console()


def run_generation_pipeline(
    golden_set_version: str,
    doc_filters: dict[str, Any] | None = None,
    max_docs: int = 10,
) -> dict[str, Any]:
    """
    Full generation pipeline: fetch docs → Agent 1 → Agent 2 → Agent 3 → persist.
    Returns summary stats.
    """
    create_golden_set(golden_set_version)

    console.print(f"\n[bold]Starting generation pipeline[/bold] — golden set [cyan]{golden_set_version}[/cyan]")

    docs = list(fetch_documents(filters=doc_filters, max_docs=max_docs))
    console.print(f"Fetched [green]{len(docs)}[/green] documents from Kore.ai")

    all_raw_cases: list[dict[str, Any]] = []

    for doc in track(docs, description="Agent 1+2: summarize & generate"):
        insert_source_document(doc)

        extraction = summarize_document(doc)
        console.print(
            f"  [dim]{doc['title'][:60]}[/dim] → "
            f"{len(extraction.get('atomic_claims', []))} claims"
        )

        raw_cases = generate_test_cases(extraction, doc)
        for tc in raw_cases:
            tc["golden_set_version"] = golden_set_version
        all_raw_cases.extend(raw_cases)

    console.print(f"\nGenerated [yellow]{len(all_raw_cases)}[/yellow] raw test cases — ranking...")

    scored = rank_test_cases(all_raw_cases)

    score_map = {s["tc_id"]: s for s in scored}

    kept = borderline = dropped = 0
    for tc in all_raw_cases:
        tc_id = tc["tc_id"]
        score = score_map.get(tc_id, {})
        decision = score.get("decision", "DROP")

        if decision in ("KEEP", "BORDERLINE"):
            insert_test_case(tc)
            insert_agent_scores({**score, "tc_id": tc_id})
            if decision == "KEEP":
                kept += 1
            else:
                borderline += 1
        else:
            dropped += 1

    console.print(
        f"\n[bold]Generation complete[/bold]\n"
        f"  KEEP:       [green]{kept}[/green]\n"
        f"  BORDERLINE: [yellow]{borderline}[/yellow] (needs human review)\n"
        f"  DROPPED:    [red]{dropped}[/red]"
    )

    return {"kept": kept, "borderline": borderline, "dropped": dropped, "total_raw": len(all_raw_cases)}
