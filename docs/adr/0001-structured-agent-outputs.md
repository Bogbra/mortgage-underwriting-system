# ADR 0001: Structured outputs instead of free-text parsing

## Context

A Decision Agent that returns a free-text block and recovers the fields it
needs with `re.search(r"RISK_SCORE:\s*(\d+)")` and a handful of
`"APPROVED" in content` string checks has to fall back to a hardcoded
default (e.g. `risk_score = 50`) whenever the regex misses. That means a
phrasing change in the model's output — or a prompt regression — degrades
silently into a wrong-but-plausible default instead of a visible failure.
The same problem exists, less critically, for any narrative-only specialist
output: nothing downstream can reliably tell a PASS from a CONDITIONAL
recommendation without more string matching.

## Decision

Every agent binds its LLM call to a Pydantic schema via
`llm.with_structured_output(Schema)` (`domain/schemas.py`:
`CreditAnalysis`, `IncomeAnalysis`, `AssetAnalysis`, `CollateralAnalysis`,
`CriticReview`, `DecisionOutcome`). `risk_level` and `recommendation` are
constrained enums, not free text. A response that doesn't fit the schema is
a `ValidationError`, not a silently wrong default.

Numbers that must be exact (DTI, LTV, reserve coverage, credit tier) are
never asked of the model at all — `domain/calculations.py` computes them in
plain Python and the result is injected into the prompt as
`DETERMINISTIC_METRICS`, with an explicit "do not recompute" instruction.
Agents explain a number; they never produce one.

## Consequences

- A malformed or out-of-policy model response fails the request instead of
  quietly defaulting to `risk_score=50` or `CONDITIONAL_APPROVAL`.
- The final `human_review_required` flag (`agents/decision.py`) is computed
  by a plain Python business rule against the validated `risk_score` and
  `bias_flags`, not by the model — a "the LLM forgot to flag this" failure
  mode is structurally impossible.
- Cost: schema-constrained output is marginally more restrictive for the
  model, and every schema change is a breaking change for whatever provider
  integration is in use. Acceptable trade for auditability in a regulated
  domain.
