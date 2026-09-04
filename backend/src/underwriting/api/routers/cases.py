"""Case submission, retrieval, and human-in-the-loop review."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from underwriting.api.auth import Principal, get_current_principal, require_reviewer
from underwriting.api.db import CaseRecord, get_db, record_audit_event
from underwriting.api.schemas_api import (
    CaseAcceptedResponse,
    CaseDetail,
    CaseSummary,
    ReviewDecisionRequest,
    SubmitCaseRequest,
)
from underwriting.domain.schemas import ApplicantData, CaseStatus
from underwriting.orchestrator import run_case

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["cases"])


def _execute_case(case_id: str, applicant: ApplicantData) -> None:
    """Runs in a worker thread via BackgroundTasks; owns its own DB session."""
    from underwriting.api.db import SessionLocal

    db = SessionLocal()
    try:
        final_state = run_case(applicant)
        record = db.get(CaseRecord, case_id)
        if record is None:
            return
        decision = final_state.decision
        record.status = final_state.status.value
        record.risk_score = decision.risk_score if decision else None
        record.final_decision = decision.decision.value if decision else None
        record.human_review_required = final_state.human_review_required
        record.state_json = final_state.model_dump(mode="json")
        db.add(record)
        db.commit()
        record_audit_event(
            db,
            case_id=case_id,
            event_type="workflow_completed",
            detail=(
                f"status={record.status} decision={record.final_decision} "
                f"risk_score={record.risk_score}"
            ),
            actor="system",
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the case record, not swallowed
        logger.exception("Workflow failed for case %s", case_id)
        record = db.get(CaseRecord, case_id)
        if record is not None:
            record.status = CaseStatus.FAILED.value
            record.error = str(exc)
            db.add(record)
            db.commit()
        record_audit_event(
            db, case_id=case_id, event_type="workflow_failed", detail=str(exc), actor="system"
        )
    finally:
        db.close()


@router.post("", response_model=CaseAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_case(
    payload: SubmitCaseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _principal: Principal = Depends(get_current_principal),
) -> CaseAcceptedResponse:
    if db.get(CaseRecord, payload.case_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Case {payload.case_id} already exists.")

    applicant = ApplicantData.model_validate(payload.model_dump())
    record = CaseRecord(
        case_id=applicant.case_id,
        status=CaseStatus.RECEIVED.value,
        applicant_name_redacted="[NAME_REDACTED]",
        state_json={},
    )
    db.add(record)
    db.commit()
    record_audit_event(
        db,
        case_id=applicant.case_id,
        event_type="case_submitted",
        detail="Case received.",
        actor="caller",
    )

    background_tasks.add_task(_execute_case, applicant.case_id, applicant)
    return CaseAcceptedResponse(case_id=applicant.case_id, status=CaseStatus.RECEIVED.value)


@router.get("", response_model=list[CaseSummary])
def list_cases(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _principal: Principal = Depends(get_current_principal),
) -> list[CaseSummary]:
    limit = max(1, min(limit, 200))
    records = db.execute(
        select(CaseRecord).order_by(CaseRecord.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [
        CaseSummary(
            case_id=r.case_id,
            status=r.status,
            applicant_name_redacted=r.applicant_name_redacted,
            risk_score=r.risk_score,
            final_decision=r.final_decision,
            human_review_required=r.human_review_required,
            human_review_completed=r.human_review_completed,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    _principal: Principal = Depends(get_current_principal),
) -> CaseDetail:
    record = db.get(CaseRecord, case_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found.")

    state = record.state_json or {}
    return CaseDetail(
        case_id=record.case_id,
        status=record.status,
        human_review_required=record.human_review_required,
        human_review_completed=record.human_review_completed,
        human_notes=state.get("human_notes"),
        human_reviewer=state.get("human_reviewer"),
        sanitized_data=state.get("sanitized_data", {}),
        credit_analysis=state.get("credit_analysis"),
        income_analysis=state.get("income_analysis"),
        asset_analysis=state.get("asset_analysis"),
        collateral_analysis=state.get("collateral_analysis"),
        critic_review=state.get("critic_review"),
        decision=state.get("decision"),
        bias_flags=state.get("bias_flags", []),
        policy_violations=state.get("policy_violations", []),
        reasoning_chain=state.get("reasoning_chain", []),
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/{case_id}/review", response_model=CaseDetail)
def review_case(
    case_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_reviewer),
) -> CaseDetail:
    record = db.get(CaseRecord, case_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found.")
    if record.status != CaseStatus.AWAITING_HUMAN_REVIEW.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Case {case_id} is not awaiting human review (status={record.status}).",
        )

    # Copy before mutating: `state_json` is a plain JSON column (not
    # MutableDict), so SQLAlchemy's change detection compares the flushed
    # value against the object it loaded by reference. Mutating that same
    # object in place and reassigning it back is a no-op as far as the ORM
    # is concerned — the UPDATE silently drops the column.
    state = dict(record.state_json or {})
    state["human_review_completed"] = True
    state["human_notes"] = payload.notes
    state["human_reviewer"] = "reviewer"
    record.state_json = state
    record.human_review_completed = True
    record.status = CaseStatus.COMPLETED.value
    db.add(record)
    db.commit()

    record_audit_event(
        db,
        case_id=case_id,
        event_type="human_review_completed",
        detail=f"approve={payload.approve} notes={payload.notes!r}",
        actor="reviewer",
    )

    return get_case(case_id, db=db, _principal=principal)
