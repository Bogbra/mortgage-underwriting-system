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


# Boundary values (43/50 DTI, 80/90/97 LTV) must land in the same band
# domain/calculations.py's own `<=` chains put them in — an earlier version
# of _band_for used `value < high`, which silently bumped every exact
# threshold value into the wrong (higher) band.


def test_dti_exactly_43_is_still_the_standard_band():
    checks = check_citation_accuracy("DTI of 43% is acceptable under the standard maximum.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_dti_exactly_43_claiming_compensating_factors_is_inconsistent():
    checks = check_citation_accuracy("DTI of 43% requires compensating factors.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


def test_dti_exactly_50_is_still_the_compensating_factors_band():
    checks = check_citation_accuracy("DTI of 50% requires compensating factors.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_dti_exactly_50_claiming_not_eligible_is_inconsistent():
    checks = check_citation_accuracy("DTI of 50% is not eligible without an exception.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


def test_ltv_exactly_80_is_still_the_no_mi_band():
    checks = check_citation_accuracy(
        "LTV of 80% qualifies for standard pricing with no mortgage insurance."
    )
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_ltv_exactly_80_claiming_mortgage_insurance_is_inconsistent():
    checks = check_citation_accuracy("LTV of 80% requires mortgage insurance.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


def test_ltv_exactly_90_is_still_the_mortgage_insurance_band():
    checks = check_citation_accuracy("LTV of 90% requires mortgage insurance.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_ltv_exactly_97_is_still_the_compensating_factors_band():
    checks = check_citation_accuracy("LTV of 97% requires compensating factors.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_ltv_exactly_97_claiming_not_eligible_is_inconsistent():
    checks = check_citation_accuracy("LTV of 97% is not eligible.")
    assert len(checks) == 1
    assert checks[0].verdict == "inconsistent"


# "above X%" / "over X%" means value > X, which bands one level up from
# where the bare number X would land under the <= semantics above.


def test_ltv_above_80_lands_in_the_mortgage_insurance_band():
    checks = check_citation_accuracy(
        "LTV ratio requires mortgage insurance due to being above 80%."
    )
    assert len(checks) == 1
    assert checks[0].cited_value == 80.0
    assert checks[0].verdict == "consistent"


def test_dti_over_50_lands_in_the_not_eligible_band():
    checks = check_citation_accuracy("DTI over 50% is not eligible without an AUS exception.")
    assert len(checks) == 1
    assert checks[0].verdict == "consistent"


def test_ltv_of_exactly_80_is_unaffected_by_exclusive_phrasing_detection():
    checks = check_citation_accuracy("LTV of exactly 80% qualifies for standard pricing.")
    assert len(checks) == 1
    assert checks[0].cited_value == 80.0
    assert checks[0].verdict == "consistent"
