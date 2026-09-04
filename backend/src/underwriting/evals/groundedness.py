"""RAG faithfulness: is an agent's claim actually supported by what it retrieved?

Recall@k (see `rag_eval.py`) only tells you the retriever found the right
policy section. It says nothing about whether the agent's generated
analysis actually stuck to that text instead of inventing a plausible
policy detail — the two failure modes are independent, and a system can
retrieve perfectly while still hallucinating in the write-up.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from underwriting.domain.schemas import GroundednessVerdict
from underwriting.llm.client import build_chat_model

JUDGE_SYSTEM_PROMPT = """You are a strict fact-checking judge for a mortgage underwriting \
system.

You will be given a POLICY CONTEXT (retrieved policy excerpts) and a CLAIM (an underwriting \
agent's analysis). Determine whether every factual or policy assertion in the CLAIM is \
actually supported by the POLICY CONTEXT.

Do NOT penalize the claim for citing case-specific numbers (credit scores, dollar amounts, \
ratios) that were computed elsewhere and are not expected to appear in the policy text \
verbatim — only judge whether policy rules/thresholds/requirements referenced in the claim \
are consistent with what the context actually says. If the claim makes no policy assertion \
at all (e.g. it only restates case facts), treat it as grounded.

List any specific unsupported claims verbatim. Be strict: an assertion the context doesn't \
mention at all is not supported, even if it sounds plausible."""


def check_groundedness(claim_text: str, context: str, llm=None) -> GroundednessVerdict:
    """Judge whether `claim_text` is supported by `context`.

    `llm` defaults to `build_chat_model()` — pass one explicitly to reuse a
    single instance across many checks instead of hitting the (cached)
    factory each time.
    """

    judge = (llm or build_chat_model()).with_structured_output(GroundednessVerdict)
    user_prompt = f"POLICY CONTEXT:\n{context}\n\nCLAIM:\n{claim_text}"
    return judge.invoke(
        [SystemMessage(content=JUDGE_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )
