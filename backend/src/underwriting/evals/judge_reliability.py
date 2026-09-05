"""Judge reliability: is the groundedness LLM-as-judge itself trustworthy?

`groundedness.py`'s LLM-as-judge is the thing `rag_eval.py` Phase 2 uses to
decide whether a specialist's analysis is faithful to retrieved policy
text. Nothing checked, until now, whether *the judge* is calibrated — and
`docs/adr/0007-rag-evaluation.md` documents a case where it wasn't: it
scored "LTV of 86.08% requires mortgage insurance" as an unsupported claim,
even though the retrieved text states the 80-90% band requires mortgage
insurance and 86.08% is arithmetically inside that band. A recall or
groundedness number is only as trustworthy as the judge producing it, so
this measures the judge against a small hand-labeled calibration set
(`data/evals/judge_reliability_cases.json`) — including that exact case —
the same way a hiring pipeline would spot-check an interviewer's ratings
against a known-answer rubric.

This is deliberately a fixed, hand-labeled set rather than a
statistically-representative sample: its job is to catch known judge
failure patterns (in-band numeric claims, cross-section contamination,
boundary values, dropped conditions), not to estimate a population-level
accuracy rate.
"""

from __future__ import annotations

import json
from pathlib import Path

from underwriting.evals.groundedness import check_groundedness
from underwriting.llm.client import build_chat_model

BACKEND_ROOT = Path(__file__).resolve().parents[3]
JUDGE_CASES_PATH = BACKEND_ROOT / "data" / "evals" / "judge_reliability_cases.json"


def load_judge_reliability_cases() -> list[dict]:
    return json.loads(JUDGE_CASES_PATH.read_text())["cases"]


def run_judge_reliability_eval(llm=None) -> dict:
    """Run every calibration case through the real judge and score agreement.

    Returns a summary dict with counts of false positives (judge said
    unsupported, human label says grounded — the failure mode this eval
    exists to catch) and false negatives (judge said grounded, human label
    says unsupported — a judge that's too lenient to be a useful eval gate).
    """

    print("Phase 3: judge reliability (groundedness judge vs. hand-labeled cases)")

    llm = llm or build_chat_model()
    cases = load_judge_reliability_cases()

    agree = 0
    false_positives: list[str] = []  # judge: unsupported, label: grounded
    false_negatives: list[str] = []  # judge: grounded, label: unsupported

    for case in cases:
        verdict = check_groundedness(case["claim"], case["context"], llm=llm)
        expected = case["expected_grounded"]
        actual = verdict.grounded

        if actual == expected:
            agree += 1
            marker = "AGREE"
        elif expected and not actual:
            false_positives.append(case["id"])
            marker = "JUDGE FALSE POSITIVE"
        else:
            false_negatives.append(case["id"])
            marker = "JUDGE FALSE NEGATIVE"

        print(f"  [{marker}] {case['id']} (expected_grounded={expected}, judge said {actual})")
        if actual != expected:
            print(f"           note: {case['note']}")
            if verdict.unsupported_claims:
                print(f"           judge unsupported_claims: {verdict.unsupported_claims}")

    total = len(cases)
    agreement_rate = agree / total if total else 1.0
    print(f"\n  judge agreement: {agree}/{total} = {agreement_rate:.0%}")
    print(f"  false positives (judge too strict): {len(false_positives)} {false_positives}")
    print(f"  false negatives (judge too lenient): {len(false_negatives)} {false_negatives}\n")

    return {
        "total": total,
        "agree": agree,
        "agreement_rate": agreement_rate,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
