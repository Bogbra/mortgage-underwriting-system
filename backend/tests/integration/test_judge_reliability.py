"""Integration test for the judge reliability calibration harness.

Runs with the offline FakeChatModel (forced by conftest.py) — asserts the
harness's plumbing (fixture loading, agreement scoring) works end to end,
not that the offline heuristic is a calibrated judge. See
`evals/judge_reliability.py` for why this eval exists: measuring whether
the *real* LLM-as-judge is trustworthy needs `--provider openai`.
"""

from __future__ import annotations

from underwriting.evals.judge_reliability import (
    load_judge_reliability_cases,
    run_judge_reliability_eval,
)
from underwriting.llm.fake import FakeChatModel


def test_calibration_cases_are_well_formed():
    cases = load_judge_reliability_cases()
    assert len(cases) >= 4
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert case["context"]
        assert case["claim"]
        assert isinstance(case["expected_grounded"], bool)
        assert case["note"]


def test_run_judge_reliability_eval_scores_agreement_offline():
    summary = run_judge_reliability_eval(llm=FakeChatModel())
    assert summary["total"] == len(load_judge_reliability_cases())
    assert summary["agree"] + len(summary["false_positives"]) + len(
        summary["false_negatives"]
    ) == summary["total"]
