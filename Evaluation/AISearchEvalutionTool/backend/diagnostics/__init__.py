"""Phase 2 — deterministic diagnostics + AI deep-dive narrative for eval runs.

Module surface:
  - compute.compute_run_diagnostics(run_id)         → dict
  - compute.compute_and_store_diagnostics(run_id)   → dict (also persists)
  - rules.evaluate_rules(diagnostics, results)      → list[FiredRule]
  - trends.compute_run_trends(run_id)               → dict (vs previous run)
"""

from diagnostics.compute import (  # re-export for convenience
    compute_and_store_diagnostics,
    compute_run_diagnostics,
)
from diagnostics.trends import compute_run_trends

__all__ = [
    "compute_run_diagnostics",
    "compute_and_store_diagnostics",
    "compute_run_trends",
]
