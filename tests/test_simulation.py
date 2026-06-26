"""Tests for simulation engine and auth validation."""
from __future__ import annotations

import types

import pytest

from auth_utils import validate_password
from simulation import SCENARIO_TYPES, build_profile_dict, calc_metrics, simulate_timeline


def _profile(**kwargs):
    defaults = dict(
        income=52000,
        other_income=0,
        savings=85000,
        min_balance=8000,
        safety_target=3.0,
        horizon_months=12,
        rent=12000,
        utilities=1800,
        insurance=1200,
        subscriptions=700,
        food=5500,
        transport=2800,
        dining=3500,
        shopping=2500,
        misc=1500,
        emis=[{"name": "Loan", "amount": 4200}, {"name": "Phone", "amount": 2100}],
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_yamuna_baseline_metrics():
    prof = build_profile_dict(_profile())
    balances, _ = simulate_timeline(prof, None, 12, "moderate")
    metrics = calc_metrics(prof, balances)

    assert prof["income"] == 52000
    assert prof["total_expenses"] == 37800
    assert metrics["monthly_cashflow"] == 14200
    assert metrics["emergency_fund_ratio"] == pytest.approx(2.25)
    assert metrics["dti"] == pytest.approx(0.121, abs=0.001)
    assert metrics["runway"] == 12
    # Account for 8% annual (0.667% monthly) interest growth on initial savings (85000)
    expected_growth = 85000 * (0.08 / 12)
    assert balances[1] == pytest.approx(85000 + expected_growth + 14200, abs=1)


def test_job_loss_reduces_runway():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "job-loss", "params": {"dur": 3, "start": 1}}
    balances, _ = simulate_timeline(prof, scenario, 12, "moderate")
    metrics = calc_metrics(prof, balances)

    assert metrics["runway"] == 2
    assert metrics["first_risk_month"] == 3


def test_rent_hike_fixed_amount():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "rent-hike", "params": {"amount": 2000, "start": 1}}
    months = 3
    balances, _ = simulate_timeline(prof, scenario, months, "moderate")
    baseline, _ = simulate_timeline(prof, None, months, "moderate")

    # Due to compound interest at 8% annual, the difference is compounded:
    # Month 1 diff: 2000
    # Month 2 diff: 2000 + 2000 * (1 + 0.08/12) = 4013.33
    # Month 3 diff: 2000 + 4013.33 * (1 + 0.08/12) = 6040.09
    assert baseline[-1] - balances[-1] == pytest.approx(6040.09, abs=0.1)


def test_rent_hike_percentage():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "rent-hike", "params": {"pct": 10, "start": 1}}
    months = 2
    balances, _ = simulate_timeline(prof, scenario, months, "moderate")
    baseline, _ = simulate_timeline(prof, None, months, "moderate")
    monthly_extra = prof["rent"] * 0.10

    # Month 1 diff: 1200
    # Month 2 diff: 1200 + 1200 * (1 + 0.08/12) = 2408
    assert baseline[-1] - balances[-1] == pytest.approx(2408, abs=0.1)


def test_medical_one_time_expense():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "medical", "params": {"amount": 50000, "month": 2}}
    balances, _ = simulate_timeline(prof, scenario, 3, "moderate")
    baseline, _ = simulate_timeline(prof, None, 3, "moderate")

    # Hit in Month 2: Month 2 diff is 50000.
    assert baseline[2] - balances[2] == pytest.approx(50000)
    # Month 3 diff includes Month 2 interest lost: 50000 * (1 + 0.08/12) = 50333.33
    assert baseline[3] - balances[3] == pytest.approx(50333.33, abs=0.1)


def test_zero_income_metrics():
    prof = build_profile_dict(_profile(income=0, other_income=0, savings=50000, emis=[]))
    balances, _ = simulate_timeline(prof, None, 12, "moderate")
    metrics = calc_metrics(prof, balances)

    assert metrics["dti"] == 0
    assert metrics["savings_ratio"] == 0


def test_scenario_types_complete():
    assert "medical" in SCENARIO_TYPES
    assert len(SCENARIO_TYPES) == 6


@pytest.mark.parametrize(
    "password,expected",
    [
        ("short", "Password must be at least 6 characters."),
        ("123456", "Password must contain at least one letter."),
        ("abcdef", "Password must contain at least one number."),
        ("Valid1", None),
    ],
)
def test_validate_password(password, expected):
    assert validate_password(password) == expected


def test_simulation_modes_growth():
    prof = build_profile_dict(_profile(
        income=40000, rent=10000, food=5000, transport=2000, dining=2000, shopping=2000, misc=1000,
        utilities=0, insurance=0, subscriptions=0, emis=[], savings=100000
    ))
    # Variable costs are: 5000 + 2000 + 2000 + 2000 + 1000 = 12000
    # Moderate: variable costs = 12000, total costs = 22000. Surplus = 40000 - 22000 = 18000. Interest = 100000 * 0.08 / 12 = 667
    bals_mod, _ = simulate_timeline(prof, None, 1, "moderate")
    assert bals_mod[1] == pytest.approx(100000 + 18000 + (100000 * 0.08 / 12), abs=1)

    # Conservative: variable costs = 12000 * 1.10 = 13200, total = 23200. Surplus = 16800. Interest = 100000 * 0.04 / 12 = 333
    bals_con, _ = simulate_timeline(prof, None, 1, "conservative")
    assert bals_con[1] == pytest.approx(100000 + 16800 + (100000 * 0.04 / 12), abs=1)

    # Aggressive: variable costs = 12000 * 0.95 = 11400, total = 21400. Surplus = 18600. Interest = 100000 * 0.12 / 12 = 1000
    bals_agg, _ = simulate_timeline(prof, None, 1, "aggressive")
    assert bals_agg[1] == pytest.approx(100000 + 18600 + (100000 * 0.12 / 12), abs=1)


def test_goal_deduction():
    prof = build_profile_dict(_profile(savings=50000, min_balance=10000))
    goals = [
        {"id": 1, "name": "Laptop", "target_amount": 25000, "target_months": 2, "category": "gadget"},
        {"id": 2, "name": "Trip", "target_amount": 10000, "target_months": 5, "category": "travel"}
    ]
    # Under moderate baseline, income is 52000, expenses are 37800. Net surplus is 14200.
    # Month 1: 50000 + 50000*0.08/12 + 14200 = 64533
    # Month 2: 64533 + 64533*0.08/12 + 14200 = 79163
    # Maturing Laptop Goal: cost 25000. Since 79163 >= 25000 + 10000 (comfort balance), laptop is achieved and deducted.
    # Month 2 balance ends at 79163 - 25000 = 54163.
    bals, g_res = simulate_timeline(prof, None, 6, "moderate", goals)
    
    laptop = next(x for x in g_res if x["id"] == 1)
    assert laptop["status"] == "achieved"
    assert laptop["achieved_month"] == 2
    assert laptop["probability"] == 1.0
    assert bals[2] == pytest.approx(79163 - 25000, abs=10)
