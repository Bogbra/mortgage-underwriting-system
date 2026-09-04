"""Credit Analyst: credit score tier, payment history, derogatory items."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE, render_metrics
from underwriting.domain.bias import scan_for_bias_signals
from underwriting.domain.calculations import check_credit_score_policy
from underwriting.domain.schemas import CreditAnalysis, UnderwritingState
from underwriting.llm.client import build_chat_model
from underwriting.rag.policy_store import get_policy_store

SYSTEM_PROMPT = f"""You are a Senior Credit Analyst with 15+ years of experience in mortgage \
underwriting.

ANALYSIS FRAMEWORK:
1. Credit score tier — use the DETERMINISTIC_METRICS below verbatim, do not recompute.
2. Payment history — review late payments and patterns.
3. Derogatory items — evaluate bankruptcies, foreclosures, collections.
4. Policy compliance — check against the retrieved policy excerpts.
5. Risk rating — LOW, MEDIUM, or HIGH.
6. Recommendation — PASS, CONDITIONAL, or FAIL, with conditions if CONDITIONAL.

{NO_PROTECTED_CHARACTERISTICS_RULE}
Respond only with the structured fields you were asked for."""


def credit_analyst_node(state: UnderwritingState) -> dict:
    sanitized = state.sanitized_data
    credit_history = sanitized.get("credit_history", {})
    credit_score = sanitized.get("credit_score", 0)

    score_result = check_credit_score_policy(credit_score)
    policies = get_policy_store().retrieve(
        "credit score requirements bankruptcies foreclosures late payments"
    )

    user_prompt = f"""Case: {state.case_id}

RELEVANT POLICY EXCERPTS:
{policies}

CREDIT HISTORY:
- Bankruptcies: {credit_history.get("bankruptcies", 0)}
- Foreclosures: {credit_history.get("foreclosures", 0)}
- Late payments (12mo): {credit_history.get("late_payments_12mo", 0)}
- Collections: {credit_history.get("collections", [])}

DETERMINISTIC_METRICS:
{render_metrics(credit_score=score_result)}
"""

    llm = build_chat_model().with_structured_output(CreditAnalysis)
    analysis: CreditAnalysis = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    bias_flags = scan_for_bias_signals(analysis.summary, sanitized)

    return {
        "credit_analysis": analysis,
        "bias_flags": bias_flags,
        "reasoning_chain": [
            f"Credit Analyst: {analysis.recommendation.value} ({analysis.risk_level.value} risk)"
        ],
    }
