# ADR 0005: Persistence, audit trail, and auth posture

## Context

A case that only exists as in-memory Python state for the lifetime of a
single process, with "human review" as a console printout followed by
manual eyeballing, doesn't survive a process restart and doesn't produce
anything a compliance reviewer could later audit.

## Decision

**Persistence.** `api/db.py` defines two SQLAlchemy tables: `cases` (one row
per case, holding the full final `UnderwritingState` as a JSON blob plus
denormalized `status` / `risk_score` / `final_decision` columns for cheap
filtering) and `audit_events` (append-only: `case_submitted`,
`workflow_completed`, `workflow_failed`, `human_review_completed`). No
router issues an `UPDATE` or `DELETE` against `audit_events` — it is
insert-only by convention, because a decision record that can be silently
edited after the fact is not an audit trail. `DATABASE_URL` defaults to a
local SQLite file; pointing it at Postgres is a one-line env change with no
code change, since nothing above `db.py` knows which engine is in use.

**Execution model.** A submitted case runs via FastAPI `BackgroundTasks`
(`api/routers/cases.py:_execute_case`) in a worker thread, not blocking the
request — the client gets `202 Accepted` immediately and polls
`GET /cases/{id}`. This is intentionally the simplest thing that works for
a single-instance deployment; a queue (Celery, RQ, or a cloud task queue)
is the natural next step once cases need to survive an API process restart
mid-run or run across multiple instances.

**Auth.** `api/auth.py` implements two static, constant-time-compared
bearer tokens (`API_BEARER_TOKEN` for callers, `REVIEWER_BEARER_TOKEN` for
the human-in-the-loop endpoint), behind a `Principal` abstraction every
router depends on. This is a placeholder for a real identity provider
(OAuth2/OIDC), not a production auth design — but every router already
depends on `Principal`, not a raw token, so swapping the token check in
`get_current_principal` for a JWT/OIDC verification is the only change an
IdP migration requires.

## Consequences

- `PUT`/`PATCH` semantics were deliberately avoided on `state_json`: it is
  always read into a *copy*, mutated, and reassigned in whole
  (`api/routers/cases.py:review_case`) — SQLAlchemy's change detection on a
  plain (non-`MutableDict`) JSON column compares the flushed value against
  the object reference it loaded, so mutating that same object in place and
  reassigning it back is silently a no-op. This was caught by
  `tests/integration/test_api.py::test_human_review_requires_reviewer_role_and_completes_awaiting_case`
  failing on `human_notes` being `None` after a successful review call.
- The rate limiter (`api/rate_limit.py`) is in-process and per-instance —
  correct for one API replica, not for a horizontally scaled deployment,
  where it would need to move to a shared store (Redis) or an API gateway.
- No encryption-at-rest is configured for `state_json`, which contains the
  *sanitized* (not raw) applicant view plus every agent's narrative
  output — acceptable for a portfolio project, not acceptable for a real
  deployment without at minimum column- or disk-level encryption and a
  documented data-retention policy.
