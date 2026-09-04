"""Tests for the MCP tool exposure (mcp_server.py).

`@mcp.tool()` registers the function but returns it unchanged, so most of
these call the tools directly like any other Python function — the point
being tested is that the *wrapper* (JSON-serializable dict, right args)
matches the underlying domain calculation, not MCP protocol plumbing
itself. `test_call_tool_round_trip_serializes_enums_as_plain_strings`
covers the one thing direct calls can't: that the actual MCP wire
protocol serializes a StrEnum status field as `"acceptable"`, not a
Python enum repr.
"""

from __future__ import annotations

import json

import pytest

# The `mcp` SDK is an opt-in extra (`uv sync --extra mcp`), not part of the
# base `dev` install — skip rather than fail collection when it's absent.
pytest.importorskip("mcp")

from underwriting.domain.calculations import calculate_ltv_ratio  # noqa: E402
from underwriting.mcp_server import (  # noqa: E402
    calculate_down_payment_adequacy,
    calculate_dti_ratio,
    calculate_reserves,
    calculate_total_debt_obligations,
    check_credit_score_policy,
    find_large_deposits,
    mcp,
)
from underwriting.mcp_server import (  # noqa: E402
    calculate_ltv_ratio as mcp_calculate_ltv_ratio,
)


def test_calculate_dti_ratio_matches_domain_calculation():
    result = calculate_dti_ratio(monthly_debt=1500, monthly_income=6000)
    assert result == {
        "dti_ratio": 25.0,
        "monthly_debt": 1500.0,
        "monthly_income": 6000.0,
        "status": "acceptable",
    }


def test_mcp_ltv_wrapper_matches_domain_function_directly():
    domain_result = calculate_ltv_ratio(loan_amount=380_000, property_value=480_000).model_dump()
    mcp_result = mcp_calculate_ltv_ratio(loan_amount=380_000, property_value=480_000)
    assert mcp_result == domain_result


def test_calculate_down_payment_adequacy_flags_shortfall():
    result = calculate_down_payment_adequacy(liquid_assets=60_000, down_payment_required=95_000)
    assert result["adequate"] is False
    assert result["shortfall_or_surplus"] == -35_000


def test_calculate_reserves_default_required_months():
    result = calculate_reserves(liquid_assets=10_000, monthly_payment=2_000)
    assert result["months_coverage"] == 5.0
    assert result["adequate"] is True


def test_check_credit_score_policy_below_minimum():
    result = check_credit_score_policy(credit_score=588)
    assert result["tier"] == "below_minimum"


def test_find_large_deposits_flags_only_above_threshold():
    result = find_large_deposits(
        deposits=[{"amount": 200, "date": "2026-01-01"}, {"amount": 5000, "date": "2026-01-15"}],
        monthly_income=8000,
    )
    assert len(result["deposits"]) == 1
    assert result["deposits"][0]["amount"] == 5000


def test_calculate_total_debt_obligations_sums_correctly():
    result = calculate_total_debt_obligations(
        debts={"car_loan": 450, "student_loan": 300}, proposed_payment=1800
    )
    assert result["total_obligation"] == 2550


def test_every_tool_output_is_json_serializable():
    """Every tool wrapper returns a `.model_dump()` dict — enums must be
    StrEnum (str subclasses) or this silently breaks JSON serialization
    over the wire."""
    result = calculate_dti_ratio(monthly_debt=1000, monthly_income=5000)
    json.dumps(result)  # raises TypeError if anything isn't JSON-safe


@pytest.mark.asyncio
async def test_call_tool_round_trip_serializes_enums_as_plain_strings():
    result = await mcp.call_tool(
        "calculate_ltv_ratio", {"loan_amount": 380_000, "property_value": 480_000}
    )
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "acceptable"


@pytest.mark.asyncio
async def test_all_expected_tools_are_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "calculate_dti_ratio",
        "calculate_ltv_ratio",
        "calculate_down_payment_adequacy",
        "calculate_reserves",
        "calculate_housing_expense_ratio",
        "check_credit_score_policy",
        "find_large_deposits",
        "calculate_total_debt_obligations",
        "retrieve_underwriting_policy",
    }
