"""Shared helpers used by every specialist agent node."""

from __future__ import annotations

import json

from pydantic import BaseModel


def render_metrics(**metrics: BaseModel) -> str:
    """Render deterministic calculation results as a labelled JSON block.

    Agents are told, in every prompt, to treat this block as ground truth and
    never recompute it themselves — see docs/adr/0001.
    """

    payload = {name: model.model_dump() for name, model in metrics.items()}
    return json.dumps(payload, indent=2)


NO_PROTECTED_CHARACTERISTICS_RULE = (
    "Do not reference or rely on race, color, religion, national origin, sex, "
    "marital status, age, gender, disability, or familial status. Base every "
    "conclusion only on the financial facts and calculated metrics provided."
)
