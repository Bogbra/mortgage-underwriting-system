"""RAG evaluation: retrieval quality, output groundedness, judge reliability,
and citation accuracy — four independent questions, each blind to the
others' failure modes:

  Phase 1 — Retrieval quality: for a query with known-correct policy
  section(s), how much of that expected set actually comes back in the
  top-k results? Reports both hit_rate@k (did at least one expected
  section come back — the metric this module used to call "recall@k") and
  true recall@k (`|expected ∩ retrieved| / |expected|`, averaged over
  queries) — see `run_recall_eval`'s docstring for why the distinction
  matters on this project's multi-section queries.

  Phase 2 — Generation faithfulness: for the four specialist agents' real
  outputs on the golden underwriting cases, is what they wrote actually
  supported by the policy text they were given? A perfect retriever doesn't
  guarantee a faithful write-up, and vice versa.

  Phase 3 — Judge reliability: Phase 2's verdict is only as trustworthy as
  the LLM-as-judge producing it. Runs the same judge against a small
  hand-labeled calibration set (`judge_reliability.py`) built from a known
  judge false positive documented in ADR 0007, to catch the judge being
  systematically too strict or too lenient rather than trusting a single
  pass silently.

  Phase 4 — Citation accuracy: a deterministic, non-LLM check
  (`citation_accuracy.py`) of the same Phase 2 claims — do the specific
  LTV/DTI percentages a specialist cites match the policy manual's own
  numeric bands? Catches the exact failure mode that fooled the judge in
  Phase 3's calibration case, without an LLM in the loop to fool.

Usage:
    uv run python -m underwriting.evals.rag_eval
    uv run python -m underwriting.evals.rag_eval --provider openai --embeddings openai

With the default fake embeddings, Phase 1's recall numbers are not
meaningful (see the warning it prints) — FakeEmbeddings is a hash, not a
semantic encoder (ADR 0003). The eval still runs end-to-end offline to
prove the harness works; --embeddings openai is what actually measures
retrieval quality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from underwriting.agents import asset, collateral, credit, income
from underwriting.config import settings
from underwriting.domain.schemas import ApplicantData
from underwriting.evals.citation_accuracy import check_citation_accuracy
from underwriting.evals.groundedness import check_groundedness
from underwriting.evals.judge_reliability import run_judge_reliability_eval
from underwriting.llm.client import build_chat_model
from underwriting.orchestrator import run_case
from underwriting.rag.policy_store import get_policy_store

BACKEND_ROOT = Path(__file__).resolve().parents[3]
RAG_QUERIES_PATH = BACKEND_ROOT / "data" / "evals" / "rag_golden_queries.json"
UNDERWRITING_CASES_PATH = BACKEND_ROOT / "data" / "test_cases" / "mortgage_test_cases.json"

AGENT_RETRIEVAL_QUERIES = {
    "credit": credit.RETRIEVAL_QUERY,
    "income": income.RETRIEVAL_QUERY,
    "asset": asset.RETRIEVAL_QUERY,
    "collateral": collateral.RETRIEVAL_QUERY,
}


def load_rag_queries() -> list[dict]:
    return json.loads(RAG_QUERIES_PATH.read_text())["queries"]


def run_recall_eval(k_values: tuple[int, ...] = (3, 6)) -> dict[int, float]:
    """Phase 1: two related-but-distinct retrieval metrics per k.

    **hit_rate@k** — the fraction of queries where *at least one* expected
    section appears in the top-k. This is what earlier versions of this
    module called "recall@k", which overstates quality on the four
    multi-section production queries: a query expecting 3 sections counts
    as a full success here even if only 1 of the 3 comes back.

    **recall@k** — the actual definition: mean over queries of
    `|expected ∩ retrieved| / |expected|`. For a single-expected-section
    query the two metrics agree; they diverge exactly on the multi-section
    queries, which is why both are reported rather than only the second —
    hit_rate@k still answers "did the query fail outright", which recall@k
    alone can obscure if partial credit hides a total miss on a different
    query.
    """

    queries = load_rag_queries()
    store = get_policy_store()

    print(f"Phase 1: retrieval hit_rate@k / recall@k  (embeddings={settings.embedding_provider})")
    if settings.embedding_provider == "fake":
        print(
            "  NOTE: FakeEmbeddings is a hash, not a semantic encoder — the numbers below\n"
            "  measure that the harness runs, not retrieval quality. Pass --embeddings openai\n"
            "  for a meaningful score.\n"
        )

    recall_at_k: dict[int, float] = {}
    for k in k_values:
        hits = 0
        recall_sum = 0.0
        for item in queries:
            retrieved = store.retrieve_sections(item["query"], k=k)
            expected = item["expected_sections"]
            found = [s for s in expected if s in retrieved]
            hit = bool(found)
            query_recall = len(found) / len(expected)
            hits += hit
            recall_sum += query_recall
            marker = "HIT " if hit else "MISS"
            print(f"  [{marker}] k={k} | recall={query_recall:.0%} | {item['query'][:60]!r}")
            if query_recall < 1.0:
                print(f"           expected: {expected}")
                print(f"           found:    {found}")
                print(f"           retrieved: {retrieved}")
        hit_rate = hits / len(queries)
        recall = recall_sum / len(queries)
        recall_at_k[k] = recall
        print(f"  hit_rate@{k}: {hits}/{len(queries)} = {hit_rate:.0%}")
        print(f"  recall@{k}:   {recall_sum:.2f}/{len(queries)} = {recall:.0%}\n")

    return recall_at_k


def run_groundedness_eval() -> list[dict]:
    print(f"Phase 2: output groundedness  (llm={settings.llm_provider})")
    if settings.llm_provider == "fake":
        print(
            "  NOTE: using the offline word-overlap heuristic, not a real LLM-as-judge —\n"
            "  see llm/fake.py:_build_groundedness. Pass --provider openai for a real check.\n"
        )

    llm = build_chat_model()
    cases = json.loads(UNDERWRITING_CASES_PATH.read_text())["test_cases"]

    results = []
    for fixture in cases:
        applicant = ApplicantData.model_validate(fixture)
        final_state = run_case(applicant)

        for agent_name, query in AGENT_RETRIEVAL_QUERIES.items():
            analysis = getattr(final_state, f"{agent_name}_analysis")
            if analysis is None:
                continue

            context = get_policy_store().retrieve(query)
            claim_text = f"{analysis.summary}\n" + "\n".join(analysis.key_factors)
            verdict = check_groundedness(claim_text, context, llm=llm)

            marker = "GROUNDED" if verdict.grounded else "UNSUPPORTED"
            print(f"  [{marker}] {fixture['case_id']} / {agent_name}")
            if not verdict.grounded:
                print(f"           unsupported: {verdict.unsupported_claims}")
                print(f"           notes: {verdict.notes}")

            results.append(
                {
                    "case_id": fixture["case_id"],
                    "agent": agent_name,
                    "grounded": verdict.grounded,
                    "unsupported_claims": verdict.unsupported_claims,
                    # Computed here (not in a separate workflow run) since it needs the
                    # same claim_text already in hand — see run_citation_accuracy_eval.
                    "citation_checks": check_citation_accuracy(claim_text),
                }
            )

    grounded_count = sum(r["grounded"] for r in results)
    print(f"\n  grounded: {grounded_count}/{len(results)} specialist analyses\n")
    return results


def run_citation_accuracy_eval(groundedness_results: list[dict]) -> dict:
    """Phase 4: deterministic LTV/DTI band check over the same claims Phase 2 judged.

    No LLM in the loop — see `citation_accuracy.py` for why that matters:
    it can confirm a claim like "LTV of 86.08% requires mortgage insurance"
    is consistent with policy even when an LLM-as-judge scores the identical
    claim unsupported (docs/adr/0007's headline finding).
    """

    print("Phase 4: citation accuracy (deterministic LTV/DTI band check)")

    consistent = inconsistent = unrecognized = 0
    inconsistent_examples: list[tuple[str, str, str, str]] = []
    for r in groundedness_results:
        for check in r["citation_checks"]:
            if check.verdict == "consistent":
                consistent += 1
            elif check.verdict == "inconsistent":
                inconsistent += 1
                inconsistent_examples.append(
                    (r["case_id"], r["agent"], check.sentence, check.detail)
                )
            else:
                unrecognized += 1

    total = consistent + inconsistent + unrecognized
    print(
        f"  consistent: {consistent} | inconsistent: {inconsistent} | "
        f"unrecognized: {unrecognized}  (of {total} LTV/DTI percentage citations found)"
    )
    for case_id, agent, sentence, detail in inconsistent_examples:
        print(f"  [INCONSISTENT] {case_id}/{agent}: {sentence!r}\n           {detail}")
    print()

    return {
        "total": total,
        "consistent": consistent,
        "inconsistent": inconsistent,
        "unrecognized": unrecognized,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openai", "anthropic", "fake"], default=None)
    parser.add_argument("--embeddings", choices=["openai", "fake"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--skip-groundedness",
        action="store_true",
        help=(
            "Run only Phase 1 (recall@k) — skips running the full agent workflow, "
            "and with it Phase 2 (groundedness), Phase 3 (judge reliability), and "
            "Phase 4 (citation accuracy)."
        ),
    )
    args = parser.parse_args()

    if args.provider:
        settings.llm_provider = args.provider  # type: ignore[assignment]
    if args.embeddings:
        settings.embedding_provider = args.embeddings  # type: ignore[assignment]
    if args.model:
        settings.llm_model = args.model

    recall = run_recall_eval()
    print("=" * 70)
    if not args.skip_groundedness:
        groundedness_results = run_groundedness_eval()
        print("=" * 70)
        run_judge_reliability_eval()
        print("=" * 70)
        run_citation_accuracy_eval(groundedness_results)

    # Only Phase 1 gates CI-style pass/fail, and only when embeddings are
    # actually semantic — see the NOTE printed above for why fake embeddings
    # are exempted.
    if settings.embedding_provider != "fake" and recall.get(6, 1.0) < 0.7:
        sys.exit(1)


if __name__ == "__main__":
    main()
