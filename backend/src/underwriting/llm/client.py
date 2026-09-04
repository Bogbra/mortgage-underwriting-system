"""Provider-agnostic LLM + embeddings factories.

Every agent module calls `build_chat_model()` — never `ChatOpenAI(...)`
directly. That single indirection is what makes `LLM_PROVIDER=anthropic`
a config change instead of a code change, and what lets the entire test
suite run against `FakeChatModel` with zero call-site differences.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from underwriting.config import Settings, settings
from underwriting.llm.fake import FakeChatModel, FakeEmbeddings


class MissingCredentialError(RuntimeError):
    """Raised when a real provider is selected but no API key is configured."""


@lru_cache
def build_chat_model(config: Settings | None = None) -> BaseChatModel:
    cfg = config or settings

    if cfg.llm_provider == "fake":
        return FakeChatModel()

    if cfg.llm_provider == "openai":
        if not cfg.openai_api_key:
            raise MissingCredentialError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            api_key=cfg.openai_api_key,
        )

    if cfg.llm_provider == "anthropic":
        if not cfg.anthropic_api_key:
            raise MissingCredentialError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY.")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=cfg.llm_model,
            temperature=cfg.llm_temperature,
            api_key=cfg.anthropic_api_key,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {cfg.llm_provider!r}")


@lru_cache
def build_embeddings(config: Settings | None = None) -> Embeddings:
    cfg = config or settings

    if cfg.embedding_provider == "fake":
        return FakeEmbeddings()

    if cfg.embedding_provider == "openai":
        if not cfg.openai_api_key:
            raise MissingCredentialError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY.")
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=cfg.embedding_model, api_key=cfg.openai_api_key)

    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {cfg.embedding_provider!r}")
