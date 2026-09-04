import pytest
from pydantic import ValidationError

from underwriting.domain.schemas import (
    ApplicantData,
    CaseStatus,
    CreditAnalysis,
    Recommendation,
    RiskLevel,
    UnderwritingState,
)

MINIMAL_APPLICANT = {
    "case_id": "CASE-TEST-001",
    "name": "Jordan Rivera",
    "ssn": "123-45-6789",
    "phone": "555-000-1111",
    "address": "1 Test Way",
    "credit_score": 720,
    "employment": {"type": "W2", "years": 5, "monthly_income": 8000},
    "loan": {"amount": 300_000, "down_payment": 60_000, "estimated_payment": 1900},
    "property": {"type": "single_family", "appraised_value": 400_000, "condition": "good"},
}


def test_applicant_data_parses_minimal_payload():
    applicant = ApplicantData.model_validate(MINIMAL_APPLICANT)
    assert applicant.credit_history.bankruptcies == 0
    assert applicant.assets.checking == 0
    assert applicant.debts == {}


def test_applicant_data_rejects_missing_required_field():
    payload = {k: v for k, v in MINIMAL_APPLICANT.items() if k != "loan"}
    with pytest.raises(ValidationError):
        ApplicantData.model_validate(payload)


def test_specialist_analysis_recommendation_is_constrained_enum():
    analysis = CreditAnalysis(
        summary="Strong profile.",
        risk_level=RiskLevel.LOW,
        recommendation=Recommendation.PASS,
        key_factors=["credit_score=760"],
    )
    assert analysis.recommendation == "PASS"
    with pytest.raises(ValidationError):
        CreditAnalysis(
            summary="x",
            risk_level="not-a-level",
            recommendation=Recommendation.PASS,
        )


def test_underwriting_state_defaults_and_status():
    applicant = ApplicantData.model_validate(MINIMAL_APPLICANT)
    state = UnderwritingState(case_id=applicant.case_id, applicant_data=applicant)
    assert state.status == CaseStatus.RECEIVED
    assert state.bias_flags == []
    assert state.reasoning_chain == []
    assert state.decision is None
