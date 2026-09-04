"""Deterministic underwriting calculations.

LLMs are unreliable at arithmetic and cannot be trusted to reproduce the same
number twice. Every figure that ends up in a decision memo — DTI, LTV,
reserve coverage — is computed here in plain Python and handed to the agents
as a fact, not asked of the model. Agents may explain a number; they never
compute one.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RatioStatus(StrEnum):
    ACCEPTABLE = "acceptable"
    ELEVATED = "elevated"
    HIGH = "high"
    EXCESSIVE = "excessive"


class DTIResult(BaseModel):
    dti_ratio: float
    monthly_debt: float
    monthly_income: float
    status: RatioStatus


class LTVResult(BaseModel):
    ltv_ratio: float
    loan_amount: float
    property_value: float
    status: RatioStatus


class ReservesResult(BaseModel):
    months_coverage: float
    liquid_assets: float
    required_amount: float
    surplus_deficit: float
    adequate: bool


class HousingRatioResult(BaseModel):
    housing_ratio: float
    monthly_payment: float
    monthly_income: float
    status: RatioStatus


class CreditTier(StrEnum):
    EXCELLENT = "excellent"
    VERY_GOOD = "very_good"
    GOOD = "good"
    FAIR = "fair"
    BELOW_MINIMUM = "below_minimum"


class CreditScoreResult(BaseModel):
    credit_score: int
    tier: CreditTier
    note: str


class LargeDeposit(BaseModel):
    amount: float
    date: str
    sourcing_required: bool = True


class LargeDepositsResult(BaseModel):
    threshold: float
    deposits: list[LargeDeposit] = Field(default_factory=list)

    @property
    def any_flagged(self) -> bool:
        return len(self.deposits) > 0


class DebtObligationsResult(BaseModel):
    current_debt: float
    proposed_payment: float
    total_obligation: float
    debt_breakdown: dict[str, float]


def calculate_dti_ratio(monthly_debt: float, monthly_income: float) -> DTIResult:
    if monthly_income <= 0:
        raise ValueError("monthly_income must be greater than 0")
    dti = (monthly_debt / monthly_income) * 100
    status = (
        RatioStatus.ACCEPTABLE
        if dti <= 43
        else RatioStatus.HIGH
        if dti <= 50
        else RatioStatus.EXCESSIVE
    )
    return DTIResult(
        dti_ratio=round(dti, 2),
        monthly_debt=round(monthly_debt, 2),
        monthly_income=round(monthly_income, 2),
        status=status,
    )


def calculate_ltv_ratio(loan_amount: float, property_value: float) -> LTVResult:
    if property_value <= 0:
        raise ValueError("property_value must be greater than 0")
    ltv = (loan_amount / property_value) * 100
    status = (
        RatioStatus.ACCEPTABLE
        if ltv <= 80
        else RatioStatus.ELEVATED
        if ltv <= 90
        else RatioStatus.HIGH
        if ltv <= 97
        else RatioStatus.EXCESSIVE
    )
    return LTVResult(
        ltv_ratio=round(ltv, 2),
        loan_amount=round(loan_amount, 2),
        property_value=round(property_value, 2),
        status=status,
    )


def calculate_reserves(
    liquid_assets: float, monthly_payment: float, required_months: int = 2
) -> ReservesResult:
    if monthly_payment <= 0:
        raise ValueError("monthly_payment must be greater than 0")
    months_coverage = liquid_assets / monthly_payment
    required_amount = monthly_payment * required_months
    return ReservesResult(
        months_coverage=round(months_coverage, 1),
        liquid_assets=round(liquid_assets, 2),
        required_amount=round(required_amount, 2),
        surplus_deficit=round(liquid_assets - required_amount, 2),
        adequate=months_coverage >= required_months,
    )


def calculate_housing_expense_ratio(
    monthly_payment: float, monthly_income: float
) -> HousingRatioResult:
    if monthly_income <= 0:
        raise ValueError("monthly_income must be greater than 0")
    ratio = (monthly_payment / monthly_income) * 100
    status = (
        RatioStatus.ACCEPTABLE
        if ratio <= 28
        else RatioStatus.ELEVATED
        if ratio <= 35
        else RatioStatus.HIGH
    )
    return HousingRatioResult(
        housing_ratio=round(ratio, 2),
        monthly_payment=round(monthly_payment, 2),
        monthly_income=round(monthly_income, 2),
        status=status,
    )


def check_credit_score_policy(credit_score: int) -> CreditScoreResult:
    if credit_score >= 740:
        tier, note = CreditTier.EXCELLENT, "Best rates available"
    elif credit_score >= 700:
        tier, note = CreditTier.VERY_GOOD, "Favorable rates"
    elif credit_score >= 660:
        tier, note = CreditTier.GOOD, "Standard rates"
    elif credit_score >= 620:
        tier, note = CreditTier.FAIR, "Higher rates, may require compensating factors"
    else:
        tier, note = CreditTier.BELOW_MINIMUM, "Does not meet conventional loan requirements"
    return CreditScoreResult(credit_score=credit_score, tier=tier, note=note)


def find_large_deposits(
    deposits: list[dict], monthly_income: float, threshold_pct: float = 0.25
) -> LargeDepositsResult:
    threshold = monthly_income * threshold_pct
    flagged = [
        LargeDeposit(amount=d.get("amount", 0), date=d.get("date", "unknown"))
        for d in deposits
        if d.get("amount", 0) >= threshold
    ]
    return LargeDepositsResult(threshold=round(threshold, 2), deposits=flagged)


def calculate_total_debt_obligations(
    debts: dict[str, float], proposed_payment: float
) -> DebtObligationsResult:
    current_debt = sum(debts.values())
    return DebtObligationsResult(
        current_debt=round(current_debt, 2),
        proposed_payment=round(proposed_payment, 2),
        total_obligation=round(current_debt + proposed_payment, 2),
        debt_breakdown={k: round(v, 2) for k, v in debts.items()},
    )
