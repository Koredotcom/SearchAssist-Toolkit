from __future__ import annotations

import json
from typing import Any

import anthropic

from config import get_config

SYSTEM_PROMPT = """You are a test-case quality auditor for a RAG evaluation framework. Score each test case against a 6-dimensional rubric. Be strict — downstream evaluation only works if test cases are clean.

RUBRIC (score 1-5 each):

1. CLARITY
   1 = unparseable or multiple distinct interpretations
   3 = minor ambiguity, intent recoverable
   5 = single unambiguous interpretation

2. SPECIFICITY
   1 = generic ("tell me about X")
   3 = partially scoped
   5 = references specific entity / time / value / context

3. MEANINGFULNESS
   1 = trivial, tautological, or answerable from the question alone
   3 = reasonable but tests only surface retrieval
   5 = tests meaningful retrieval + reasoning

4. ANSWERABILITY
   1 = contradicts the cited source
   3 = partially supported; requires inference beyond source
   5 = fully derivable from source (or correctly tagged as unanswerable/refusal)

5. REFERENCE_VERIFIABILITY
   1 = reference_doc_ids missing or don't support the question
   3 = partial coverage
   5 = every fact traces cleanly to reference_doc_ids

6. ANSWER_UNIQUENESS
   1 = multiple equally-valid answers (unintended ambiguity)
   3 = one preferred but alternatives possible
   5 = single canonical answer (or by-design CLARIFY case)

DECISION RULES:
KEEP      if: all dims >= 3 AND (clarity+specificity+meaningfulness) >= 12 AND answerability == 5 AND reference_verifiability >= 4
BORDERLINE if: meets KEEP within 1 point on exactly one dimension
DROP      otherwise

OUTPUT — JSON array ONLY, one object per input test case:
[
  {
    "tc_id": "...",
    "scores": {
      "clarity": int,
      "specificity": int,
      "meaningfulness": int,
      "answerability": int,
      "reference_verifiability": int,
      "answer_uniqueness": int
    },
    "decision": "KEEP"|"BORDERLINE"|"DROP",
    "primary_concern": "dimension name or null",
    "rationale": "one-sentence justification"
  }
]"""


def rank_test_cases(
    test_cases: list[dict[str, Any]],
    batch_size: int = 10,
) -> list[dict[str, Any]]:
    """Run Agent 3 on all test cases. Returns scored list."""
    cfg = get_config()
    client = anthropic.Anthropic()

    scored: list[dict[str, Any]] = []

    for i in range(0, len(test_cases), batch_size):
        batch = test_cases[i : i + batch_size]

        batch_payload = [
            {
                "tc_id": tc.get("tc_id"),
                "question": tc.get("question"),
                "expected_answer": tc.get("expected_answer"),
                "expected_behavior": tc.get("expected_behavior"),
                "question_type": tc.get("question_type"),
                "reference_doc_ids": tc.get("reference_doc_ids"),
                "rationale": tc.get("rationale"),
            }
            for tc in batch
        ]

        user_msg = f"Score these {len(batch)} test cases:\n\n{json.dumps(batch_payload, indent=2)}"

        message = client.messages.create(
            model=cfg.agent_model,
            max_tokens=2500,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = message.content[0].text.strip()
        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            results = json.loads(raw[start:end])

        scored.extend(results)

    return scored
