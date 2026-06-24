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
    balances = simulate_timeline(prof, None, 12)
    metrics = calc_metrics(prof, balances)

    assert prof["income"] == 52000
    assert prof["total_expenses"] == 37800
    assert metrics["monthly_cashflow"] == 14200
    assert metrics["emergency_fund_ratio"] == pytest.approx(2.25)
    assert metrics["dti"] == pytest.approx(0.121, abs=0.001)
    assert metrics["runway"] == 12
    assert balances[1] == pytest.approx(85000 + 14200)


def test_job_loss_reduces_runway():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "job-loss", "params": {"dur": 3, "start": 1}}
    balances = simulate_timeline(prof, scenario, 12)
    metrics = calc_metrics(prof, balances)

    assert metrics["runway"] == 2
    assert metrics["first_risk_month"] == 3


def test_rent_hike_fixed_amount():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "rent-hike", "params": {"amount": 2000, "start": 1}}
    months = 3
    balances = simulate_timeline(prof, scenario, months)
    baseline = simulate_timeline(prof, None, months)

    assert balances[-1] == pytest.approx(baseline[-1] - 2000 * months)


def test_rent_hike_percentage():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "rent-hike", "params": {"pct": 10, "start": 1}}
    months = 2
    balances = simulate_timeline(prof, scenario, months)
    baseline = simulate_timeline(prof, None, months)
    monthly_extra = prof["rent"] * 0.10

    assert balances[-1] == pytest.approx(baseline[-1] - monthly_extra * months)


def test_medical_one_time_expense():
    prof = build_profile_dict(_profile())
    scenario = {"scenario_type": "medical", "params": {"amount": 50000, "month": 2}}
    balances = simulate_timeline(prof, scenario, 3)
    baseline = simulate_timeline(prof, None, 3)

    assert balances[2] == pytest.approx(baseline[2] - 50000)
    assert balances[3] == pytest.approx(baseline[3] - 50000)


def test_zero_income_metrics():
    prof = build_profile_dict(_profile(income=0, other_income=0, savings=50000, emis=[]))
    balances = simulate_timeline(prof, None, 12)
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
