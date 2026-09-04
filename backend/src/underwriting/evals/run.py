"""Golden-case regression eval.

Distinct from `tests/integration/test_graph_fake_llm.py`: that suite asserts
the workflow *runs* correctly (every node fires, PII is redacted, flags
merge). This script asserts the workflow's *output quality* — does the
final decision match what a senior underwriter would expect for each golden
case — and is meant to be run against a real provider before every prompt
change ships, not just in CI against the fake model.

Usage:
    uv run python -m underwriting.evals.run
    uv run python -m underwriting.evals.run --provider openai --model gpt-4o-mini

Exits non-zero if any golden case's decision doesn't match its expected
band, so it can gate a CI job or a pre-deploy check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from underwriting.config import settings
from underwriting.domain.schemas import ApplicantData
from underwriting.orchestrator import run_case

FIXTURES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "test_cases" / "mortgage_test_cases.json"
)


def load_golden_cases() -> list[dict]:
    return json.loads(FIXTURES_PATH.read_text())["test_cases"]


def run_evals(provider: str | None, model: str | None) -> int:
    if provider:
        settings.llm_provider = provider  # type: ignore[assignment]
    if model:
        settings.llm_model = model

    cases = load_golden_cases()
    failures = 0

    print(f"Running {len(cases)} golden case(s) against LLM_PROVIDER={settings.llm_provider}\n")

    for fixture in cases:
        applicant = ApplicantData.model_validate(fixture)
        expected = fixture.get("expected_decision")

        final_state = run_case(applicant)
        actual = final_state.decision.decision.value if final_state.decision else None
        risk_score = final_state.decision.risk_score if final_state.decision else None

        ok = actual == expected
        failures += 0 if ok else 1
        marker = "PASS" if ok else "FAIL"

        print(
            f"[{marker}] {fixture['case_id']} ({fixture['name']}): "
            f"expected={expected} actual={actual} risk_score={risk_score} "
            f"human_review_required={final_state.human_review_required} "
            f"bias_flags={len(final_state.bias_flags)}"
        )

    print(f"\n{len(cases) - failures}/{len(cases)} golden cases passed.")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openai", "anthropic", "fake"], default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    sys.exit(run_evals(args.provider, args.model))


if __name__ == "__main__":
    main()
