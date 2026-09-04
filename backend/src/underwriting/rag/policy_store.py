"""Policy retrieval: chunk, embed, and search the underwriting policy manual.

Kept deliberately swappable: `PolicyStore` wraps a `VectorStore` behind a
narrow interface (`retrieve`) so Chroma (local/dev) can be replaced with a
managed store (Qdrant, pgvector) for a multi-instance deployment without
touching any agent code — see docs/adr/0002.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from underwriting.config import settings
from underwriting.llm.client import build_embeddings

_SECTION_HEADING_RE = re.compile(r"^#{2,4}\s*\d+\.\d+\s+.+", re.MULTILINE)


def _section_label(text: str) -> str:
    match = _SECTION_HEADING_RE.match(text)
    return match.group(0).lstrip("#").strip() if match else "General"


class PolicyStore:
    def __init__(self, vectorstore: Chroma) -> None:
        self._vectorstore = vectorstore

    def retrieve(self, query: str, k: int = 6) -> str:
        """Return deduplicated, section-labelled policy text relevant to `query`."""

        docs = self._vectorstore.similarity_search(query, k=k)
        sections: dict[str, str] = {}
        for doc in docs:
            text = doc.page_content.strip()
            section = _section_label(text)
            if section not in sections:
                sections[section] = text
            elif text not in sections[section]:
                sections[section] += f"\n\n{text}"
        return "\n\n---\n\n".join(f"[{section}]\n{body}" for section, body in sections.items())

    def retrieve_sections(self, query: str, k: int = 6) -> list[str]:
        """Which policy sections the top-k chunks for `query` belong to, ranked.

        Used by `evals/rag_eval.py` for recall@k — a thin, non-LLM entry
        point into the same retrieval `retrieve()` uses, so the eval measures
        the exact retrieval behavior agents get, not a re-implementation of it.
        """

        docs = self._vectorstore.similarity_search(query, k=k)
        seen: list[str] = []
        for doc in docs:
            section = _section_label(doc.page_content.strip())
            if section not in seen:
                seen.append(section)
        return seen


def _load_policy_documents(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text, metadata={"source": path.name})]


_build_lock = threading.Lock()
_cached_store: PolicyStore | None = None


def get_policy_store(policy_path: Path | None = None) -> PolicyStore:
    """Lazily build (once) and return the process-wide policy store.

    Guarded by an explicit lock rather than `lru_cache`: the four specialist
    agents call this concurrently on their very first invocation (parallel
    fan-out, see graph/build.py), and `lru_cache` alone does not serialize
    the wrapped call on a cache miss — it only protects its own bookkeeping.
    Two threads racing to construct the same Chroma collection corrupts it.
    `orchestrator.run_case` also warms this before invoking the graph so the
    lock is only ever contended, never relied upon, in steady state.
    """

    global _cached_store
    if _cached_store is not None:
        return _cached_store

    with _build_lock:
        if _cached_store is None:
            path = policy_path or settings.policy_document_path
            documents = _load_policy_documents(path)

            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
            chunks = splitter.split_documents(documents)

            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=build_embeddings(),
                collection_name="underwriting_policies",
                persist_directory=str(settings.chroma_persist_dir),
            )
            _cached_store = PolicyStore(vectorstore)
    return _cached_store
