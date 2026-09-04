"""The underwriting workflow graph.

The four specialist agents (credit/income/asset/collateral) are independent
of each other's *output* — each reads only the sanitized applicant data — so
they fan out from `initialize` and run concurrently instead of being polled
one-by-one by a supervisor loop. `critic` has a structural dependency on all
four, so LangGraph only executes it once every incoming edge has completed
(a standard fan-in join). See docs/adr/0002-parallel-specialist-execution.md.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from underwriting.agents.asset import asset_analyst_node
from underwriting.agents.collateral import collateral_analyst_node
from underwriting.agents.credit import credit_analyst_node
from underwriting.agents.critic import critic_node
from underwriting.agents.decision import decision_node
from underwriting.agents.income import income_analyst_node
from underwriting.domain.pii import sanitize_applicant_data
from underwriting.domain.schemas import CaseStatus, UnderwritingState

SPECIALIST_NODES = ("credit", "income", "asset", "collateral")


def initialize_node(state: UnderwritingState) -> dict:
    sanitized = sanitize_applicant_data(state.applicant_data.model_dump(mode="json"))
    return {
        "sanitized_data": sanitized,
        "status": CaseStatus.RUNNING,
        "reasoning_chain": [f"Application {state.case_id} received and PII-sanitized"],
    }


def finalize_node(state: UnderwritingState) -> dict:
    status = (
        CaseStatus.AWAITING_HUMAN_REVIEW
        if state.human_review_required
        else CaseStatus.COMPLETED
    )
    return {"status": status}


def build_graph():
    graph = StateGraph(UnderwritingState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("credit", credit_analyst_node)
    graph.add_node("income", income_analyst_node)
    graph.add_node("asset", asset_analyst_node)
    graph.add_node("collateral", collateral_analyst_node)
    graph.add_node("critic", critic_node)
    graph.add_node("decision", decision_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "initialize")
    for node_name in SPECIALIST_NODES:
        graph.add_edge("initialize", node_name)
        graph.add_edge(node_name, "critic")
    graph.add_edge("critic", "decision")
    graph.add_edge("decision", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


@lru_cache
def get_compiled_graph():
    return build_graph()
