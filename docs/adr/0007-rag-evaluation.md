# ADR 0007: RAG evaluation — retrieval, groundedness, judge reliability, and citation accuracy

## Context

Every prior eval in this project (`evals/run.py`) checks the final
*decision* — does the workflow reach the right APPROVED/CONDITIONAL/DENIED
call. That says nothing about the RAG layer specifically: a specialist
agent could reach the right decision while citing policy text that isn't
actually in the retrieved context (a faithfulness failure), or the
retriever could be returning weakly relevant chunks that happen not to
change the outcome for the three golden cases (a recall failure masked by
a small eval set). Both are real, independent failure modes a
decision-level eval cannot see. Two more failure modes surfaced once the
first two were being measured: the LLM-as-judge grading groundedness can
itself be miscalibrated (a judge false positive or false negative is
indistinguishable from a real finding unless something checks the judge),
and a claim can cite a real, in-context number while still attaching the
wrong section's rule to it.

## Decision

`evals/rag_eval.py` runs four independent checks.

**Phase 1 — retrieval quality.** `data/evals/rag_golden_queries.json`
pairs 14 queries (the 4 real per-agent retrieval queries from
`agents/*.py:RETRIEVAL_QUERY`, plus 10 targeted single-topic queries
spanning every policy section including Fair Lending) with the policy
section(s) a correct retrieval should surface. `PolicyStore.retrieve_sections()`
(alongside the existing prompt-formatting `retrieve()`) returns the ranked,
deduplicated section labels for the top-k chunks. Two metrics are reported,
not one:

- **hit_rate@k** — the fraction of queries where *at least one* expected
  section appears in the top-k. This is what this ADR originally called
  "recall@k" — a naming bug caught in review. It overstates quality on the
  four multi-section production queries: a query expecting 3 sections
  counts as a full success here even if only 1 of the 3 comes back.
- **recall@k** — the actual definition: mean over queries of
  `|expected ∩ retrieved| / |expected|`. Single-expected-section queries
  score the same under both metrics; they diverge exactly on the
  multi-section queries, which is why both are still reported —
  hit_rate@k answers "did the query fail outright," which recall@k alone
  can obscure by handing out partial credit.

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

**Phase 3 — judge reliability.** Phase 2's verdict is only as trustworthy
as the judge producing it, and Phase 2 found a case where it wasn't (see
Consequences). `evals/judge_reliability.py` runs the same
`check_groundedness` judge against a small hand-labeled calibration set
(`data/evals/judge_reliability_cases.json`) — six `(context, claim,
expected_grounded)` triples built specifically to probe known failure
patterns: an in-band numeric claim, a case-specific-number carve-out, a
genuinely wrong threshold, cross-section contamination, a boundary value,
and a dropped condition. It reports agreement, and separately, false
positives (judge too strict) vs. false negatives (judge too lenient) —
collapsing both into one "accuracy" number would hide which failure mode
is actually occurring.

**Phase 4 — citation accuracy.** A deterministic, non-LLM check
(`evals/citation_accuracy.py`) of the same Phase 2 claims: for every
LTV or DTI percentage a specialist cites, does the claim's stated outcome
(mortgage insurance required or not, compensating factors required or
not, eligible or not) match the band that percentage actually falls in
per the policy manual's own numeric bands (section 4.1 and 2.2)? A
regex/keyword check can't be talked into a false positive or false
negative the way an LLM judge can — it either matches the fixed band
table or it doesn't. Deliberately scoped to the two sections that define
numeric bands (rather than a single threshold), because those are exactly
where "is 86.08% inside 80-90%?" arithmetic trips up a judge reading prose.

## Consequences — and what the eval actually found

Run against real embeddings and `gpt-4o-mini` (`--provider openai
--embeddings openai`), on 2026-09-05:

### Phase 1: a chunking bug, found and fixed

The first real run found **hit_rate@3 = hit_rate@6 = 43% (6/14)** — at the
time, this project called that number "recall@6" (see Phase 1's
correction above). The 4 broad production queries all hit; several of the
narrow single-topic queries (`"how many months of post-closing reserves
are required"`, `"loan-to-value ratio above which mortgage insurance is
required"`) missed, consistently retrieving `"2.4 Housing Expense Ratio"`
and `"General"` instead.

Root cause: `PolicyStore` ran `RecursiveCharacterTextSplitter` over the
*whole* policy document and identified each chunk's section by
regex-matching the chunk's own first line. A character-count split has no
idea where a `### X.Y` heading is, so a chunk that started mid-section
silently mislabeled as "General" or the *previous* section — the chunk's
embedding was correct, its section label was not.

**Fix:** `policy_store._split_into_sections()` now splits the raw document
on `### X.Y` heading boundaries *first*, then runs the character splitter
within each section, and stamps `section` in chunk metadata at indexing
time instead of inferring it later from a regex match against arbitrary
chunk text. Every chunk is now drawn from exactly one section by
construction.

**Result, same queries, same embeddings, clean rebuild:**

| metric | before | after |
|---|---|---|
| hit_rate@3 | 43% (6/14) | 100% (14/14) |
| recall@3 | *(not computed — metric didn't exist)* | 98% (13.67/14) |
| hit_rate@6 | 43% (6/14) | 100% (14/14) |
| recall@6 | *(not computed)* | 100% (14/14) |

The one query that doesn't hit 100% recall@3 — `"employment income
verification DTI ratio self-employed"` (the real `income` agent query,
expecting all of 2.1/2.2/2.3) — finds only 2 of 3 sections at k=3 and all
3 at k=6, a real (and much smaller) precision/recall tradeoff rather than
a labeling bug.

### Phase 2: groundedness did not improve when retrieval did

**3/12 (25%) specialist analyses fully grounded** on this run — lower
than an earlier draft of this ADR reported (7/12, before the chunking
fix), which is itself informative: fixing retrieval didn't fix
generation faithfulness, confirming this ADR's original premise that the
two are independent failure modes rather than one causing the other.

Two representative "unsupported" verdicts from this run:

- `CASE-2026-0002 / collateral`: flagged **"LTV ratio requires mortgage
  insurance, indicating elevated risk"** unsupported. The judge's own
  notes concede *"the LTV ratio of 86.08% does require mortgage
  insurance"* — the policy states the 80-90% band requires mortgage
  insurance, and 86.08% is arithmetically inside it — but flagged the
  claim anyway because of the adjacent, harder-to-verify phrase
  "indicating elevated risk."
- `CASE-2026-0003 / collateral`: flagged **"LTV ratio of 97.6% is
  excessive and not eligible under standard guidelines"** unsupported,
  reasoning that the policy "does not explicitly categorize it as
  'excessive.'" 97.6% > 97% and the policy states LTV above 97% is not
  eligible under standard guidelines — the claim's substance is correct;
  the judge objected to a synonym.

Both are false positives on the specific numeric claim, sitting inside a
`claim_text` that mixes several assertions and gets one shared boolean
`grounded` verdict — which is exactly what Phases 3 and 4 exist to catch
and quantify rather than leaving as an anecdote.

### Phase 3: the judge is reliable in isolation, less so bundled

Against the 6-case calibration set (one claim, one context, per case):
**5/6 (83%) agreement, 0 false positives, 1 false negative** (the
judge scored a cross-section-contamination claim — self-employment
content asserted from LTV-only context — as grounded when it should not
have been; the same failure mode the pre-fix retriever produced by
mislabeling chunks).

Notably, the calibration set's `ltv-86-in-band` case — the isolated
single-sentence version of Phase 2's false positive above — was scored
correctly (`grounded=True`) by the same judge. The discrepancy points at
a specific, fixable design gap rather than a fundamentally unreliable
judge: `check_groundedness` returns one `grounded` boolean for an entire
multi-sentence `claim_text`. Judging a whole paragraph as a single
pass/fail means one adjacent, harder-to-verify assertion ("indicating
elevated risk," "categorizing it as excessive") can sink an otherwise
correct claim's verdict. A per-sentence or per-claim groundedness check
would likely resolve this without changing the judge prompt at all — not
implemented here, since it's a real scope increase (spans
`GroundednessVerdict`'s shape and every caller), but now backed by
evidence instead of a guess.

### Phase 4: zero numeric errors among what the judge flagged

Across all 12 specialist analyses: **8 consistent, 0 inconsistent, 11
unrecognized** (of 19 LTV/DTI percentage citations found; some sentences
are checked twice because `claim_text` concatenates `summary` and
`key_factors`, which often restate the same figure). Zero inconsistent
findings means every LTV/DTI number a specialist actually cited was
attributed to the correct policy band — including both examples in Phase
2 that the LLM judge flagged as unsupported. "Unrecognized" (not
"consistent" or "inconsistent") is the deliberately conservative default
when a sentence names a banded percentage but doesn't use one of a fixed
set of recognizable outcome phrases — the checker declines to guess
rather than risk a wrong verdict on wording it wasn't built to parse.

This is the concrete version of Phase 3's finding: the judge's Phase 2
"unsupported" calls are, so far, entirely about phrasing and adjacent
inferential language, never about a specialist getting an LTV/DTI number
or its policy consequence wrong.

### What's still fake-mode-only, and why

Both numbers in Phase 1 are **only meaningful with `--embeddings openai`
/ `--provider openai`.** The default (`fake`) run still executes all four
phases end to end — proving the harness works with no API key — but
`FakeEmbeddings` is a content-blind hash (ADR 0003) and the fake
groundedness heuristic scores the offline model's own template
boilerplate, which by construction shares little vocabulary with real
policy text. `rag_eval.py` prints an explicit warning rather than let
those numbers be mistaken for retrieval or faithfulness quality. Phase 4
(citation accuracy) is the exception — it's deterministic and needs no
LLM or embeddings — but the offline fake specialist output never mentions
an LTV/DTI percentage, so it reports `0 citations found` rather than
anything misleading.

CI (`.github/workflows/ci.yml`) runs `rag_eval.py` as an offline smoke
test on every push — fake embeddings and fake LLM, asserting the harness
runs end to end, not gating on quality. The real, meaningful run (`
--provider openai --embeddings openai`) costs API calls and isn't fully
deterministic run-to-run (see Phase 2's two different groundedness counts
across two runs of this ADR), so it's treated as a manual/periodic check
before shipping a retrieval or prompt change, the same way `evals/run.py
--provider openai` is — not a per-commit CI gate.
