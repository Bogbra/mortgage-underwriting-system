"""Income Analyst: employment stability, DTI, housing ratio, capacity to repay."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE, render_metrics
from underwriting.domain.bias import scan_for_bias_signals
from underwriting.domain.calculations import (
    calculate_dti_ratio,
    calculate_housing_expense_ratio,
    calculate_total_debt_obligations,
)
from underwriting.domain.schemas import IncomeAnalysis, UnderwritingState
from underwriting.llm.client import build_chat_model
from underwriting.rag.policy_store import get_policy_store

SYSTEM_PROMPT = f"""You are the Income Analyst Agent in a mortgage underwriting multi-agent \
system.

ANALYSIS FRAMEWORK:
1. Employment stability — job history and tenure.
2. Income verification — validate income sources.
3. DTI ratio — use DETERMINISTIC_METRICS verbatim, do not recompute.
4. Housing expense ratio and payment capacity.
5. Risk rating — LOW, MEDIUM, or HIGH.
6. Recommendation — PASS, CONDITIONAL, or FAIL, with conditions if CONDITIONAL.

{NO_PROTECTED_CHARACTERISTICS_RULE}
Respond only with the structured fields you were asked for."""


def income_analyst_node(state: UnderwritingState) -> dict:
    sanitized = state.sanitized_data
    employment = sanitized.get("employment", {})
    debts = sanitized.get("debts", {})
    proposed_payment = sanitized.get("loan", {}).get("estimated_payment", 0)
    monthly_income = employment.get("monthly_income", 0)

    total_debt = sum(debts.values())
    dti_result = calculate_dti_ratio(total_debt + proposed_payment, monthly_income)
    housing_result = calculate_housing_expense_ratio(proposed_payment, monthly_income)
    debt_breakdown = calculate_total_debt_obligations(debts, proposed_payment)

    policies = get_policy_store().retrieve(
        "employment income verification DTI ratio self-employed"
    )

    user_prompt = f"""Case: {state.case_id}

RELEVANT POLICY EXCERPTS:
{policies}

EMPLOYMENT:
- Type: {employment.get("type")}
- Years: {employment.get("years")}
- Monthly income: {monthly_income}

DETERMINISTIC_METRICS:
{render_metrics(dti=dti_result, housing_ratio=housing_result, debt_obligations=debt_breakdown)}
"""

    llm = build_chat_model().with_structured_output(IncomeAnalysis)
    analysis: IncomeAnalysis = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    bias_flags = scan_for_bias_signals(analysis.summary, sanitized)

    return {
        "income_analysis": analysis,
        "bias_flags": bias_flags,
        "reasoning_chain": [
            f"Income Analyst: {analysis.recommendation.value} ({analysis.risk_level.value} risk), "
            f"DTI={dti_result.dti_ratio}%"
        ],
    }
