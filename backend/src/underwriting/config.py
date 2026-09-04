"""Runtime configuration, loaded from environment variables / .env.

Nothing in this module is a secret's default value — there is no bundled
API key, no hardcoded proxy URL. A missing credential fails fast at startup
instead of silently falling back to an undocumented default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM provider — swap without touching agent code.
    llm_provider: Literal["openai", "anthropic", "fake"] = "fake"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Embeddings for the RAG policy store (OpenAI-compatible endpoint).
    embedding_provider: Literal["openai", "fake"] = "fake"
    embedding_model: str = "text-embedding-3-small"

    # Storage
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'underwriting.db'}"
    chroma_persist_dir: Path = BACKEND_ROOT / "data" / "chroma"
    policy_document_path: Path = BACKEND_ROOT / "data" / "policies" / "underwriting_policies.md"

    # API / auth
    api_bearer_token: str = "dev-local-token"
    reviewer_bearer_token: str = "dev-reviewer-token"
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Guardrail thresholds
    human_review_risk_threshold: int = 65


settings = Settings()
