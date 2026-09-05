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


def _section_label(doc: Document) -> str:
    """The policy section a chunk belongs to.

    Prefers the `section` metadata `_chunk_policy_document` stamps on every
    chunk at indexing time. Falls back to matching the chunk's own first
    line for documents indexed before that metadata existed (e.g. a stale
    persisted Chroma collection) — see docs/adr/0007 for why relying on the
    first-line match alone was wrong: a chunk that doesn't happen to start
    on a heading (because character-count splitting cut across a section
    boundary) silently mislabels as "General" instead of raising.
    """

    section = doc.metadata.get("section")
    if section:
        return section
    match = _SECTION_HEADING_RE.match(doc.page_content.strip())
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
            section = _section_label(doc)
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
            section = _section_label(doc)
            if section not in seen:
                seen.append(section)
        return seen


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split raw policy text on `### X.Y Heading` boundaries.

    The old approach ran `RecursiveCharacterTextSplitter` over the whole
    document and identified a chunk's section by regex-matching its first
    line — which silently mislabels any chunk that a character-count split
    happens to cut mid-section (see docs/adr/0007: this is why recall@k sat
    at 43%, with misses consistently landing on chunks the harness had
    stamped "General" or an adjacent, wrong section). Splitting on headers
    first guarantees every chunk is drawn from exactly one section, however
    it's later subdivided by size.
    """

    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [("General", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("General", preamble))

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = match.group(0).lstrip("#").strip()
        sections.append((label, text[match.start() : end].strip()))
    return sections


def _chunk_policy_document(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    chunks: list[Document] = []
    for label, section_text in _split_into_sections(text):
        for piece in splitter.split_text(section_text):
            chunks.append(
                Document(page_content=piece, metadata={"source": path.name, "section": label})
            )
    return chunks


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
            chunks = _chunk_policy_document(path)

            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=build_embeddings(),
                collection_name="underwriting_policies",
                persist_directory=str(settings.chroma_persist_dir),
            )
            _cached_store = PolicyStore(vectorstore)
    return _cached_store
