"""Rule engine — deterministic patterns over a run's diagnostics + raw results.

Each rule inspects the precomputed ``diagnostics`` dict and the list of raw
``eval_result`` rows; if its predicate is satisfied it returns a ``FiredRule``
with severity, human-readable description, evidence test-case ids, and a list
of concrete recommendations.

A rule fires only when it affects ≥ ``MIN_IMPACT_COUNT`` failed cases OR
≥ ``MIN_IMPACT_PCT`` of all failures, so single-case noise is suppressed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

# ── Tunables ────────────────────────────────────────────────────────────────
MIN_IMPACT_COUNT = 3       # rule fires only if ≥ 3 cases affected
MIN_IMPACT_PCT   = 0.20    # …OR ≥ 20% of failures
EVIDENCE_CAP     = 10      # max tc_ids stored per fired rule

# Judge metric → "low" threshold (mean across the run)
JUDGE_LOW_THRESHOLD = 3.5

# Chunk rank thresholds
CHUNK_RANK_BAD_AVG = 30    # avg chunk rank > 30 → ranking problem
CHUNK_RANK_TOP_K   = 5     # cases where chunk rank > 5 but doc was retrieved
                            # → "ranking, not retrieval" failure

# Question-type weakness
WEAK_QTYPE_PASS_RATE = 0.50  # pass rate < 50% on a question_type with ≥ 3 cases


@dataclass
class FiredRule:
    rule_id: str
    severity: str            # 'high' | 'medium' | 'low'
    title: str
    description: str         # one sentence; references actual counts
    impact_count: int        # how many failures this rule explains
    impact_pct: float        # impact_count / total_failures, 0..1
    evidence_tc_ids: list[str]  # up to EVIDENCE_CAP failing tc_ids
    recommendations: list[str]  # concrete actions (1-3 items)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _meets_floor(impact_count: int, total_failures: int) -> bool:
    """Rule must affect ≥ MIN_IMPACT_COUNT cases OR ≥ MIN_IMPACT_PCT of failures."""
    if total_failures <= 0:
        return False
    if impact_count >= MIN_IMPACT_COUNT:
        return True
    return (impact_count / total_failures) >= MIN_IMPACT_PCT


def _verdict_is_fail(r: dict) -> bool:
    return r.get("verdict") == "fail"


def _failed_results(results: list[dict]) -> list[dict]:
    return [r for r in results if _verdict_is_fail(r)]


def _tc_ids(rows: list[dict], cap: int = EVIDENCE_CAP) -> list[str]:
    return [str(r.get("tc_id")) for r in rows[:cap] if r.get("tc_id")]


# ── Individual rules ────────────────────────────────────────────────────────

def _rule_retrieval_miss_dominant(diag: dict, results: list[dict]) -> FiredRule | None:
    """Retrieval miss is the leading failure mode."""
    failures = _failed_results(results)
    total_failures = len(failures)
    miss = [r for r in failures if r.get("failure_category") == "retrieval_miss"]
    n = len(miss)
    if not _meets_floor(n, total_failures):
        return None
    pct = n / total_failures
    return FiredRule(
        rule_id="retrieval_miss_dominant",
        severity="high" if pct >= 0.5 else "medium",
        title="Retrieval miss is your top failure mode",
        description=(
            f"{n} of {total_failures} failures ({pct:.0%}) had the correct document "
            f"missing from the retrieved results entirely."
        ),
        impact_count=n,
        impact_pct=round(pct, 3),
        evidence_tc_ids=_tc_ids(miss),
        recommendations=[
            "Verify the expected documents are actually indexed in your Kore.ai bot.",
            "Re-check chunking strategy — overly small chunks lose context, "
            "overly large chunks dilute relevance.",
            "Consider raising the search recall (e.g. broaden filters or increase top-k).",
        ],
    )


def _rule_ranking_not_retrieval(diag: dict, results: list[dict]) -> FiredRule | None:
    """Expected doc IS retrieved but ranked too low (chunk_rank > top-K)."""
    failures = _failed_results(results)
    total_failures = len(failures)
    poorly_ranked = [
        r for r in failures
        if (r.get("expected_doc_rank") is not None
            and isinstance((r.get("scores") or {}).get("chunk_rank"), int)
            and ((r.get("scores") or {}).get("chunk_rank") or 999) > CHUNK_RANK_TOP_K)
    ]
    n = len(poorly_ranked)
    if not _meets_floor(n, total_failures):
        return None
    return FiredRule(
        rule_id="ranking_not_retrieval",
        severity="medium",
        title="Ranking problem, not retrieval",
        description=(
            f"{n} failing cases retrieved the right document but ranked the matching "
            f"chunk outside top-{CHUNK_RANK_TOP_K}. Retrieval works; ranking is the "
            f"bottleneck."
        ),
        impact_count=n,
        impact_pct=round(n / total_failures, 3),
        evidence_tc_ids=_tc_ids(poorly_ranked),
        recommendations=[
            "Tune the keyword / vector / positional score weights in Kore.ai search.",
            "Inspect chunk boundaries — answer-bearing sentences may be split across chunks.",
            "Try alternate retrieval settings (hybrid weights, MMR, re-ranker).",
        ],
    )


def _rule_chunk_rank_too_low_overall(diag: dict, _results: list[dict]) -> FiredRule | None:
    """Average chunk rank is poor across the whole run."""
    avg = diag.get("retrieval", {}).get("avg_chunk_rank")
    n_with_rank = diag.get("retrieval", {}).get("cases_with_chunk_rank", 0)
    if avg is None or n_with_rank < MIN_IMPACT_COUNT:
        return None
    if avg <= CHUNK_RANK_BAD_AVG:
        return None
    return FiredRule(
        rule_id="chunk_rank_too_low_overall",
        severity="medium",
        title="Chunk ranking is consistently poor",
        description=(
            f"Average chunk rank across {n_with_rank} cases is #{avg:.1f} "
            f"(target ≤ {CHUNK_RANK_BAD_AVG}). The correct content is buried."
        ),
        impact_count=n_with_rank,
        impact_pct=0.0,
        evidence_tc_ids=[],
        recommendations=[
            "Consider adding a re-ranker (e.g. cross-encoder) on top of retrieval.",
            "Boost keyword score weight if your domain uses precise terminology.",
            "Audit the top-ranked chunks for off-topic content competing with the answer.",
        ],
    )


def _rule_low_judge_metric(diag: dict, _results: list[dict]) -> list[FiredRule]:
    """Any judge metric whose run-wide average falls below JUDGE_LOW_THRESHOLD."""
    judge_avgs = diag.get("judge_metric_avgs") or {}
    fired: list[FiredRule] = []
    metric_labels = {
        "groundedness":           ("answers may be hallucinating",
                                   "Inspect failing cases — answers cite facts not in the retrieved docs."),
        "query_relevance":        ("answers drift off-topic",
                                   "Check whether retrieval returns docs even loosely related to the question."),
        "ground_truth_relevance": ("answers diverge from expected ground truth",
                                   "Inspect the prompt — the LLM may be paraphrasing into different facts."),
        "coherence":              ("answer structure is fragmented",
                                   "Consider a different generator model or improve prompt clarity."),
        "fluency":                ("answer grammar / readability is poor",
                                   "Try a larger generator model."),
        "completeness":           ("answers are incomplete vs. ground truth",
                                   "Raise the top-k or chunk size — the LLM may be missing context."),
    }
    for key, avg in judge_avgs.items():
        if not isinstance(avg, (int, float)):
            continue
        if avg >= JUDGE_LOW_THRESHOLD:
            continue
        title_extra, rec = metric_labels.get(key, ("", "Investigate failing cases for this metric."))
        fired.append(FiredRule(
            rule_id=f"low_judge_{key}",
            severity="medium" if avg >= 2.5 else "high",
            title=f"Weak judge metric: {key.replace('_', ' ').title()}",
            description=(
                f"Average {key.replace('_', ' ')} score is {avg:.2f}/5 "
                f"(threshold {JUDGE_LOW_THRESHOLD}) — {title_extra}."
            ),
            impact_count=0,  # metric-level, not per-case
            impact_pct=0.0,
            evidence_tc_ids=[],
            recommendations=[rec],
        ))
    return fired


def _rule_safety_violations(_diag: dict, results: list[dict]) -> FiredRule | None:
    """Any toxicity / bias / banned-topic flag fires."""
    flagged = [
        r for r in results
        if (r.get("scores") or {}).get("toxicity_detected") is True
        or (r.get("scores") or {}).get("bias_detected") is True
        or (r.get("scores") or {}).get("banned_topic_violation") is True
    ]
    n = len(flagged)
    if n == 0:
        return None
    return FiredRule(
        rule_id="safety_violations_detected",
        severity="high",
        title="Safety violations detected",
        description=(
            f"{n} answer{'s' if n != 1 else ''} were flagged for toxicity, bias, "
            f"or banned-topic violation."
        ),
        impact_count=n,
        impact_pct=0.0,
        evidence_tc_ids=_tc_ids(flagged),
        recommendations=[
            "Review the flagged answers — even small numbers indicate an unsafe path.",
            "Tighten the safety prompt for the generator and/or expand banned_topics.",
        ],
    )


def _rule_weak_question_types(diag: dict, results: list[dict]) -> list[FiredRule]:
    """Question types where pass rate < threshold AND ≥ MIN_IMPACT_COUNT cases."""
    by_qtype = diag.get("by_question_type") or {}
    fired: list[FiredRule] = []
    for qtype, stats in by_qtype.items():
        total = stats.get("total", 0)
        passed = stats.get("passed", 0)
        rate = stats.get("pass_rate", 0.0)
        if total < MIN_IMPACT_COUNT:
            continue
        if rate >= WEAK_QTYPE_PASS_RATE:
            continue
        evidence = [
            r for r in results
            if r.get("question_type") == qtype and _verdict_is_fail(r)
        ]
        fired.append(FiredRule(
            rule_id=f"weak_qtype_{qtype}",
            severity="high" if rate < 0.3 else "medium",
            title=f"Weak performance on '{qtype}' questions",
            description=(
                f"Only {passed}/{total} '{qtype}' questions passed ({rate:.0%}) — "
                f"well below the {WEAK_QTYPE_PASS_RATE:.0%} floor."
            ),
            impact_count=total - passed,
            impact_pct=round((total - passed) / max(len(_failed_results(results)), 1), 3),
            evidence_tc_ids=_tc_ids(evidence),
            recommendations=_qtype_recommendations(qtype),
        ))
    return fired


def _qtype_recommendations(qtype: str) -> list[str]:
    base = {
        "multi_hop":   [
            "Multi-hop questions need cross-chunk reasoning. Increase top-k chunks sent to the LLM.",
            "Check if chunking splits the linked facts across documents.",
        ],
        "comparative": [
            "Comparative questions need both items retrieved together. Ensure both are top-ranked.",
            "Inspect whether your retrieval returns docs from a single entity only.",
        ],
        "boundary":    [
            "Boundary/edge-case questions test exact numerics. Verify the chunk containing the number is retrieved.",
            "Consider a numerical re-ranker or keyword boost for digits/units.",
        ],
        "factual":     [
            "Factual questions should be the easiest. Look for retrieval misses first.",
        ],
        "follow_up":   [
            "Follow-up questions may depend on context not present in the corpus.",
            "Inspect whether the prompt provides enough disambiguation.",
        ],
    }
    return base.get(qtype, [
        f"Inspect failing '{qtype}' cases — pattern may be retrieval, ranking, or generation.",
    ])


def _rule_case_imbalance(diag: dict, _results: list[dict]) -> FiredRule | None:
    """One of the 4 evaluation cases is failing much more than others."""
    by_case = diag.get("by_case") or {}
    if not by_case:
        return None
    worst = None
    worst_rate = 1.0
    for case_id_str, stats in by_case.items():
        total = stats.get("total", 0)
        if total < MIN_IMPACT_COUNT:
            continue
        rate = stats.get("pass_rate", 0.0)
        if rate < worst_rate:
            worst_rate = rate
            worst = (case_id_str, stats)
    if worst is None or worst_rate >= 0.5:
        return None
    case_id_str, stats = worst
    case_meanings = {
        "1": "question-only (no expected answer / doc)",
        "2": "answer-correctness (Q + expected answer)",
        "3": "retrieval (Q + reference doc)",
        "4": "full evaluation (Q + answer + reference doc)",
    }
    return FiredRule(
        rule_id=f"case_{case_id_str}_imbalance",
        severity="medium",
        title=f"Case {case_id_str} dragging down the run",
        description=(
            f"Case {case_id_str} ({case_meanings.get(case_id_str, '?')}) is passing only "
            f"{stats.get('passed', 0)}/{stats.get('total', 0)} = {worst_rate:.0%} — "
            f"materially worse than other cases."
        ),
        impact_count=stats.get("failed", 0),
        impact_pct=round(stats.get("failed", 0) / max(len(_failed_results(_results)), 1), 3),
        evidence_tc_ids=[],
        recommendations=[
            f"Filter to case_id={case_id_str} on the results page and inspect failing cases together.",
            "Check whether your golden-set composition skews toward harder examples for this case.",
        ],
    )


def _rule_no_verdict_blind_spot(_diag: dict, results: list[dict]) -> FiredRule | None:
    """Many rows have no verdict — embeddings unavailable + no judge."""
    null_verdicts = [r for r in results if r.get("verdict") not in ("pass", "fail")]
    n = len(null_verdicts)
    if n < MIN_IMPACT_COUNT:
        return None
    pct = n / max(len(results), 1)
    if pct < 0.10:
        return None
    return FiredRule(
        rule_id="no_verdict_blind_spot",
        severity="low",
        title="Many cases have no pass/fail verdict",
        description=(
            f"{n} of {len(results)} cases ({pct:.0%}) ended without a verdict — "
            f"usually Case 1 rows that couldn't run the embedding model."
        ),
        impact_count=n,
        impact_pct=round(pct, 3),
        evidence_tc_ids=_tc_ids(null_verdicts),
        recommendations=[
            "Configure an LLM judge to verdict Case 1 rows.",
            "Or add expected_answers to Case 1 rows so they become Case 2 (verdictable).",
        ],
    )


# Registry — order matters only for display
_RULES = [
    _rule_retrieval_miss_dominant,
    _rule_ranking_not_retrieval,
    _rule_chunk_rank_too_low_overall,
    _rule_safety_violations,
    _rule_case_imbalance,
    _rule_no_verdict_blind_spot,
]


def evaluate_rules(diagnostics: dict, results: list[dict]) -> list[FiredRule]:
    """Run every rule against the diagnostics + raw results, return fired ones."""
    fired: list[FiredRule] = []
    for rule in _RULES:
        out = rule(diagnostics, results)
        if out is None:
            continue
        if isinstance(out, list):
            fired.extend(out)
        else:
            fired.append(out)
    fired.extend(_rule_low_judge_metric(diagnostics, results))
    fired.extend(_rule_weak_question_types(diagnostics, results))
    severity_order = {"high": 0, "medium": 1, "low": 2}
    fired.sort(key=lambda r: (severity_order.get(r.severity, 9), -r.impact_count))
    return fired
