"""Collateral Analyst: appraisal review, LTV, property condition."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE, render_metrics
from underwriting.domain.bias import scan_for_bias_signals
from underwriting.domain.calculations import calculate_ltv_ratio
from underwriting.domain.schemas import CollateralAnalysis, UnderwritingState
from underwriting.llm.client import build_chat_model
from underwriting.rag.policy_store import get_policy_store

SYSTEM_PROMPT = f"""You are a Senior Collateral Analyst with expertise in property valuation.

ANALYSIS FRAMEWORK:
1. Appraisal review — validate the property value against policy.
2. LTV ratio — use DETERMINISTIC_METRICS verbatim, do not recompute.
3. Property condition and habitability.
4. Marketability considerations.
5. Risk rating — LOW, MEDIUM, or HIGH.
6. Recommendation — PASS, CONDITIONAL, or FAIL, with conditions if CONDITIONAL.

{NO_PROTECTED_CHARACTERISTICS_RULE}
Respond only with the structured fields you were asked for."""


def collateral_analyst_node(state: UnderwritingState) -> dict:
    sanitized = state.sanitized_data
    property_data = sanitized.get("property", {})
    loan = sanitized.get("loan", {})

    ltv_result = calculate_ltv_ratio(
        loan_amount=loan.get("amount", 0),
        property_value=property_data.get("appraised_value", 0),
    )

    policies = get_policy_store().retrieve("appraisal property condition LTV collateral")

    user_prompt = f"""Case: {state.case_id}

RELEVANT POLICY EXCERPTS:
{policies}

PROPERTY:
- Type: {property_data.get("type")}
- Appraised value: {property_data.get("appraised_value")}
- Condition: {property_data.get("condition")}
- Use: {loan.get("use")}

DETERMINISTIC_METRICS:
{render_metrics(ltv=ltv_result)}
"""

    llm = build_chat_model().with_structured_output(CollateralAnalysis)
    analysis: CollateralAnalysis = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    bias_flags = scan_for_bias_signals(analysis.summary, sanitized)

    return {
        "collateral_analysis": analysis,
        "bias_flags": bias_flags,
        "reasoning_chain": [
            f"Collateral Analyst: {analysis.recommendation.value} "
            f"({analysis.risk_level.value} risk), LTV={ltv_result.ltv_ratio}%"
        ],
    }
