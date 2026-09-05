"""Deterministic policy-claim consistency check for LTV/DTI numeric claims.

Not "citation accuracy" in the general RAG sense of claim -> cited source
-> does the source support the claim. What this module actually checks is
narrower: for every LTV or DTI percentage a claim mentions, does the
claim's stated outcome (mortgage insurance required or not, compensating
factors required or not, eligible or not) match the band that percentage
falls in per the policy manual's own numeric bands (section 4.1/2.2)? Kept
under the name `citation_accuracy` for continuity with `rag_eval.py`'s
Phase 4, but scoped and documented here precisely so it isn't mistaken for
a general source-attribution checker.

Groundedness (`groundedness.py`) asks an LLM judge whether a claim is
supported *somewhere* in a retrieved context blob — necessary, but not
sufficient. A judge reading a large blob can also go the other way and
flag a claim as unsupported when the claim is actually a correct inference
from a stated numeric band: `docs/adr/0007-rag-evaluation.md` documents
exactly this — a judge scored "LTV of 86.08% requires mortgage insurance"
as an unsupported claim, even though the retrieved policy text states the
80-90% band requires mortgage insurance and 86.08% is arithmetically in
that band.

This module checks that one narrow but concrete case deterministically,
with no LLM in the loop. A regex/keyword check can't be talked into a
false positive or false negative the way a judge can — it either matches
the fixed band table in `data/policies/underwriting_policies.md` section
4.1/2.2 (mirroring `domain/calculations.py`'s own `<=` boundaries exactly,
so a value sitting exactly on a threshold lands in the same band the real
calculator would put it in), or it doesn't.

Deliberately scoped to LTV and DTI — the two sections in the policy manual
that define numeric bands rather than a single threshold, and the two
implicated in the false positive above. Extending this table to every
banded policy figure, or generalizing to real citation-source checking, is
future work, not something this eval needs today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

# "LTV above 80%" means value > 80, which bands as if it were the *next*
# band up under domain/calculations.py's <= semantics — not the band that
# contains 80 itself. Without this, a claim quoting the threshold in "above
# X%" phrasing gets banded as X exactly and looks inconsistent even when
# it's a correct paraphrase of the policy.
_EXCLUSIVE_ABOVE_RE = re.compile(
    r"(?:above|over|exceed(?:s|ing)?|more than|greater than|in excess of)\s*$",
    re.IGNORECASE,
)
_LOOKBEHIND_WINDOW = 20

_LTV_KEYWORDS = ("ltv", "loan-to-value", "loan to value")
_DTI_KEYWORDS = ("dti", "debt-to-income", "debt to income")

_LTV_SECTION = "4.1 Loan-to-Value (LTV) Ratio"
_DTI_SECTION = "2.2 Debt-to-Income (DTI) Ratio"

# (high-inclusive-or-None, correct-outcome keywords, incorrect-outcome keywords).
# Mirrors domain/calculations.py's own `if value <= X` chains exactly — the
# first band whose `high` the value doesn't exceed wins, so a value sitting
# exactly on a threshold (43, 50, 80, 90, 97) lands in the same band the real
# calculator puts it in, not the band above it.
_LTV_BANDS: list[tuple[float | None, tuple[str, ...], tuple[str, ...]]] = [
    (
        80.0,
        ("no mortgage insurance", "standard pricing"),
        ("requires mortgage insurance", "not eligible"),
    ),
    (
        90.0,
        ("requires mortgage insurance", "mortgage insurance"),
        ("no mortgage insurance", "not eligible"),
    ),
    (97.0, ("compensating factor",), ("no mortgage insurance", "not eligible")),
    (
        None,
        ("not eligible", "exceeds the maximum", "exceeds the acceptable", "excessive"),
        ("standard pricing", "no mortgage insurance"),
    ),
]

_DTI_BANDS: list[tuple[float | None, tuple[str, ...], tuple[str, ...]]] = [
    (43.0, ("acceptable", "standard maximum", "meets"), ("compensating factor", "not eligible")),
    (50.0, ("compensating factor",), ("not eligible",)),
    (
        None,
        ("not eligible", "exceeds the maximum", "excessive", "excessively high"),
        ("acceptable",),
    ),
]


@dataclass
class CitationCheck:
    sentence: str
    section: str
    cited_value: float
    verdict: str  # "consistent" | "inconsistent" | "unrecognized"
    detail: str


def _band_for(value: float, bands) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    for high, correct, wrong in bands:
        if high is None or value <= high:
            return correct, wrong
    return None  # unreachable: the last band always has high=None


def check_citation_accuracy(claim_text: str) -> list[CitationCheck]:
    """Check every LTV/DTI percentage mention in `claim_text` against the
    policy's numeric bands. Returns one `CitationCheck` per recognized
    percentage mention; sentences with no LTV/DTI percentage produce none.
    """

    results: list[CitationCheck] = []
    for sentence in re.split(r"(?<=[.!?])\s+", claim_text):
        sentence_lower = sentence.lower()
        for m in _PERCENT_RE.finditer(sentence):
            value = float(m.group(1))
            if any(k in sentence_lower for k in _LTV_KEYWORDS):
                section, bands = _LTV_SECTION, _LTV_BANDS
            elif any(k in sentence_lower for k in _DTI_KEYWORDS):
                section, bands = _DTI_SECTION, _DTI_BANDS
            else:
                continue

            lookbehind = sentence[max(0, m.start() - _LOOKBEHIND_WINDOW) : m.start()]
            is_exclusive_above = bool(_EXCLUSIVE_ABOVE_RE.search(lookbehind))
            banding_value = value + 1e-9 if is_exclusive_above else value

            band = _band_for(banding_value, bands)
            if band is None:
                continue
            correct_kw, wrong_kw = band

            if any(k in sentence_lower for k in wrong_kw):
                verdict, detail = (
                    "inconsistent",
                    f"{value}% falls in a band where {section} states the opposite outcome.",
                )
            elif any(k in sentence_lower for k in correct_kw):
                verdict, detail = (
                    "consistent",
                    f"{value}% is correctly attributed to {section}'s band.",
                )
            else:
                verdict, detail = (
                    "unrecognized",
                    "Cites a banded percentage but doesn't state a recognizable outcome.",
                )

            results.append(
                CitationCheck(
                    sentence=sentence.strip(),
                    section=section,
                    cited_value=value,
                    verdict=verdict,
                    detail=detail,
                )
            )
    return results
