"""Persistence: case records and an append-only audit log.

SQLite by default (zero-setup local dev); point `DATABASE_URL` at Postgres
for anything shared. The audit table is insert-only by convention — no
router ever issues an UPDATE or DELETE against it — because a decision
record that can be silently edited after the fact is not an audit trail.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from underwriting.config import settings


class Base(DeclarativeBase):
    pass


class CaseRecord(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_decision: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    human_review_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    applicant_name_redacted: Mapped[str] = mapped_column(String, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def record_audit_event(
    db: Session, *, case_id: str, event_type: str, detail: str, actor: str
) -> None:
    db.add(AuditEventRecord(case_id=case_id, event_type=event_type, detail=detail, actor=actor))
    db.commit()
