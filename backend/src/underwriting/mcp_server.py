"""MCP server: the same deterministic tools and policy retrieval the
LangGraph agents use, reachable by any MCP client — not just this project's
own graph.

Every calculation here is the identical function `agents/*.py` calls
directly in-process; this module adds no new logic, only a second transport
for it. See docs/adr/0008-mcp-tool-exposure.md for why that separation is
the point: the deterministic layer was already framework-agnostic pure
Python, so exposing it over MCP costs nothing but thin wrappers, and any
MCP-speaking agent (Claude Desktop, another LangGraph app, a completely
different framework) gets audit-grade DTI/LTV/reserve math instead of
asking its own model to do arithmetic.

Run standalone:
    uv run python -m underwriting.mcp_server

Or point an MCP client's config at:
    { "command": "uv", "args": ["run", "--project", "<path-to-backend>",
      "python", "-m", "underwriting.mcp_server"] }
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from underwriting.domain import calculations as calc
from underwriting.rag.policy_store import get_policy_store

mcp = MCPServer(
    name="underwriting-tools",
    instructions=(
        "Deterministic mortgage underwriting calculators (DTI, LTV, reserves, "
        "down-payment adequacy, credit tier, large-deposit flagging) and "
        "underwriting-policy retrieval. Every number is computed in plain "
        "Python — never ask a model to recompute one of these; call the tool."
    ),
)


@mcp.tool()
def calculate_dti_ratio(monthly_debt: float, monthly_income: float) -> dict:
    """Debt-to-income ratio: total monthly debt (incl. the proposed mortgage
    payment) divided by gross monthly income. Bands: <=43% acceptable,
    <=50% high, >50% excessive."""
    return calc.calculate_dti_ratio(monthly_debt, monthly_income).model_dump()


@mcp.tool()
def calculate_ltv_ratio(loan_amount: float, property_value: float) -> dict:
    """Loan-to-value ratio: loan amount divided by appraised property value.
    Bands: <=80% acceptable, <=90% elevated, <=97% high, >97% excessive."""
    return calc.calculate_ltv_ratio(loan_amount, property_value).model_dump()


@mcp.tool()
def calculate_down_payment_adequacy(liquid_assets: float, down_payment_required: float) -> dict:
    """Whether an applicant's liquid assets actually cover the required down
    payment — a distinct check from reserves, which must be computed on
    what's left *after* the down payment, not gross liquid assets."""
    return calc.calculate_down_payment_adequacy(liquid_assets, down_payment_required).model_dump()


@mcp.tool()
def calculate_reserves(
    liquid_assets: float, monthly_payment: float, required_months: int = 2
) -> dict:
    """Post-closing reserve coverage in months: liquid assets divided by the
    monthly PITI payment, compared against a required minimum (default 2)."""
    return calc.calculate_reserves(liquid_assets, monthly_payment, required_months).model_dump()


@mcp.tool()
def calculate_housing_expense_ratio(monthly_payment: float, monthly_income: float) -> dict:
    """Front-end (housing expense) ratio: proposed monthly payment divided by
    gross monthly income. Bands: <=28% acceptable, <=35% elevated, >35% high."""
    return calc.calculate_housing_expense_ratio(monthly_payment, monthly_income).model_dump()


@mcp.tool()
def check_credit_score_policy(credit_score: int) -> dict:
    """Credit score tier and pricing note: excellent (740+), very_good (700+),
    good (660+), fair (620+), below_minimum (<620, does not meet conventional
    loan requirements)."""
    return calc.check_credit_score_policy(credit_score).model_dump()


@mcp.tool()
def find_large_deposits(deposits: list[dict], monthly_income: float) -> dict:
    """Flag deposits at or above 25% of monthly income as requiring sourcing
    documentation. `deposits` is a list of {"amount": number, "date": string}."""
    return calc.find_large_deposits(deposits, monthly_income).model_dump()


@mcp.tool()
def calculate_total_debt_obligations(debts: dict[str, float], proposed_payment: float) -> dict:
    """Sum existing monthly debts plus the proposed mortgage payment, with a
    per-debt breakdown. `debts` is a mapping of debt name to monthly amount."""
    return calc.calculate_total_debt_obligations(debts, proposed_payment).model_dump()


@mcp.tool()
def retrieve_underwriting_policy(query: str, k: int = 6) -> str:
    """Semantic search over the underwriting policy manual (credit, income,
    asset, collateral, and Fair Lending sections). Returns the top-k matching
    policy excerpts, labelled by section."""
    return get_policy_store().retrieve(query, k=k)


if __name__ == "__main__":
    mcp.run()
