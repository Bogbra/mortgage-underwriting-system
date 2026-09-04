# ADR 0004: Deterministic PII redaction and a non-LLM bias gate

## Context

PII redaction and Fair Lending (ECOA) bias detection are both easy to
implement as plain functions and easy to weaken by accident: nothing
enforces that every code path *calls* them, and nothing prevents "ask the
model nicely not to mention protected characteristics" from being the only
line of defense against it actually doing so.

## Decision

**PII.** `domain/pii.py` defines a `PIIRedactor` protocol with one method,
`redact()`. Sanitization happens exactly once, at the workflow boundary
(`graph/build.py:initialize_node`), before `sanitized_data` — the only view
of the application any agent or prompt ever sees — is populated. The
default `RuleBasedPIIRedactor` is field-name aware (`ssn`, `name`,
`address`, `phone`, `email`) with a pattern-based fallback for PII that
leaks into free-text fields. It is deliberately offline and dependency-free
so it can never fail open because of a missing model download or a network
call; a statistical NER-based redactor (e.g. Presidio) can implement the
same protocol for messier free-text fields without touching a call site.

**Bias.** `domain/bias.py` is a deterministic substring/regex scanner
(`scan_for_bias_signals`) that every specialist agent runs, unconditionally,
against its own output (`agents/credit.py` etc.) — not something a prompt
instruction can turn off. It is intentionally a hard gate, not a
"best-effort" check: a prompt regression, a poisoned policy document, or a
jailbreak attempt cannot silently disable it, because it never asks the
model anything. The critic agent's LLM-based review is a second,
complementary layer on top of this for subtler inconsistencies (one analyst
being harsher than the facts of *this* application warrant) that a regex
genuinely cannot catch — never a replacement for the deterministic scan.

## Consequences

- Every bias flag raised anywhere in the workflow forces
  `human_review_required = True` (`agents/decision.py`), regardless of the
  computed risk score — a compliance flag cannot be outvoted by an
  otherwise-clean risk assessment.
- The deterministic scanner will produce false positives (e.g. a policy
  excerpt that legitimately discusses "age" of an account) — accepted,
  because a human review escalation is a much cheaper failure mode than a
  missed Fair Lending violation.
- The redactor operates on field names and text patterns, not on document
  images or unstructured attachments — out of scope for this project, but
  the boundary is exactly where a stronger redactor (Presidio, or a
  document-understanding model) would slot in.
