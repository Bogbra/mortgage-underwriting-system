# Mortgage Underwriting System

[![CI](https://github.com/Bogbra/mortgage-underwriting-system/workflows/CI/badge.svg)](https://github.com/Bogbra/mortgage-underwriting-system/actions/workflows/ci.yml)

A multi-agent mortgage underwriting engine: four specialist agents (credit,
income, asset, collateral) analyze an application in parallel, a critic
cross-checks their findings, and a decision agent produces an audit-ready
outcome — with deterministic guardrails (PII redaction, Fair Lending bias
scanning), a human-in-the-loop review gate, and a full audit trail.

It's built as a service: a LangGraph agent engine behind a FastAPI API,
persisted to Postgres/SQLite, with a Next.js reviewer dashboard on top.

<p align="center">
  <img src="docs/screenshots/case-list.png" alt="Case queue: three cases with color-coded status, decision, and risk score" width="800"><br>
  <sub>Case queue — status, decision, and risk score at a glance.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/case-detail.png" alt="Case detail: final decision, human-in-the-loop review form, all four specialist analyses, critic synthesis, and audit trail" width="800"><br>
  <sub>Case detail — decision memo, human-in-the-loop review, every specialist's analysis, and a full audit trail.</sub>
</p>

## Why it's built this way

The short version — the full reasoning for each decision is in
[`docs/adr/`](docs/adr/):

- **[Structured outputs, not regex-parsed prose.](docs/adr/0001-structured-agent-outputs.md)**
  Every agent's response is a validated Pydantic model. Numbers that must be
  exact (DTI, LTV, reserves) are computed in plain Python and handed to the
  model as fact — never asked of it.
- **[Specialist agents run in parallel.](docs/adr/0002-parallel-specialist-execution.md)**
  Credit/income/asset/collateral don't depend on each other; they fan out
  from a single node and join at the critic, cutting that stage's latency
  roughly 4x versus polling them one at a time.
- **[The LLM provider is a config value, not a code path.](docs/adr/0003-provider-agnostic-llm-layer.md)**
  `LLM_PROVIDER=fake` (the default) runs the entire real workflow — parallel
  agents, RAG, guardrails — against a deterministic offline model. No API
  key is required to run this project or its test suite.
- **[PII redaction and bias detection are deterministic gates.](docs/adr/0004-deterministic-pii-and-bias-guardrails.md)**
  Neither depends on the model choosing to comply with an instruction.
- **[Persistence, audit trail, and auth are explicit, minimal, and swappable.](docs/adr/0005-persistence-audit-and-auth.md)**
  SQLite locally, Postgres in Docker, an append-only audit log, and a
  `Principal`-based auth seam sized for a portfolio project but shaped like
  the real thing.

## Architecture

```
                    ┌─────────────────────────────┐
                    │      Next.js dashboard       │
                    │  (Server Components +        │
                    │   Server Actions; token       │
                    │   never reaches the browser)  │
                    └───────────────┬───────────────┘
                                    │ REST (bearer auth)
                    ┌───────────────▼───────────────┐
                    │           FastAPI              │
                    │  cases router · auth · rate    │
                    │  limiting · SQLAlchemy (Case,  │
                    │  audit_events)                 │
                    └───────────────┬───────────────┘
                                    │ BackgroundTasks
                    ┌───────────────▼───────────────┐
                    │        LangGraph workflow      │
                    │                                │
                    │   initialize (PII redaction)   │
                    │        │  │  │  │              │
                    │     credit income asset collat  │ ← parallel
                    │        │  │  │  │              │
                    │        └──┴──┴──┘              │
                    │            ▼                   │
                    │          critic                │
                    │            ▼                   │
                    │         decision                │
                    └───────────────┬───────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     ▼              ▼              ▼
              domain/calculations  rag/policy_store  domain/bias
              (deterministic)      (Chroma + RAG)    (hard gate)
```

## Repository layout

```
backend/            Python: domain logic, agents, graph, RAG, FastAPI service
  src/underwriting/
    domain/          Pure business logic: calculations, PII, bias, schemas
    llm/             Provider-agnostic client + offline fake model/embeddings
    rag/             Policy chunking, embedding, retrieval
    agents/          One module per agent (credit/income/asset/collateral/critic/decision)
    graph/           The LangGraph workflow definition
    api/             FastAPI app: routers, auth, persistence, rate limiting
    evals/           Golden-case regression eval script
  data/              Policy manual (markdown) + golden test cases (JSON)
  tests/             pytest: unit (domain) + integration (graph, API)
apps/web/            Next.js 15 dashboard (case queue, detail, HITL review)
infra/               Dockerfiles + docker-compose (api, web, Postgres)
docs/adr/            Architecture decision records
```

## Running it

### Locally (fastest inner loop)

```bash
# Backend
cd backend
uv sync --extra dev
uv run uvicorn underwriting.api.main:app --reload --port 8000

# Frontend, in another terminal
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`, go to **New case**, load one of the three
sample applicants, and submit — no API key needed, `LLM_PROVIDER=fake` is
the default. Swap in a real key by copying `backend/.env.example` to
`backend/.env` and setting `LLM_PROVIDER=openai` + `OPENAI_API_KEY` (or the
Anthropic equivalents).

### Docker Compose (Postgres-backed)

```bash
docker compose -f infra/docker-compose.yml up --build
```

Dashboard at `http://localhost:3000`, API at `http://localhost:8000`.

## Testing and evals

```bash
cd backend
uv run pytest tests -q                    # 43 tests: domain unit tests +
                                           # full-graph integration tests +
                                           # API tests, all offline
uv run python -m underwriting.evals.run   # golden-case decision regression
uv run ruff check src tests               # lint
```

`tests/integration/test_graph_fake_llm.py` runs the real parallel workflow
end-to-end, including a regression test that forces all four specialist
agents to raise a bias flag simultaneously and asserts all four survive the
concurrent state merge — the exact bug class a naive (overwrite, not
append) LangGraph reducer would introduce silently.

`evals/run.py` is the decision-quality gate: it runs the three golden cases
(a clean approval, a marginal case with several real flags, and a clear
denial) and diffs the actual decision against the expected one. Pass
`--provider openai` to run it against a live model before shipping a prompt
change.

## Security posture (and its limits)

- PII is redacted once, at the workflow boundary, before any LLM call —
  never re-derived downstream.
- Fair Lending (ECOA) compliance has a deterministic regex/substring gate
  that runs on every specialist output unconditionally, plus an LLM-based
  critic review as a second layer for subtler issues.
- Auth is bearer-token based with a `caller` / `reviewer` role split; the
  frontend keeps both tokens server-side and never ships them to the
  browser.
- A simple in-process rate limiter sits in front of the API.
- What's explicitly **not** production-hardened, and documented as such in
  [ADR 0005](docs/adr/0005-persistence-audit-and-auth.md): the auth tokens
  are a placeholder for a real IdP, there's no encryption-at-rest, and the
  rate limiter doesn't survive multiple instances.
