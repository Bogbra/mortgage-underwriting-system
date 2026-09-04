"""Session-wide test environment.

Must run before `underwriting.config` is imported by any test module, so
these env vars are set at conftest *module* scope (executed once, at
collection start) rather than inside a fixture function.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_tmp_dir = Path(tempfile.mkdtemp(prefix="underwriting-tests-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_dir / 'test.db'}")
os.environ.setdefault("CHROMA_PERSIST_DIR", str(_tmp_dir / "chroma"))
