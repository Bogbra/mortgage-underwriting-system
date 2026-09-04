"""End-to-end workflow test against the deterministic FakeChatModel.

This is the regression harness referenced in the architecture proposal: it
runs the real LangGraph workflow — real parallel fan-out, real PII
sanitization, real deterministic calculators, real bias scanner — with only
the LLM call itself swapped for a offline stand-in. It requires no API key
and no network access, so it runs in CI on every commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from underwriting.domain.schemas import ApplicantData, CaseStatus, FinalDecision
from underwriting.orchestrator import run_case

FIXTURES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "test_cases" / "mortgage_test_cases.json"
)
FIXTURES = json.loads(FIXTURES_PATH.read_text())["test_cases"]


@pytest.fixture(autouse=True)
def _clear_caches():
    """Each case should hit a lru_cache-wrapped singleton fresh — nothing carries state."""
    from underwriting.llm.client import build_chat_model, build_embeddings

    build_chat_model.cache_clear()
    build_embeddings.cache_clear()
    yield


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["case_id"])
def test_full_workflow_runs_and_produces_all_analyses(fixture):
    applicant = ApplicantData.model_validate(fixture)

    final_state = run_case(applicant)

    assert final_state.status in (CaseStatus.COMPLETED, CaseStatus.AWAITING_HUMAN_REVIEW)
    assert final_state.credit_analysis is not None
    assert final_state.income_analysis is not None
    assert final_state.asset_analysis is not None
    assert final_state.collateral_analysis is not None
    assert final_state.critic_review is not None
    assert final_state.decision is not None
    assert final_state.decision.decision in list(FinalDecision)

    # PII must never leak into sanitized_data.
    assert final_state.sanitized_data["ssn"] != applicant.ssn
    assert final_state.sanitized_data["name"] == "[NAME_REDACTED]"

    # Every specialist step and the final decision must be in the audit trail.
    joined_chain = " | ".join(final_state.reasoning_chain)
    assert "Credit Analyst" in joined_chain
    assert "Income Analyst" in joined_chain
    assert "Asset Analyst" in joined_chain
    assert "Collateral Analyst" in joined_chain
    assert "Critic" in joined_chain
    assert "Decision Agent" in joined_chain


def test_denied_case_always_requires_human_review():
    fixture = next(f for f in FIXTURES if f["case_id"] == "CASE-2026-0003")
    applicant = ApplicantData.model_validate(fixture)

    final_state = run_case(applicant)

    if final_state.decision.decision == FinalDecision.DENIED:
        assert final_state.human_review_required is True
        assert final_state.status == CaseStatus.AWAITING_HUMAN_REVIEW


def test_bias_flags_are_aggregated_from_all_parallel_branches(monkeypatch):
    """Regression test for the parallel fan-out reducer.

    Forces every specialist analysis to mention a protected characteristic and
    asserts all four bias flags survive the concurrent merge into state —
    this is exactly the scenario a naive (overwrite-not-append) reducer would
    silently drop flags from.
    """
    from underwriting.domain import bias as bias_module

    original_scan = bias_module.scan_for_bias_signals

    def _always_flag(text: str, applicant_data: dict):
        flags = original_scan(text, applicant_data)
        flags.append(bias_module.BiasFlag(code="test_forced_flag", detail="forced for test"))
        return flags

    for module_name in ("credit", "income", "asset", "collateral"):
        monkeypatch.setattr(
            f"underwriting.agents.{module_name}.scan_for_bias_signals", _always_flag
        )

    applicant = ApplicantData.model_validate(FIXTURES[0])
    final_state = run_case(applicant)

    forced = [f for f in final_state.bias_flags if f.code == "test_forced_flag"]
    assert len(forced) == 4, "expected one forced bias flag per specialist agent"
