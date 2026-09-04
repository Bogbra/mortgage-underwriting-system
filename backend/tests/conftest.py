"""Session-wide test environment.

Must run before `underwriting.config` is imported by any test module, so
these env vars are set at conftest *module* scope (executed once, at
collection start) rather than inside a fixture function.

LLM_PROVIDER / EMBEDDING_PROVIDER are forced to "fake" — not defaulted —
because pydantic-settings resolves real process env vars *and* `.env` file
values before falling back to the field default, and a developer's local
`backend/.env` legitimately sets `LLM_PROVIDER=openai` to run a live eval
(see evals/run.py). Without this override, the test suite would silently
start making real, billed API calls the moment that `.env` file exists —
exactly what happened here: a full pytest run went from ~0.6s to ~58s the
first time `backend/.env` was created with a real provider configured. The
whole point of `llm/fake.py` (ADR 0003) is that this suite never depends on
network access or an API key; this override is what actually guarantees it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_tmp_dir = Path(tempfile.mkdtemp(prefix="underwriting-tests-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_dir / 'test.db'}")
os.environ.setdefault("CHROMA_PERSIST_DIR", str(_tmp_dir / "chroma"))
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = "fake"
