import pytest

from underwriting.domain.calculations import (
    CreditTier,
    RatioStatus,
    calculate_dti_ratio,
    calculate_housing_expense_ratio,
    calculate_ltv_ratio,
    calculate_reserves,
    calculate_total_debt_obligations,
    check_credit_score_policy,
    find_large_deposits,
)


def test_dti_acceptable():
    result = calculate_dti_ratio(monthly_debt=1500, monthly_income=6000)
    assert result.dti_ratio == 25.0
    assert result.status == RatioStatus.ACCEPTABLE


def test_dti_excessive():
    result = calculate_dti_ratio(monthly_debt=3600, monthly_income=6000)
    assert result.status == RatioStatus.EXCESSIVE


def test_dti_rejects_zero_income():
    with pytest.raises(ValueError):
        calculate_dti_ratio(monthly_debt=100, monthly_income=0)


@pytest.mark.parametrize(
    "loan_amount,property_value,expected_status",
    [
        (240_000, 300_000, RatioStatus.ACCEPTABLE),  # 80%
        (270_000, 300_000, RatioStatus.ELEVATED),  # 90%
        (288_000, 300_000, RatioStatus.HIGH),  # 96%
        (300_000, 300_000, RatioStatus.EXCESSIVE),  # 100%
    ],
)
def test_ltv_bands(loan_amount, property_value, expected_status):
    result = calculate_ltv_ratio(loan_amount=loan_amount, property_value=property_value)
    assert result.status == expected_status


def test_reserves_adequate_vs_insufficient():
    adequate = calculate_reserves(liquid_assets=10_000, monthly_payment=2_000, required_months=2)
    assert adequate.adequate is True
    assert adequate.months_coverage == 5.0

    insufficient = calculate_reserves(
        liquid_assets=1_000, monthly_payment=2_000, required_months=2
    )
    assert insufficient.adequate is False
    assert insufficient.surplus_deficit == -3_000.0


def test_housing_expense_ratio_bands():
    ok = calculate_housing_expense_ratio(monthly_payment=1_000, monthly_income=5_000)
    assert ok.status == RatioStatus.ACCEPTABLE

    high = calculate_housing_expense_ratio(monthly_payment=2_000, monthly_income=5_000)
    assert high.status == RatioStatus.HIGH


@pytest.mark.parametrize(
    "score,tier",
    [
        (760, CreditTier.EXCELLENT),
        (710, CreditTier.VERY_GOOD),
        (670, CreditTier.GOOD),
        (630, CreditTier.FAIR),
        (580, CreditTier.BELOW_MINIMUM),
    ],
)
def test_credit_score_tiers(score, tier):
    assert check_credit_score_policy(score).tier == tier


def test_large_deposits_flags_only_above_threshold():
    deposits = [
        {"amount": 200, "date": "2026-01-01"},
        {"amount": 5_000, "date": "2026-01-15"},
    ]
    result = find_large_deposits(deposits, monthly_income=8_000)  # threshold = 2000
    assert result.any_flagged is True
    assert len(result.deposits) == 1
    assert result.deposits[0].amount == 5_000


def test_total_debt_obligations_sums_correctly():
    result = calculate_total_debt_obligations(
        debts={"car_loan": 450, "student_loan": 300}, proposed_payment=1_800
    )
    assert result.current_debt == 750
    assert result.total_obligation == 2_550
