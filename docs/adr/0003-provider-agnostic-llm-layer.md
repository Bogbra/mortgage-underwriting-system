# ADR 0003: Provider-agnostic LLM layer with an offline fake

## Context

Instantiating `ChatOpenAI(...)` (or any provider SDK client) directly inside
every agent module makes the codebase inseparable from that one provider and
from wherever its credentials happen to be configured. It also means there
is no way to test the agent logic without spending real API credits, and no
way to run the project at all without first obtaining a key.

## Decision

`llm/client.py` exposes exactly two factories — `build_chat_model()` and
`build_embeddings()` — read from `Settings.llm_provider` /
`Settings.embedding_provider` (`openai`, `anthropic`, or `fake`). No agent
module ever imports `ChatOpenAI` or `ChatAnthropic` directly. Missing a
required API key for a real provider raises `MissingCredentialError`
immediately at call time rather than failing deep inside a LangChain
internal with an opaque HTTP error.

`fake` is the default for both. `llm/fake.py`'s `FakeChatModel` implements
`with_structured_output` by reading the `DETERMINISTIC_METRICS` block
already embedded in every prompt (see ADR 0001) and deriving a plausible,
fully deterministic structured response from it — worst status band per
specialist, a critic score derived from the specialists' recommendations, a
decision derived from the critic's score. `FakeEmbeddings` is a
hash-based, dependency-free embedder sufficient to exercise the RAG
retrieval *pipeline* (chunking, storage, similarity search plumbing) —
explicitly not sufficient for evaluating retrieval *quality*, which needs
real embeddings.

## Consequences

- `docker compose up` with zero configured secrets produces a fully working
  demo: real graph, real parallel execution, real guardrails, synthetic
  reasoning. This is what `tests/integration/` and
  `evals/run.py --provider fake` (the default) exercise, and what CI runs
  on every commit — no API cost, no network flake, no key management for
  contributors.
- Swapping providers, or moving off the fake for a live eval run, is a
  `.env` change (`LLM_PROVIDER=openai`) — see `evals/run.py --provider
  openai` for the live-eval path, which is deliberately a separate,
  explicitly-invoked script rather than something CI runs automatically.
- The fake model does not exercise real prompt quality, hallucination
  behavior, or provider-specific structured-output quirks. It validates the
  *workflow*; the golden-case eval script validates *decision quality*
  against a real provider and is what should gate an actual prompt change.
