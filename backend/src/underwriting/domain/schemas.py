"""Typed contracts for applicant data and every agent's output.

Agents never return prose that a downstream
`re.search(r"RISK_SCORE:\\s*(\\d+)")` has to hope matches. Every agent binds
its LLM call to one of these Pydantic models via structured output
(`llm.with_structured_output(...)`), so a malformed response is a validation
error the workflow can catch and retry — not a silent default. See
docs/adr/0001-structured-agent-outputs.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from underwriting.domain.bias import BiasFlag

# --------------------------------------------------------------------------
# Applicant data (input)
# --------------------------------------------------------------------------


class CreditHistory(BaseModel):
    bankruptcies: int = 0
    foreclosures: int = 0
    late_payments_12mo: int = 0
    collections: list[str] = Field(default_factory=list)


class Employment(BaseModel):
    type: str
    years: float
    monthly_income: float
    employer: str | None = None


class Deposit(BaseModel):
    amount: float
    date: str
    explanation: str | None = None


class Assets(BaseModel):
    checking: float = 0
    savings: float = 0
    recent_deposits: list[Deposit] = Field(default_factory=list)


class Loan(BaseModel):
    amount: float
    down_payment: float
    estimated_payment: float
    use: str = "primary_residence"


class Property(BaseModel):
    type: str
    appraised_value: float
    condition: str


class ApplicantData(BaseModel):
    """Raw application intake. Contains PII — never pass this to an LLM.

    Use `underwriting.domain.pii.sanitize_applicant_data` to derive the
    `sanitized_data` payload that agents actually see.
    """

    case_id: str
    name: str
    ssn: str
    phone: str
    email: str | None = None
    address: str
    credit_score: int
    credit_history: CreditHistory = Field(default_factory=CreditHistory)
    employment: Employment
    debts: dict[str, float] = Field(default_factory=dict)
    loan: Loan
    assets: Assets = Field(default_factory=Assets)
    property: Property

    # Present only in curated test/eval fixtures; never required in production.
    expected_decision: str | None = None


# --------------------------------------------------------------------------
# Specialist agent outputs
# --------------------------------------------------------------------------


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Recommendation(StrEnum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    FAIL = "FAIL"


class SpecialistAnalysis(BaseModel):
    """Common shape returned by every specialist agent (credit/income/asset/collateral)."""

    summary: str = Field(description="2-4 sentence underwriting assessment for this domain.")
    risk_level: RiskLevel
    recommendation: Recommendation
    key_factors: list[str] = Field(
        default_factory=list, description="Concrete facts that drove the assessment."
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions required before approval, if recommendation is CONDITIONAL.",
    )


class CreditAnalysis(SpecialistAnalysis):
    pass


class IncomeAnalysis(SpecialistAnalysis):
    pass


class AssetAnalysis(SpecialistAnalysis):
    pass


class CollateralAnalysis(SpecialistAnalysis):
    pass


class CriticReview(BaseModel):
    consistent: bool = Field(description="False if specialist analyses contradict each other.")
    issues: list[str] = Field(default_factory=list)
    synthesis: str = Field(description="Short synthesis of the four specialist findings.")
    preliminary_risk_score: int = Field(ge=0, le=100)


class FinalDecision(StrEnum):
    APPROVED = "APPROVED"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"
    DENIED = "DENIED"


class DecisionOutcome(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    decision: FinalDecision
    conditions: list[str] = Field(default_factory=list)
    credit_memo: str = Field(description="Audit-ready rationale referencing every domain.")


# --------------------------------------------------------------------------
# Workflow state
# --------------------------------------------------------------------------


def _append(existing: list, new: list) -> list:
    return [*existing, *new]


ReasoningChain = Annotated[list[str], _append]
BiasFlags = Annotated[list[BiasFlag], _append]


class CaseStatus(StrEnum):
    RECEIVED = "received"
    RUNNING = "running"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    COMPLETED = "completed"
    FAILED = "failed"


class UnderwritingState(BaseModel):
    """Full state threaded through the LangGraph workflow for one case."""

    model_config = {"arbitrary_types_allowed": True}

    case_id: str
    applicant_data: ApplicantData
    sanitized_data: dict = Field(default_factory=dict)

    credit_analysis: CreditAnalysis | None = None
    income_analysis: IncomeAnalysis | None = None
    asset_analysis: AssetAnalysis | None = None
    collateral_analysis: CollateralAnalysis | None = None
    critic_review: CriticReview | None = None
    decision: DecisionOutcome | None = None

    status: CaseStatus = CaseStatus.RECEIVED
    human_review_required: bool = False
    human_review_completed: bool = False
    human_notes: str | None = None
    human_reviewer: str | None = None

    bias_flags: BiasFlags = Field(default_factory=list)
    policy_violations: list[str] = Field(default_factory=list)
    reasoning_chain: ReasoningChain = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
