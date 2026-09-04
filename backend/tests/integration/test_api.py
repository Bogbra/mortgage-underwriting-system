from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from underwriting.api.main import app
from underwriting.config import settings

FIXTURES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "test_cases" / "mortgage_test_cases.json"
)
FIXTURES = json.loads(FIXTURES_PATH.read_text())["test_cases"]

AUTH = {"Authorization": f"Bearer {settings.api_bearer_token}"}
REVIEWER_AUTH = {"Authorization": f"Bearer {settings.reviewer_bearer_token}"}


def test_health_endpoint_requires_no_auth():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cases_endpoints_reject_missing_or_bad_auth():
    with TestClient(app) as client:
        assert client.get("/cases").status_code == 401
        assert client.get("/cases", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_submit_get_and_list_case_flow():
    strong_applicant = FIXTURES[0]  # expected APPROVED

    with TestClient(app) as client:
        submit_response = client.post("/cases", json=strong_applicant, headers=AUTH)
        assert submit_response.status_code == 202
        body = submit_response.json()
        assert body["case_id"] == strong_applicant["case_id"]
        assert body["status"] == "received"

        # BackgroundTasks complete before TestClient returns control here.
        detail_response = client.get(f"/cases/{strong_applicant['case_id']}", headers=AUTH)
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["status"] in ("completed", "awaiting_human_review")
        assert detail["decision"] is not None
        assert detail["sanitized_data"]["name"] == "[NAME_REDACTED]"

        list_response = client.get("/cases", headers=AUTH)
        assert list_response.status_code == 200
        case_ids = [c["case_id"] for c in list_response.json()]
        assert strong_applicant["case_id"] in case_ids


def test_duplicate_case_id_is_rejected():
    applicant = FIXTURES[1]
    with TestClient(app) as client:
        first = client.post("/cases", json=applicant, headers=AUTH)
        assert first.status_code == 202
        second = client.post("/cases", json=applicant, headers=AUTH)
        assert second.status_code == 409


def test_same_ssn_under_a_new_case_id_is_flagged_not_rejected():
    # Distinct case_id *and* a synthetic SSN, not reused from any fixture —
    # the DB is shared across the whole test session (see conftest.py), and
    # every fixture's own SSN has likely already been submitted by another
    # test by the time this one runs.
    original = {**FIXTURES[0], "case_id": "CASE-2026-DUPTEST-A", "ssn": "000-11-2222"}
    reapplication = {**FIXTURES[0], "case_id": "CASE-2026-DUPTEST-B", "ssn": "000-11-2222"}

    with TestClient(app) as client:
        first = client.post("/cases", json=original, headers=AUTH)
        assert first.status_code == 202
        assert first.json()["possible_duplicate_of"] is None

        second = client.post("/cases", json=reapplication, headers=AUTH)
        assert second.status_code == 202  # not rejected — same person, new case
        assert second.json()["possible_duplicate_of"] == original["case_id"]

        detail = client.get(f"/cases/{reapplication['case_id']}", headers=AUTH).json()
        assert detail["possible_duplicate_of"] == original["case_id"]

        summaries = {c["case_id"]: c for c in client.get("/cases", headers=AUTH).json()}
        assert summaries[original["case_id"]]["possible_duplicate_of"] is None
        assert summaries[reapplication["case_id"]]["possible_duplicate_of"] == original["case_id"]


def test_human_review_requires_reviewer_role_and_completes_awaiting_case():
    denial_applicant = FIXTURES[2]  # expected DENIED -> forces human_review_required

    with TestClient(app) as client:
        client.post("/cases", json=denial_applicant, headers=AUTH)
        detail = client.get(f"/cases/{denial_applicant['case_id']}", headers=AUTH).json()

        # Every calculated ratio for this fixture lands in the worst band, so the
        # deterministic fake model always recommends FAIL / DENIED here.
        assert detail["human_review_required"] is True

        forbidden = client.post(
            f"/cases/{denial_applicant['case_id']}/review",
            json={"approve": False, "notes": "Confirmed denial after manual review."},
            headers=AUTH,  # caller role, not reviewer
        )
        assert forbidden.status_code == 403

        reviewed = client.post(
            f"/cases/{denial_applicant['case_id']}/review",
            json={"approve": False, "notes": "Confirmed denial after manual review."},
            headers=REVIEWER_AUTH,
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "completed"
        assert reviewed.json()["human_notes"] == "Confirmed denial after manual review."


def test_review_rejects_case_not_awaiting_review():
    # The strong-applicant fixture is clean (no adverse ratio statuses, no bias
    # flags), so the deterministic fake model always lands below the human
    # review risk threshold — this case never reaches AWAITING_HUMAN_REVIEW.
    applicant = {**FIXTURES[0], "case_id": "CASE-2026-9999"}
    with TestClient(app) as client:
        client.post("/cases", json=applicant, headers=AUTH)
        detail = client.get(f"/cases/{applicant['case_id']}", headers=AUTH).json()
        assert detail["human_review_required"] is False

        response = client.post(
            f"/cases/{applicant['case_id']}/review",
            json={"approve": True, "notes": "n/a"},
            headers=REVIEWER_AUTH,
        )
        assert response.status_code == 409
