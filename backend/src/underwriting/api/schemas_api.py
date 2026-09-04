"""API request/response contracts — kept separate from the internal domain
schemas so the workflow's internal state shape can change without breaking
API consumers (the Next.js dashboard, or anyone else)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from underwriting.domain.schemas import ApplicantData


class SubmitCaseRequest(ApplicantData):
    """Identical to ApplicantData today; kept as a distinct type so the API
    contract can diverge from the internal model deliberately, not by accident."""


class CaseAcceptedResponse(BaseModel):
    case_id: str
    status: str
    possible_duplicate_of: str | None = None


class CaseSummary(BaseModel):
    case_id: str
    status: str
    applicant_name: str
    risk_score: int | None
    final_decision: str | None
    human_review_required: bool
    human_review_completed: bool
    possible_duplicate_of: str | None
    created_at: datetime
    updated_at: datetime


class CaseDetail(BaseModel):
    case_id: str
    status: str
    applicant_name: str
    possible_duplicate_of: str | None
    human_review_required: bool
    human_review_completed: bool
    human_notes: str | None
    human_reviewer: str | None
    sanitized_data: dict[str, Any]
    credit_analysis: dict[str, Any] | None
    income_analysis: dict[str, Any] | None
    asset_analysis: dict[str, Any] | None
    collateral_analysis: dict[str, Any] | None
    critic_review: dict[str, Any] | None
    decision: dict[str, Any] | None
    bias_flags: list[dict[str, Any]]
    policy_violations: list[str]
    reasoning_chain: list[str]
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewDecisionRequest(BaseModel):
    approve: bool
    notes: str


class AuditEvent(BaseModel):
    event_type: str
    detail: str
    actor: str
    created_at: datetime
