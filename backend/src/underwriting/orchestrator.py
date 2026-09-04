"""Single entry point for running a case through the full agent workflow."""

from __future__ import annotations

from underwriting.domain.schemas import ApplicantData, UnderwritingState
from underwriting.graph.build import get_compiled_graph
from underwriting.rag.policy_store import get_policy_store


def run_case(applicant_data: ApplicantData) -> UnderwritingState:
    get_policy_store()  # warm before the parallel fan-out to avoid a build race
    initial_state = UnderwritingState(case_id=applicant_data.case_id, applicant_data=applicant_data)
    graph = get_compiled_graph()
    result = graph.invoke(initial_state)
    return UnderwritingState.model_validate(result)
