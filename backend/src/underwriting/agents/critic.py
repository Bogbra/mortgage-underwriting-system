"""Critic: cross-checks the four specialist analyses for contradictions and gaps.

This is the second, complementary bias-review layer referenced in
`domain/bias.py` — the deterministic scanner runs on every specialist output
unconditionally; the critic is asked, as one of its jobs, to reason about
subtler inconsistencies a regex cannot catch (e.g. one analyst being harsher
than the facts on this application warrant).
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.agents.common import NO_PROTECTED_CHARACTERISTICS_RULE
from underwriting.domain.schemas import CriticReview, UnderwritingState
from underwriting.llm.client import build_chat_model

SYSTEM_PROMPT = f"""You are a Quality Assurance Critic reviewing mortgage underwriting analyses.

Your job:
1. Verify all four specialist analyses are complete and internally consistent.
2. Identify contradictions (e.g. one analyst treats a fact as favorable that another
   treats as adverse).
3. Flag any gap that would block a defensible final decision.
4. Produce a short synthesis and a preliminary risk score (0-100) reflecting the
   combined severity of the four recommendations.

{NO_PROTECTED_CHARACTERISTICS_RULE}
Respond only with the structured fields you were asked for."""


def critic_node(state: UnderwritingState) -> dict:
    analyses = {
        "credit": state.credit_analysis,
        "income": state.income_analysis,
        "asset": state.asset_analysis,
        "collateral": state.collateral_analysis,
    }
    rendered = "\n\n".join(
        f"{name.upper()} ANALYSIS:\n{json.dumps(analysis.model_dump(), indent=2)}"
        for name, analysis in analyses.items()
        if analysis is not None
    )

    user_prompt = f"""Case: {state.case_id}

{rendered}

BIAS FLAGS RAISED SO FAR: {len(state.bias_flags)}
POLICY VIOLATIONS RAISED SO FAR: {len(state.policy_violations)}
"""

    llm = build_chat_model().with_structured_output(CriticReview)
    review: CriticReview = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )

    return {
        "critic_review": review,
        "reasoning_chain": [
            f"Critic: consistent={review.consistent}, "
            f"preliminary_risk_score={review.preliminary_risk_score}"
        ],
    }
