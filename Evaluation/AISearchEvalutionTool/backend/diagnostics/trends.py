"""Cross-run trend computation.

A "trend" compares the current run against the most recent prior completed
run for the same (app_id, golden_set_version). It is computed on-demand and
NOT cached, since adding a new run could change the answer for older runs.
"""
from __future__ import annotations

import logging
from typing import Any

from db.database import get_eval_run, get_previous_completed_run, get_run_diagnostics
from diagnostics.compute import compute_and_store_diagnostics

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────────────────

def compute_run_trends(run_id: str) -> dict[str, Any]:
    """Return a ``RunTrend`` dict comparing ``run_id`` to its predecessor.

    Shape:
      {
        "run_id":             "...",
        "previous_run_id":    "...",        # null if no baseline exists
        "previous_run_date":  "ISO ts",     # null if no baseline
        "golden_set_version": "1.2.0",
        "has_baseline":       true,
        "deltas": {
           "pass_rate":           {"current": .., "previous": .., "delta": .., "direction": "better|worse|same"},
           "total_cases":         {...},
           "failed_cases":        {...},
           "avg_chunk_rank":      {...},          # nullable; direction is inverted (lower = better)
           "weakest_judge_metric": {"current": "...", "previous": "..."},
           "failures_by_category": {  cat:  {current, previous, delta, direction}, ... },
           "judge_metric_avgs":    {  metric: {current, previous, delta, direction}, ... },
        }
      }
    """
    current = get_eval_run(run_id)
    if not current:
        raise ValueError(f"run_id {run_id} not found")

    previous = get_previous_completed_run(
        app_id=current["app_id"],
        golden_set_version=current["golden_set_version"],
        before_run_id=run_id,
    )

    cur_diag = _ensure_diagnostics(run_id)
    if not previous:
        return _empty_trends(run_id, current, cur_diag)

    prev_diag = _ensure_diagnostics(previous["run_id"])

    return {
        "run_id":             run_id,
        "previous_run_id":    previous["run_id"],
        "previous_run_date":  previous.get("finished_at") or previous.get("started_at"),
        "golden_set_version": current["golden_set_version"],
        "has_baseline":       True,
        "deltas":             _compute_deltas(cur_diag, prev_diag),
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

def _ensure_diagnostics(run_id: str) -> dict[str, Any]:
    """Load cached diagnostics, computing+caching on miss (lazy backfill)."""
    diag, _fired = get_run_diagnostics(run_id)
    if diag is not None:
        return diag
    return compute_and_store_diagnostics(run_id)


def _empty_trends(run_id: str, run_row: dict, cur_diag: dict) -> dict[str, Any]:
    """Trend payload when there's no baseline (first run on this golden set)."""
    return {
        "run_id":             run_id,
        "previous_run_id":    None,
        "previous_run_date":  None,
        "golden_set_version": run_row["golden_set_version"],
        "has_baseline":       False,
        "deltas":             _identity_deltas(cur_diag),
    }


def _identity_deltas(cur: dict) -> dict[str, Any]:
    """When no baseline exists, populate ``current`` with previous=None throughout.

    Frontends can rely on the shape being stable; ``direction`` is "same" so
    indicators render flat.
    """
    totals = cur.get("totals") or {}
    retr   = cur.get("retrieval") or {}
    return {
        "pass_rate":           _scalar_delta(totals.get("pass_rate"),       None, lower_is_better=False),
        "total_cases":         _scalar_delta(totals.get("total"),           None, lower_is_better=False),
        "failed_cases":        _scalar_delta(totals.get("failed"),          None, lower_is_better=True),
        "avg_chunk_rank":      _scalar_delta(retr.get("avg_chunk_rank"),    None, lower_is_better=True),
        "weakest_judge_metric": {
            "current":  cur.get("weakest_judge_metric"),
            "previous": None,
            "changed":  False,
        },
        "failures_by_category": {
            cat: _scalar_delta(count, None, lower_is_better=True)
            for cat, count in (cur.get("by_failure_category") or {}).items()
            if cat != "none"
        },
        "judge_metric_avgs": {
            metric: _scalar_delta(val, None, lower_is_better=False)
            for metric, val in (cur.get("judge_metric_avgs") or {}).items()
        },
    }


def _compute_deltas(cur: dict, prev: dict) -> dict[str, Any]:
    """Diff every meaningful field between current and previous diagnostics."""
    cur_totals = cur.get("totals") or {}
    prev_totals = prev.get("totals") or {}
    cur_retr   = cur.get("retrieval") or {}
    prev_retr  = prev.get("retrieval") or {}

    failure_cats = set((cur.get("by_failure_category") or {}).keys()) \
                 | set((prev.get("by_failure_category") or {}).keys())
    failure_cats.discard("none")

    judge_metrics = set((cur.get("judge_metric_avgs") or {}).keys()) \
                  | set((prev.get("judge_metric_avgs") or {}).keys())

    return {
        "pass_rate": _scalar_delta(
            cur_totals.get("pass_rate"), prev_totals.get("pass_rate"),
            lower_is_better=False,
        ),
        "total_cases": _scalar_delta(
            cur_totals.get("total"), prev_totals.get("total"),
            lower_is_better=False,
        ),
        "failed_cases": _scalar_delta(
            cur_totals.get("failed"), prev_totals.get("failed"),
            lower_is_better=True,
        ),
        "avg_chunk_rank": _scalar_delta(
            cur_retr.get("avg_chunk_rank"), prev_retr.get("avg_chunk_rank"),
            lower_is_better=True,
        ),
        "weakest_judge_metric": {
            "current":  cur.get("weakest_judge_metric"),
            "previous": prev.get("weakest_judge_metric"),
            "changed":  cur.get("weakest_judge_metric") != prev.get("weakest_judge_metric"),
        },
        "failures_by_category": {
            cat: _scalar_delta(
                (cur.get("by_failure_category") or {}).get(cat),
                (prev.get("by_failure_category") or {}).get(cat),
                lower_is_better=True,
            )
            for cat in sorted(failure_cats)
        },
        "judge_metric_avgs": {
            metric: _scalar_delta(
                (cur.get("judge_metric_avgs") or {}).get(metric),
                (prev.get("judge_metric_avgs") or {}).get(metric),
                lower_is_better=False,
            )
            for metric in sorted(judge_metrics)
        },
    }


def _scalar_delta(
    current: float | int | None,
    previous: float | int | None,
    lower_is_better: bool,
) -> dict[str, Any]:
    """Build a {current, previous, delta, direction} struct from two values."""
    if not isinstance(current, (int, float)):
        current = None
    if not isinstance(previous, (int, float)):
        previous = None

    delta: float | int | None
    if current is None or previous is None:
        delta = None
    else:
        delta = round(current - previous, 4) if isinstance(current, float) or isinstance(previous, float) else current - previous

    direction = "same"
    if delta is not None and delta != 0:
        if lower_is_better:
            direction = "better" if delta < 0 else "worse"
        else:
            direction = "better" if delta > 0 else "worse"

    return {
        "current":          current,
        "previous":         previous,
        "delta":            delta,
        "direction":        direction,           # 'better' | 'worse' | 'same'
        "lower_is_better":  lower_is_better,     # so the UI knows colour rules
    }
