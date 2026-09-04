"""Asset Analyst: down-payment adequacy, reserve coverage, large-deposit sourcing."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE, render_metrics
from underwriting.domain.bias import scan_for_bias_signals
from underwriting.domain.calculations import (
    calculate_down_payment_adequacy,
    calculate_reserves,
    find_large_deposits,
)
from underwriting.domain.schemas import AssetAnalysis, UnderwritingState
from underwriting.llm.client import build_chat_model
from underwriting.rag.policy_store import get_policy_store

SYSTEM_PROMPT = f"""You are the Asset Analyst Agent in a mortgage underwriting multi-agent \
system.

ANALYSIS FRAMEWORK:
1. Down payment adequacy — use DETERMINISTIC_METRICS verbatim, do not recompute. A
   shortfall here is a serious concern even if reserves look adequate on paper.
2. Required reserves — computed on liquid assets *remaining after* the down payment,
   not gross liquid assets. Use DETERMINISTIC_METRICS verbatim, do not recompute.
3. Large deposits requiring sourcing documentation.
4. Asset documentation issues.
5. Risk rating — LOW, MEDIUM, or HIGH.
6. Recommendation — PASS, CONDITIONAL, or FAIL, with conditions if CONDITIONAL.

{NO_PROTECTED_CHARACTERISTICS_RULE}
Respond only with the structured fields you were asked for."""


def asset_analyst_node(state: UnderwritingState) -> dict:
    sanitized = state.sanitized_data
    assets = sanitized.get("assets", {})
    loan = sanitized.get("loan", {})
    monthly_income = sanitized.get("employment", {}).get("monthly_income", 0)

    liquid_assets = assets.get("checking", 0) + assets.get("savings", 0)
    monthly_payment = loan.get("estimated_payment", 0)
    down_payment_required = loan.get("down_payment", 0)

    down_payment_result = calculate_down_payment_adequacy(liquid_assets, down_payment_required)
    # Reserves are what's left *after* covering the down payment — not gross
    # liquid assets. A shortfall here still leaves 0 remaining, never negative.
    remaining_after_down_payment = max(0.0, liquid_assets - down_payment_required)
    reserves_result = calculate_reserves(
        remaining_after_down_payment, monthly_payment, required_months=2
    )
    deposits_result = find_large_deposits(assets.get("recent_deposits", []), monthly_income)

    policies = get_policy_store().retrieve(
        "down payment reserves assets large deposits gift funds"
    )

    user_prompt = f"""Case: {state.case_id}

RELEVANT POLICY EXCERPTS:
{policies}

TOTAL LIQUID ASSETS (before down payment): {liquid_assets}

DETERMINISTIC_METRICS:
{render_metrics(
    down_payment=down_payment_result,
    reserves_after_down_payment=reserves_result,
    large_deposits=deposits_result,
)}
"""

    llm = build_chat_model().with_structured_output(AssetAnalysis)
    analysis: AssetAnalysis = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    bias_flags = scan_for_bias_signals(analysis.summary, sanitized)

    return {
        "asset_analysis": analysis,
        "bias_flags": bias_flags,
        "reasoning_chain": [
            f"Asset Analyst: {analysis.recommendation.value} ({analysis.risk_level.value} risk)"
        ],
    }
