"""Fair-lending guardrail: a deterministic gate, not an LLM opinion.

An LLM can be asked to "avoid mentioning protected characteristics" and will
mostly comply — but "mostly" is not a compliance posture for ECOA/Fair
Lending. This module is a plain substring/regex scanner that runs on every
agent's output regardless of what the model was told to do, so a prompt
regression or a jailbroken policy document can't silently remove the check.
An LLM-as-judge pass (see agents/critic.py) is a *second*, complementary
layer on top of this — never a replacement for it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

PROTECTED_TERMS = (
    "race",
    "color",
    "religion",
    "national origin",
    "ethnicity",
    "sex",
    "marital status",
    "age",
    "gender",
    "disability",
    "familial status",
    "sexual orientation",
    "immigration status",
    "citizenship",
)

# Matched as a prefix (no trailing word boundary) so both "pregnant" and
# "pregnancy" are caught by a single entry.
PROTECTED_TERM_PREFIXES = ("pregnan",)

_GEOGRAPHIC_TERMS = ("neighborhood", "zip code", "area", "district", "community")

_WORD_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


class BiasFlag(BaseModel):
    code: str
    detail: str


def _pattern_for(term: str, *, prefix_only: bool = False) -> re.Pattern[str]:
    if term not in _WORD_BOUNDARY_CACHE:
        suffix = "" if prefix_only else r"\b"
        _WORD_BOUNDARY_CACHE[term] = re.compile(rf"\b{re.escape(term)}{suffix}", re.IGNORECASE)
    return _WORD_BOUNDARY_CACHE[term]


def scan_for_bias_signals(analysis_text: str, applicant_data: dict) -> list[BiasFlag]:
    """Scan a single agent's free-text output for fair-lending red flags."""

    flags: list[BiasFlag] = []
    lowered = analysis_text.lower()

    for term in PROTECTED_TERMS:
        if _pattern_for(term).search(lowered):
            flags.append(
                BiasFlag(
                    code="protected_characteristic_mentioned",
                    detail=f"Analysis references a protected characteristic: '{term}'",
                )
            )
    for term in PROTECTED_TERM_PREFIXES:
        if _pattern_for(term, prefix_only=True).search(lowered):
            flags.append(
                BiasFlag(
                    code="protected_characteristic_mentioned",
                    detail=f"Analysis references a protected characteristic: '{term}'",
                )
            )

    has_zip = "zip" in applicant_data or "zipcode" in applicant_data or "zip_code" in applicant_data
    if has_zip and any(term in lowered for term in _GEOGRAPHIC_TERMS):
        flags.append(
            BiasFlag(
                code="potential_geographic_proxy",
                detail=(
                    "Geographic/neighborhood language alongside zip data — "
                    "review for redlining proxy risk"
                ),
            )
        )

    return flags


def scan_many(analyses: dict[str, str | None], applicant_data: dict) -> list[BiasFlag]:
    """Run the scanner across every specialist's output for a case."""

    flags: list[BiasFlag] = []
    for text in analyses.values():
        if text:
            flags.extend(scan_for_bias_signals(text, applicant_data))
    return flags
