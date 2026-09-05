"""Unit tests for the deterministic LTV/DTI citation accuracy checker.

This is the eval that would have (and does) score the ADR 0007 false
positive correctly: an LLM-as-judge groundedness check flagged "LTV of
86.08% requires mortgage insurance" as unsupported, even though 86.08% is
arithmetically inside the policy's 80-90% mortgage-insurance band.
"""

from __future__ import annotations

from underwriting.evals.citation_accuracy import check_citation_accuracy


def test_in_band_ltv_claim_is_consistent():
    checks = check_citation_accuracy("LTV of 86.08% requires mortgage insurance.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"
    assert checks[0].section == "4.1 Loan-to-Value (LTV) Ratio"


def test_ltv_claim_with_wrong_outcome_is_inconsistent():
    checks = check_citation_accuracy("LTV of 86.08% requires no mortgage insurance.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


def test_low_ltv_claim_needing_no_mortgage_insurance_is_consistent():
    checks = check_citation_accuracy("At 72% LTV, the loan qualifies for standard pricing.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_dti_within_standard_maximum_is_consistent():
    checks = check_citation_accuracy("A DTI of 38% is acceptable under the standard maximum.")
    assert len(checks) == 1
    assert checks[0].section == "2.2 Debt-to-Income (DTI) Ratio"
    assert checks[0].verdict == "consistent"


def test_dti_above_fifty_requiring_no_exception_is_inconsistent():
    checks = check_citation_accuracy("DTI of 55% is acceptable without any exception.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


def test_percentage_without_outcome_language_is_unrecognized():
    checks = check_citation_accuracy("The applicant's LTV is 86.08%.")
    assert len(checks) == 1
    assert checks[0].verdict == "unrecognized"


def test_sentence_without_ltv_or_dti_keyword_produces_no_check():
    assert check_citation_accuracy("The credit score is 740%.") == []


def test_claim_with_no_percentages_produces_no_checks():
    assert check_citation_accuracy("No adverse metrics found.") == []
