"""Unit tests for the offline groundedness heuristic (llm/fake.py).

Not a test of RAG quality — a test that the offline stand-in behaves
sanely (obviously-supported claims pass, obviously-unrelated ones fail)
so `evals/rag_eval.py` has a working harness with no API key.
"""

from __future__ import annotations

from underwriting.domain.schemas import GroundednessVerdict
from underwriting.evals.groundedness import check_groundedness
from underwriting.llm.fake import FakeChatModel

CONTEXT = (
    "The minimum credit score for a conventional loan is 620. Applicants below 620 "
    "do not meet conventional loan requirements. A minimum of 2 months of PITI in "
    "post-closing liquid reserves is required for primary residences."
)


def test_claim_using_context_vocabulary_is_grounded():
    claim = "The applicant's credit score meets the conventional loan minimum requirement."
    verdict = check_groundedness(claim, CONTEXT, llm=FakeChatModel())
    assert isinstance(verdict, GroundednessVerdict)
    assert verdict.grounded is True
    assert verdict.unsupported_claims == []


def test_claim_unrelated_to_context_is_not_grounded():
    claim = "The property appraisal expired ninety days before the scheduled closing date."
    verdict = check_groundedness(claim, CONTEXT, llm=FakeChatModel())
    assert verdict.grounded is False
    assert verdict.unsupported_claims != []


def test_empty_claim_is_trivially_grounded():
    verdict = check_groundedness("", CONTEXT, llm=FakeChatModel())
    assert verdict.grounded is True
