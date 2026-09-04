# ADR 0007: RAG evaluation — retrieval recall@k and output groundedness

## Context

Every prior eval in this project (`evals/run.py`) checks the final
*decision* — does the workflow reach the right APPROVED/CONDITIONAL/DENIED
call. That says nothing about the RAG layer specifically: a specialist
agent could reach the right decision while citing policy text that isn't
actually in the retrieved context (a faithfulness failure), or the
retriever could be returning weakly relevant chunks that happen not to
change the outcome for the three golden cases (a recall failure masked by
a small eval set). Both are real, independent failure modes a
decision-level eval cannot see.

## Decision

`evals/rag_eval.py` runs two independent checks:

**Phase 1 — retrieval recall@k.** `data/evals/rag_golden_queries.json`
pairs 14 queries (the 4 real per-agent retrieval queries from
`agents/*.py:RETRIEVAL_QUERY`, plus 10 targeted single-topic queries
spanning every policy section including Fair Lending) with the policy
section(s) a correct retrieval should surface. `PolicyStore.retrieve_sections()`
(new, alongside the existing prompt-formatting `retrieve()`) returns the
ranked, deduplicated section labels for the top-k chunks, and recall@k is
the fraction of queries where at least one expected section appears.

**Phase 2 — output groundedness.** For each of the 3 golden underwriting
cases, after running the real workflow, every specialist's actual
`summary` + `key_factors` is checked against the policy text
*that agent was actually given* (re-retrieved via its
`RETRIEVAL_QUERY` constant — retrieval is deterministic for a fixed query
against a fixed corpus, so this reproduces the real context without
threading it through the workflow state). `GroundednessVerdict`
(`domain/schemas.py`) is produced by an LLM-as-judge prompt
(`evals/groundedness.py`) in live mode, or a word-overlap heuristic
(`llm/fake.py:_build_groundedness`) offline — the same fake/real split
every other eval in this project uses, for the same reason (ADR 0003).

## Consequences — and what the eval actually found

Run against real embeddings and `gpt-4o-mini` (`--provider openai
--embeddings openai`), on 2026-09-04:

- **recall@3 = recall@6 = 43% (6/14).** The 4 broad production queries
  all hit; several of the narrow single-topic queries (`"how many months
  of post-closing reserves are required"`, `"loan-to-value ratio above
  which mortgage insurance is required"`) miss, consistently retrieving
  `"2.4 Housing Expense Ratio"` and `"General"` instead. This points at
  the chunking, not the embedding model: `RecursiveCharacterTextSplitter`
  with `chunk_size=1000` does not reliably keep one `### X.Y` section per
  chunk in this policy document, so a chunk's `_section_label()` (matched
  from its first line) can end up representing content from an adjacent
  section. **Not fixed here** — this ADR's job is to make the gap
  measurable, not to close it blind. A likely fix is section-aware
  splitting (split on `### ` headers first, chunk within each section
  second) rather than pure character-count splitting.
- **7/12 (58%) specialist analyses fully grounded.** The 5 unsupported
  cases were real, specific over-claims an LLM-as-judge caught — e.g. an
  agent asserting "LTV of 86.08% requires mortgage insurance" when the
  retrieved policy text states the 80–90% band requires mortgage
  insurance but does not name 86.08% specifically, or attaching a
  severity claim ("indicates poor payment history") to a raw count the
  policy text never characterizes that way. These are plausible-sounding
  inferences beyond what the retrieved text actually says — exactly the
  failure mode a recall-only eval cannot see, and a "does the workflow
  run" eval has no reason to catch.
- Both numbers are **only meaningful with `--embeddings openai` /
  `--provider openai`.** The default (`fake`) run still executes both
  phases end to end — proving the harness works with no API key — but
  `FakeEmbeddings` is a content-blind hash (ADR 0003) and the fake
  groundedness heuristic scores the offline model's own template
  boilerplate, which by construction shares little vocabulary with real
  policy text. `rag_eval.py` prints an explicit warning rather than let
  those numbers be mistaken for retrieval or faithfulness quality.
