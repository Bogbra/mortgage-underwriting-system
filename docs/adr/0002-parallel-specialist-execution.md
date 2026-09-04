# ADR 0002: Parallel fan-out for the four specialist agents

## Context

A `supervisor` node that loops — check which analyses are done, route to the
next incomplete one, come back, repeat — turns credit → income → asset →
collateral into four sequential LLM round-trips, even though none of those
four agents reads another's output. Only the critic and decision stages have
a genuine dependency on the specialists being complete.

## Decision

`graph/build.py` fans out from `initialize` directly to all four specialist
nodes, and each specialist has an edge into `critic`. LangGraph (Pregel
under the hood) treats a node with multiple incoming edges as a join: it
only executes once every predecessor in the current step has produced its
update, so `critic` still sees all four analyses, in the same state, with
no explicit synchronization code required.

Two fields need special handling under concurrent writers: `bias_flags` and
`reasoning_chain` are annotated with a small `_append` reducer
(`domain/schemas.py`) so four simultaneous partial-state updates concatenate
instead of the last writer overwriting the other three. This is exercised
directly by
`tests/integration/test_graph_fake_llm.py::test_bias_flags_are_aggregated_from_all_parallel_branches`,
which forces all four agents to raise a flag and asserts all four survive
the merge — the scenario a naive (overwrite, not append) reducer would
silently drop three of.

## Consequences

- Wall-clock latency for the specialist stage drops from ~4x a single LLM
  call to ~1x (bounded by the slowest of the four), at the cost of 4x the
  concurrent provider load for that stage — worth checking against your
  provider's concurrency/rate limits before raising traffic.
- `rag/policy_store.py`'s Chroma store is built lazily on first use; under
  concurrent first access from four threads this raced and corrupted the
  client (`ValueError: Could not connect to tenant default_tenant`). Fixed
  with an explicit lock plus `orchestrator.run_case` eagerly warming the
  store before invoking the graph — a good example of a bug parallel
  execution introduces that sequential execution never would have exposed.
- The critic and decision stages remain sequential by design — they have a
  real dependency, not an artificial one, so parallelizing them further
  would only shuffle risk-scoring order for no latency benefit.
