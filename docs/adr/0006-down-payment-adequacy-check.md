# ADR 0006: Down-payment adequacy as its own deterministic check

## Context

Reserve adequacy was computed against an applicant's *gross* liquid assets
(`checking + savings`), with no check anywhere in the deterministic layer
for whether those same liquid assets were actually enough to cover the
required down payment in the first place. A down payment and post-closing
reserves both draw from the same pool of money; treating them as
independent was silently wrong.

This surfaced by running the golden-case eval harness (`evals/run.py`)
against a real model (`--provider openai`, `gpt-4o-mini`) instead of only
the offline fake model. The "clean approval" golden case had a down payment
requirement of $95,000 against only $60,000 in liquid assets — a real
$35,000 shortfall the deterministic layer never computed and so never
surfaced to the asset agent as a fact. The real model reasoned about the
raw numbers in its prompt context and caught it anyway, downgrading the
case to `CONDITIONAL_APPROVAL`. The offline fake model, which only reads
structured `DETERMINISTIC_METRICS`, had nothing to catch — it isn't a
substitute for judgment, it can only be as good as what it's given to read.

## Decision

Added `domain/calculations.py:calculate_down_payment_adequacy()` — a small,
pure function returning a `DownPaymentResult` (required amount, available
liquid assets, surplus/shortfall, `adequate: bool`), following the same
shape as every other deterministic result in this module.

`agents/asset.py` now:
1. Runs this check first and includes it in `DETERMINISTIC_METRICS`.
2. Computes reserves against `liquid_assets - down_payment_required`
   (floored at 0), not gross liquid assets — reserves are what's left
   *after* the down payment is paid, not before.

The golden-case fixtures (`data/test_cases/mortgage_test_cases.json`, and
its frontend mirror `apps/web/lib/demoFixtures.ts`) were recalibrated so
the intended "clean approval" case is actually clean under this corrected
check, and the "marginal" case keeps its real risk factors (elevated LTV,
high DTI, an undocumented large deposit, two late payments) without also
tripping a reserves shortfall that was really a side effect of the
now-fixed bug rather than an intentional part of that case's story.

## Consequences

- Every specialist test and the eval harness now pass against both the
  fake model and a real provider (`gpt-4o-mini`), confirmed by rerunning
  `evals/run.py --provider openai` after the fix: 3/3 golden cases, same
  decisions as the offline run.
- This is the concrete argument for running the live eval at all, not just
  the offline one: the offline fake model validates that the *workflow*
  runs correctly, but it cannot catch a gap in what the deterministic layer
  computes in the first place — only a model reasoning over the raw
  underlying numbers surfaced this.
- `tests/conftest.py` was hardening at the same time: it previously only
  `setdefault`-ed `DATABASE_URL`/`CHROMA_PERSIST_DIR`, so once a local
  `backend/.env` set `LLM_PROVIDER=openai` for this live-eval run, the
  *entire pytest suite* silently started making real, billed API calls
  (a ~0.6s run became ~58s). Fixed by forcing `LLM_PROVIDER`/
  `EMBEDDING_PROVIDER` to `fake` unconditionally in `conftest.py`,
  regardless of what a developer's local `.env` contains — the pytest
  suite must never depend on network access or spend API credits, full
  stop.
