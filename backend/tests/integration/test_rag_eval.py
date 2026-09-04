"""Integration tests for the RAG eval harness's building blocks.

Runs with the offline FakeEmbeddings (forced by conftest.py), so these
assert structural correctness — the retrieval and eval plumbing works end
to end — not retrieval *quality*, which needs real embeddings (see
evals/rag_eval.py's own warning about this).
"""

from __future__ import annotations

import json
from pathlib import Path

from underwriting.rag.policy_store import get_policy_store

RAG_QUERIES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "evals" / "rag_golden_queries.json"
)


def test_golden_query_dataset_is_well_formed():
    queries = json.loads(RAG_QUERIES_PATH.read_text())["queries"]
    assert len(queries) >= 10
    for item in queries:
        assert item["query"]
        assert item["expected_sections"]
        assert all(isinstance(s, str) for s in item["expected_sections"])


def test_retrieve_sections_returns_ranked_unique_labels():
    store = get_policy_store()
    sections = store.retrieve_sections("credit score bankruptcy", k=6)

    assert isinstance(sections, list)
    assert 1 <= len(sections) <= 6
    assert len(sections) == len(set(sections))  # de-duplicated
    assert all(isinstance(s, str) for s in sections)


def test_retrieve_sections_respects_k():
    store = get_policy_store()
    assert len(store.retrieve_sections("mortgage", k=1)) <= 1
    assert len(store.retrieve_sections("mortgage", k=3)) <= 3
