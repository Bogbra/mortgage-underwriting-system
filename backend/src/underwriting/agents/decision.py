"""Decision Agent: synthesizes every finding into the final, audit-ready outcome.

The final `human_review_required` flag is a deterministic business rule, not
something the LLM decides — a model that "forgets" to ask for review on a
DENIED case is a guardrail failure, not a rounding error. See
docs/adr/0001-structured-agent-outputs.md.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE
from underwriting.config import settings
from underwriting.domain.schemas import DecisionOutcome, FinalDecision, UnderwritingState
from underwriting.llm.client import build_chat_model

SYSTEM_PROMPT = f"""You are the Decision Agent — acting as a Senior Mortgage Underwriter —
in a multi-agent underwriting system.

You must:
1. Assign a risk_score from 0 (lowest risk) to 100 (highest risk), informed by — but not
   required to exactly match — the critic's preliminary estimate.
2. Choose a final decision using these bands: 0-30 APPROVED, 31-64 CONDITIONAL_APPROVAL,
   65-100 DENIED.
3. List approval conditions if CONDITIONAL_APPROVAL.
4. Write an audit-ready credit_memo referencing credit, income, assets, collateral, and
   compliance, that a regulator could read as the sole record of this decision.

{NO_PROTECTED_CHARACTERISTICS_RULE}
If bias flags or policy violations are present, the memo must state that senior
underwriter review is required.
Respond only with the structured fields you were asked for."""


def decision_node(state: UnderwritingState) -> dict:
    summaries = {
        "credit": state.credit_analysis,
        "income": state.income_analysis,
        "asset": state.asset_analysis,
        "collateral": state.collateral_analysis,
    }
    rendered = "\n\n".join(
        f"{name.upper()}: {json.dumps(analysis.model_dump())}"
        for name, analysis in summaries.items()
        if analysis is not None
    )
    critic = state.critic_review

    user_prompt = f"""Case: {state.case_id}

{rendered}

CRITIC SYNTHESIS: {critic.synthesis if critic else "N/A"}
CRITIC PRELIMINARY ASSESSMENT: {{"risk_score": {critic.preliminary_risk_score if critic else 50}}}

COMPLIANCE:
- Bias flags: {len(state.bias_flags)}
- Policy violations: {len(state.policy_violations)}
"""

    llm = build_chat_model().with_structured_output(DecisionOutcome)
    outcome: DecisionOutcome = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    human_review_required = (
        outcome.risk_score >= settings.human_review_risk_threshold
        or len(state.bias_flags) > 0
        or outcome.decision == FinalDecision.DENIED
    )

    return {
        "decision": outcome,
        "human_review_required": human_review_required,
        "reasoning_chain": [
            f"Decision Agent: {outcome.decision.value} at risk score {outcome.risk_score}/100 "
            f"(human review required: {human_review_required})"
        ],
    }
