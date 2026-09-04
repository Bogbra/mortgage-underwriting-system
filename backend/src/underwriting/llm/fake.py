"""Deterministic, offline stand-ins for a chat model and an embedder.

Two things this project should never require just to be *evaluated*: a paid
API key, or a network call. `llm_provider=fake` / `embedding_provider=fake`
(the defaults) route through this module instead, so `docker compose up`
produces a fully working end-to-end demo — real agent graph, real RAG
retrieval, real guardrails — with synthetic-but-deterministic reasoning
in place of an LLM call. Golden-case regression tests run against this
model in CI for the same reason: no flakiness, no API cost, no network
dependency, and a bug in the *graph* can't hide behind LLM variance.

Swapping to a real provider is a one-line env change (`LLM_PROVIDER=openai`)
— see underwriting/llm/client.py.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda

from underwriting.domain.schemas import (
    AssetAnalysis,
    CollateralAnalysis,
    CreditAnalysis,
    CriticReview,
    DecisionOutcome,
    FinalDecision,
    GroundednessVerdict,
    IncomeAnalysis,
    Recommendation,
    RiskLevel,
)

_RECOMMENDATION_RE = re.compile(r'"?recommendation"?\s*[:=]\s*"?([A-Z]+)"?')
_RISK_SCORE_HINT_RE = re.compile(r'"?risk_score"?\s*[:=]\s*(\d+)')

# Every `domain/calculations.py` result model uses a different vocabulary for
# "this number is bad" — DTI/LTV/housing use `status: RatioStatus`,
# credit score uses `tier: CreditTier`, reserves uses a boolean `adequate`.
# Scanning only `"status"` (as an earlier version of this module did) silently
# treats every credit-score and reserves result as fine regardless of their
# actual value — exactly the kind of bug that would let a 588-credit-score,
# insufficient-reserves applicant read as LOW risk. All three vocabularies are
# scanned here so a specialist's severity reflects its actual inputs.
_STATUS_RE = re.compile(r'"status"\s*:\s*"(\w+)"')
_TIER_RE = re.compile(r'"tier"\s*:\s*"(\w+)"')
_ADEQUATE_RE = re.compile(r'"adequate"\s*:\s*(true|false)')
_DEPOSITS_RE = re.compile(r'"deposits"\s*:\s*(\[[^\]]*\])')

_STATUS_SEVERITY: dict[str, int] = {
    "excessive": 3,
    "below_minimum": 3,
    "insufficient": 3,
    "high": 2,
    "elevated": 2,
    "fair": 2,
    "acceptable": 0,
    "good": 0,
    "excellent": 0,
    "very_good": 0,
    "adequate": 0,
}

_SPECIALIST_SCHEMAS = (CreditAnalysis, IncomeAnalysis, AssetAnalysis, CollateralAnalysis)


def _messages_to_text(messages: Sequence[BaseMessage]) -> str:
    return "\n".join(str(m.content) for m in messages)


def _worst_status_severity(text: str) -> int:
    severities = [_STATUS_SEVERITY.get(s.lower(), 1) for s in _STATUS_RE.findall(text)]
    severities += [_STATUS_SEVERITY.get(t.lower(), 1) for t in _TIER_RE.findall(text)]
    severities += [3 for adequate in _ADEQUATE_RE.findall(text) if adequate == "false"]
    severities += [2 for deposits in _DEPOSITS_RE.findall(text) if deposits.strip("[] \n") != ""]
    return max(severities, default=0)


def _risk_level_for_severity(severity: int) -> RiskLevel:
    if severity >= 3:
        return RiskLevel.HIGH
    if severity >= 2:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _recommendation_for(risk: RiskLevel) -> Recommendation:
    return {
        RiskLevel.LOW: Recommendation.PASS,
        RiskLevel.MEDIUM: Recommendation.CONDITIONAL,
        RiskLevel.HIGH: Recommendation.FAIL,
    }[risk]


def _build_specialist(schema: type, text: str):
    severity = _worst_status_severity(text)
    risk = _risk_level_for_severity(severity)
    recommendation = _recommendation_for(risk)
    factors = (
        [f"status={s}" for s in _STATUS_RE.findall(text)]
        + [f"tier={t}" for t in _TIER_RE.findall(text)]
        + [f"reserves_adequate={a}" for a in _ADEQUATE_RE.findall(text)]
        + [f"large_deposits_flagged={d.strip() != '[]'}" for d in _DEPOSITS_RE.findall(text)]
    )
    return schema(
        summary=(
            f"[demo-mode] Deterministic metrics indicate {risk.value.lower()} risk "
            f"({len(factors)} calculated metric(s) considered)."
        ),
        risk_level=risk,
        recommendation=recommendation,
        key_factors=[f"calculated {f}" for f in factors[:5]] or ["No adverse metrics found."],
        conditions=(
            []
            if recommendation == Recommendation.PASS
            else ["Underwriter to review flagged metrics before final approval."]
        ),
    )


def _build_critic(text: str) -> CriticReview:
    recommendations = _RECOMMENDATION_RE.findall(text)
    severity_map = {"PASS": 20, "CONDITIONAL": 50, "FAIL": 85}
    score = max((severity_map.get(r, 50) for r in recommendations), default=50)
    return CriticReview(
        consistent=True,
        issues=[],
        synthesis=(
            f"[demo-mode] Synthesis of {len(recommendations)} specialist recommendation(s): "
            f"{', '.join(recommendations) or 'none found'}."
        ),
        preliminary_risk_score=score,
    )


def _build_decision(text: str) -> DecisionOutcome:
    match = _RISK_SCORE_HINT_RE.search(text)
    score = int(match.group(1)) if match else 50
    score = max(0, min(100, score))
    decision = (
        FinalDecision.APPROVED
        if score <= 30
        else FinalDecision.DENIED
        if score >= 65
        else FinalDecision.CONDITIONAL_APPROVAL
    )
    return DecisionOutcome(
        risk_score=score,
        decision=decision,
        conditions=(
            []
            if decision == FinalDecision.APPROVED
            else ["Senior underwriter sign-off required before funding."]
        ),
        credit_memo=(
            f"[demo-mode] Synthesized decision: {decision.value} at risk score {score}/100. "
            "This narrative was generated by the offline fake model, not an LLM — set "
            "OPENAI_API_KEY or ANTHROPIC_API_KEY and LLM_PROVIDER to produce a full narrative memo."
        ),
    )


_CONTEXT_RE = re.compile(r"POLICY CONTEXT:\s*(.*?)\s*CLAIM:", re.DOTALL)
_CLAIM_RE = re.compile(r"CLAIM:\s*(.*)\Z", re.DOTALL)
_WORD_RE = re.compile(r"[a-zA-Z]{4,}")
_GROUNDEDNESS_OVERLAP_THRESHOLD = 0.35


def _build_groundedness(text: str) -> GroundednessVerdict:
    """Word-overlap heuristic standing in for an LLM-as-judge groundedness check.

    Real groundedness checking needs a model reading both the claim and the
    context — a hash embedding or a regex can't judge entailment. This is
    explicitly a rough proxy so `evals/rag_eval.py` has something offline to
    run, not a claim that vocabulary overlap proves a statement is supported.
    """

    claim_match = _CLAIM_RE.search(text)
    context_match = _CONTEXT_RE.search(text)
    claim = claim_match.group(1) if claim_match else text
    context = context_match.group(1) if context_match else ""

    claim_words = {w.lower() for w in _WORD_RE.findall(claim)}
    context_words = {w.lower() for w in _WORD_RE.findall(context)}
    if not claim_words:
        return GroundednessVerdict(grounded=True, notes="[demo-mode] empty claim.")

    overlap_ratio = len(claim_words & context_words) / len(claim_words)
    grounded = overlap_ratio >= _GROUNDEDNESS_OVERLAP_THRESHOLD
    return GroundednessVerdict(
        grounded=grounded,
        unsupported_claims=[] if grounded else [claim.strip()[:200]],
        notes=(
            f"[demo-mode] word-overlap heuristic: {overlap_ratio:.0%} of claim vocabulary "
            "found in retrieved context — an offline stand-in for a real LLM-as-judge check."
        ),
    )


class FakeChatModel(BaseChatModel):
    """A `BaseChatModel` that never leaves the process.

    Only `with_structured_output` is meaningfully implemented — that is the
    only mode the agent workflow uses. Plain `.invoke()` returns a labelled
    placeholder so misuse is obvious rather than silently wrong.
    """

    @property
    def _llm_type(self) -> str:
        return "fake-deterministic"

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        message = AIMessage(content="[demo-mode] FakeChatModel does not generate free text.")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def with_structured_output(self, schema: type, **kwargs: Any) -> Runnable:
        def _invoke(messages: Sequence[BaseMessage]):
            text = _messages_to_text(messages)
            if schema in _SPECIALIST_SCHEMAS:
                return _build_specialist(schema, text)
            if schema is CriticReview:
                return _build_critic(text)
            if schema is DecisionOutcome:
                return _build_decision(text)
            if schema is GroundednessVerdict:
                return _build_groundedness(text)
            raise TypeError(f"FakeChatModel has no deterministic handler for {schema!r}")

        return RunnableLambda(_invoke)


class FakeEmbeddings(Embeddings):
    """Deterministic, hash-based embeddings — no model download, no network.

    Similarity is meaningless beyond exact/near-duplicate text matches, which
    is sufficient for exercising the RAG retrieval pipeline in tests and demo
    mode. Not intended to produce relevant results against arbitrary policy
    text; swap `EMBEDDING_PROVIDER=openai` for real semantic retrieval.
    """

    dimensions: int = 384

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat the 32-byte digest to fill the target dimensionality.
        raw = (digest * ((self.dimensions // len(digest)) + 1))[: self.dimensions]
        return [b / 255.0 for b in raw]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
