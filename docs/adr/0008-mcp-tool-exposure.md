# ADR 0008: Expose the deterministic tools and policy retrieval over MCP

## Context

The deterministic calculators (`domain/calculations.py`) and policy
retrieval (`rag/policy_store.py`) are already plain, framework-agnostic
Python — nothing in them imports LangGraph or LangChain. The only thing
tying them to this project's agents is that `agents/*.py` happens to be
the only caller. Any other agent framework, or a human using an MCP
client directly, has no way to reach the same audit-grade DTI/LTV/reserve
math without reimplementing it.

## Decision

`mcp_server.py` wraps the same functions `agents/*.py` calls in-process —
not a reimplementation, the identical `domain/calculations` functions —
behind the [Model Context Protocol](https://modelcontextprotocol.io)
using the official `mcp` SDK's `MCPServer`. Nine tools: the eight
deterministic calculators (`calculate_dti_ratio`, `calculate_ltv_ratio`,
`calculate_down_payment_adequacy`, `calculate_reserves`,
`calculate_housing_expense_ratio`, `check_credit_score_policy`,
`find_large_deposits`, `calculate_total_debt_obligations`), plus
`retrieve_underwriting_policy` wrapping `PolicyStore.retrieve()`. Each tool
returns `.model_dump()` of the same
Pydantic result model the LangGraph agents use — one calculation, one
result shape, two transports (a direct Python call inside the graph, or
an MCP `tools/call` from anywhere else).

Kept as a separate optional dependency group (`uv sync --extra mcp`), not
folded into `dev` — most work on this repo never touches MCP, and
`tests/unit/test_mcp_server.py` skips (via `pytest.importorskip`) rather
than fails when the extra isn't installed. CI installs it explicitly
(`--extra dev --extra mcp`) so the tools are actually exercised, not just
present.

## Consequences

- Any MCP client (Claude Desktop, a different agent framework, an ad hoc
  script) can call `calculate_ltv_ratio` or `retrieve_underwriting_policy`
  and get exactly the numbers/text this system's own agents would compute
  — a second consumer never has to trust an LLM's arithmetic or
  re-implement the policy chunking to get the same answer.
- The tools are stateless and read-only from the caller's perspective
  (`retrieve_underwriting_policy` reads the shared policy store; nothing
  here writes to `cases`/`audit_events` or touches applicant PII) — there
  was no new guardrail surface to add. If this server ever exposed
  something that reads or writes case data, it would need its own
  authentication; today it doesn't have any, deliberately, because it has
  nothing behind it worth authenticating for.
- `MCPServer.run()` defaults to stdio transport — correct for a local
  client (Claude Desktop, an IDE) launching the server as a subprocess.
  Multi-client remote access would mean `transport="streamable-http"` and
  actual auth, which is out of scope for what this ADR is demonstrating.
