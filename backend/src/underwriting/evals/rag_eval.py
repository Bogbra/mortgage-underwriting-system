"""RAG evaluation: retrieval recall@k, and whether agent output is grounded.

Two independent questions, both worth asking separately:

  Phase 1 — Retrieval quality: for a query with a known-correct policy
  section, does that section actually come back in the top-k results?
  (query -> expected sections -> retrieved sections -> recall@k)

  Phase 2 — Generation faithfulness: for the four specialist agents' real
  outputs on the golden underwriting cases, is what they wrote actually
  supported by the policy text they were given? A perfect retriever doesn't
  guarantee a faithful write-up, and vice versa.

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
from underwriting.evals.groundedness import check_groundedness
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
    queries = load_rag_queries()
    store = get_policy_store()

    print(f"Phase 1: retrieval recall@k  (embeddings={settings.embedding_provider})")
    if settings.embedding_provider == "fake":
        print(
            "  NOTE: FakeEmbeddings is a hash, not a semantic encoder — recall numbers below\n"
            "  measure that the harness runs, not retrieval quality. Pass --embeddings openai\n"
            "  for a meaningful score.\n"
        )

    recall_at_k: dict[int, float] = {}
    for k in k_values:
        hits = 0
        for item in queries:
            retrieved = store.retrieve_sections(item["query"], k=k)
            hit = any(expected in retrieved for expected in item["expected_sections"])
            hits += hit
            marker = "HIT " if hit else "MISS"
            print(f"  [{marker}] k={k} | {item['query'][:60]!r}")
            if not hit:
                print(f"           expected one of: {item['expected_sections']}")
                print(f"           retrieved:        {retrieved}")
        recall = hits / len(queries)
        recall_at_k[k] = recall
        print(f"  recall@{k}: {hits}/{len(queries)} = {recall:.0%}\n")

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
                }
            )

    grounded_count = sum(r["grounded"] for r in results)
    print(f"\n  grounded: {grounded_count}/{len(results)} specialist analyses\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openai", "anthropic", "fake"], default=None)
    parser.add_argument("--embeddings", choices=["openai", "fake"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--skip-groundedness",
        action="store_true",
        help="Run only Phase 1 (recall@k) — skips running the full agent workflow.",
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
        run_groundedness_eval()

    # Only Phase 1 gates CI-style pass/fail, and only when embeddings are
    # actually semantic — see the NOTE printed above for why fake embeddings
    # are exempted.
    if settings.embedding_provider != "fake" and recall.get(6, 1.0) < 0.7:
        sys.exit(1)


if __name__ == "__main__":
    main()
