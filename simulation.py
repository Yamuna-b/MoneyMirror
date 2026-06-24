"""
Pure simulation logic — no FastAPI / HTTP. Uses config thresholds for risk bands.
"""
from __future__ import annotations

from typing import Any

from config import get_settings


def build_profile_dict(p: Any) -> dict:
    """Build internal profile dict from SQLAlchemy FinancialProfile or compatible object."""
    emis = p.emis or []
    total_emi = sum(e.get("amount", 0) for e in emis)
    fixed = p.rent + p.utilities + p.insurance + p.subscriptions
    variable = p.food + p.transport + p.dining + p.shopping + p.misc
    total_income = p.income + p.other_income
    total_expenses = fixed + variable + total_emi
    return {
        "income": total_income,
        "savings": p.savings,
        "min_balance": p.min_balance,
        "rent": p.rent,
        "fixed": fixed,
        "variable": variable,
        "total_emi": total_emi,
        "total_expenses": total_expenses,
        "horizon": p.horizon_months,
        "safety_target": p.safety_target,
        "emis": emis,
        "expense_breakdown": {
            "Rent/PG": p.rent,
            "Food": p.food,
            "EMIs": total_emi,
            "Transport": p.transport,
            "Dining": p.dining,
            "Shopping": p.shopping,
            "Utilities/Subs": p.utilities + p.insurance + p.subscriptions,
            "Misc": p.misc,
        },
    }


def simulate_timeline(profile: dict, scenario: dict | None, months: int) -> list[float]:
    balances = [profile["savings"]]
    for t in range(months):
        prev = balances[-1]
        inc = profile["income"]
        exp = profile["total_expenses"]
        m = t + 1

        if scenario:
            st = scenario.get("scenario_type")
            par = scenario.get("params", {})
            s = int(par.get("start", 1))
            dur = int(par.get("dur", 3))

            if st == "salary-cut" and s <= m <= s + dur - 1:
                inc *= 1 - float(par.get("cut", 20)) / 100
            elif st == "job-loss" and s <= m <= s + dur - 1:
                inc = 0
            elif st == "new-emi" and s <= m <= s + int(par.get("dur", 12)) - 1:
                exp += float(par.get("amount", 5000))
            elif st == "rent-hike" and m >= s:
                amt = par.get("amount")
                if amt is not None and float(amt) > 0:
                    exp += float(amt)
                else:
                    exp += profile["rent"] * float(par.get("pct", 10)) / 100
            elif st == "lifestyle-up" and m >= s:
                exp += profile["variable"] * float(par.get("pct", 20)) / 100
            elif st == "medical" and m == int(par.get("month", 1)):
                exp += float(par.get("amount", 50000))

        balances.append(prev + inc - exp)
    return balances


def calc_metrics(profile: dict, balances: list[float]) -> dict:
    cfg = get_settings()
    months = len(balances) - 1
    monthly_cf = profile["income"] - profile["total_expenses"]
    ef_ratio = profile["savings"] / profile["total_expenses"] if profile["total_expenses"] > 0 else 0
    dti = profile["total_emi"] / profile["income"] if profile["income"] > 0 else 0
    sav_ratio = max(0, monthly_cf) / profile["income"] if profile["income"] > 0 else 0

    runway = 0
    first_risk = None
    for i in range(1, len(balances)):
        if balances[i] >= profile["min_balance"]:
            runway = i
        elif first_risk is None:
            first_risk = i
            break
    if all(b >= profile["min_balance"] for b in balances[1:]):
        runway = months

    st = profile.get("safety_target", cfg.safety_target_months)
    if ef_ratio < cfg.ef_months_high or runway < cfg.runway_months_high or dti > cfg.dti_high:
        risk = "high"
    elif ef_ratio < cfg.ef_months_caution or runway < cfg.runway_months_caution or dti > cfg.dti_caution:
        risk = "caution"
    else:
        risk = "comfortable"

    safety_gap_months = st - ef_ratio
    safety_gap_amount = max(0, safety_gap_months * profile["total_expenses"])

    return {
        "emergency_fund_ratio": round(ef_ratio, 2),
        "dti": round(dti, 3),
        "savings_ratio": round(sav_ratio, 3),
        "runway": runway,
        "first_risk_month": first_risk,
        "risk_level": risk,
        "monthly_cashflow": round(monthly_cf),
        "safety_target": st,
        "safety_gap_months": round(safety_gap_months, 2),
        "safety_gap_amount": round(safety_gap_amount),
    }


def generate_insights(profile: dict, base_metrics: dict, scenario_results: list) -> list[str]:
    cfg = get_settings()
    lines = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    m = base_metrics

    if m["monthly_cashflow"] < 0:
        lines.append(
            f"Your current expenses exceed income by {fmt(-m['monthly_cashflow'])}/month. "
            f"Your savings will be depleted in approximately {m['runway']} months."
        )
    else:
        lines.append(
            f"With your current plan, you have a safety runway of {m['runway']} month{'s' if m['runway'] != 1 else ''} "
            f"and are saving {fmt(m['monthly_cashflow'])}/month."
        )

    if m["safety_gap_amount"] > 0:
        lines.append(
            f"Your safety target is {profile.get('safety_target', cfg.safety_target_months):.1f} months of expenses. "
            f"You are at {m['emergency_fund_ratio']:.1f} months — short by {fmt(m['safety_gap_amount'])}."
        )

    if m["dti"] > cfg.dti_high:
        lines.append(
            f"Your EMIs consume {m['dti'] * 100:.0f}% of income — above the {cfg.dti_high * 100:.0f}% caution line. "
            "Avoid new loans until you clear one."
        )
    elif m["dti"] > cfg.dti_caution:
        lines.append(
            f"Your EMI ratio is {m['dti'] * 100:.0f}%. Manageable, but new EMIs would add pressure."
        )

    if m["emergency_fund_ratio"] < cfg.ef_months_recommended_min:
        lines.append(
            f"Your emergency fund covers {m['emergency_fund_ratio']:.1f} months of expenses. "
            f"Aim for at least {cfg.ef_months_recommended_min:.0f} months."
        )

    names = {
        "salary-cut": "A salary cut",
        "job-loss": "Job loss",
        "new-emi": "Adding this EMI",
        "rent-hike": "A rent hike",
        "lifestyle-up": "A lifestyle upgrade",
    }
    base_rw = m["runway"]
    for sr in scenario_results:
        diff = sr["metrics"]["runway"] - base_rw
        label = names.get(sr["scenario_type"], sr["name"])
        if diff < -1:
            lines.append(
                f"{label} would reduce your safety runway from {base_rw} to {sr['metrics']['runway']} "
                f"month{'s' if sr['metrics']['runway'] != 1 else ''}."
            )
        elif diff >= 0:
            lines.append(f"{label} (as configured) has a manageable impact on your plan.")
    return lines


def generate_baseline_explanation(profile: dict, metrics: dict) -> str:
    inc = profile["income"]
    rent_pct = (profile["rent"] / inc * 100) if inc > 0 else 0
    emi_pct = (profile["total_emi"] / inc * 100) if inc > 0 else 0
    rw = metrics["runway"]
    risk = metrics["risk_level"]
    risk_word = {"high": "High risk", "caution": "Caution", "comfortable": "Comfortable"}[risk]
    parts = [
        f"Your baseline plan keeps a safety runway of about {rw} month{'s' if rw != 1 else ''} "
        "before your balance would dip below your comfort threshold.",
        f"EMIs are roughly {emi_pct:.0f}% of income and rent about {rent_pct:.0f}%.",
        f"Overall risk label: {risk_word}.",
    ]
    if metrics["monthly_cashflow"] < 0:
        parts.append(
            "You are spending more than you earn each month on this profile — consider trimming variable costs or fixed commitments."
        )
    return " ".join(parts)


def generate_scenario_explanation(
    profile: dict,
    scenario_type: str,
    params: dict,
    scen_metrics: dict,
    base_metrics: dict,
) -> str:
    rw0 = base_metrics["runway"]
    rw1 = scen_metrics["runway"]
    delta = rw1 - rw0
    inc = profile["income"]
    emi_pct = (profile["total_emi"] / inc * 100) if inc > 0 else 0
    rent_pct = (profile["rent"] / inc * 100) if inc > 0 else 0
    lines = []
    if delta < -0.5:
        lines.append(
            f"Compared to baseline, this scenario cuts your safety runway from {rw0} to {rw1} "
            f"month{'s' if rw1 != 1 else ''}."
        )
    elif delta > 0.5:
        lines.append(f"Under this scenario your runway improves from {rw0} to {rw1} months vs baseline.")
    else:
        lines.append(f"Safety runway is similar to baseline ({rw1} months), with a small change from {rw0} months.")
    lines.append(
        f"EMIs use about {emi_pct:.0f}% of income and rent about {rent_pct:.0f}% — fixed costs drive much of the risk."
    )
    st = scenario_type
    if st == "salary-cut":
        lines.append(f"A {params.get('cut', 0):.0f}% salary cut for {int(params.get('dur', 0))} months is the main stress here.")
    elif st == "job-loss":
        lines.append(f"No income for {int(params.get('dur', 0))} months is the dominant factor.")
    elif st == "new-emi":
        lines.append(f"The new EMI of ₹{int(params.get('amount', 0)):,}/month adds steady pressure to cash flow.")
    elif st == "rent-hike":
        if params.get("amount") is not None and float(params.get("amount", 0) or 0) > 0:
            lines.append(f"A fixed +₹{int(params['amount']):,}/month rent increase raises fixed outgo.")
        else:
            lines.append(f"A {params.get('pct', 0):.0f}% rent increase raises fixed outgo each month.")
    elif st == "lifestyle-up":
        lines.append(f"Higher variable spending ({params.get('pct', 0):.0f}%) compounds over the horizon.")
    risk = scen_metrics["risk_level"]
    lines.append(f"Risk vs this scenario: {'High risk' if risk == 'high' else 'Caution' if risk == 'caution' else 'Comfortable'}.")
    return " ".join(lines)


def generate_advice(profile: dict, metrics: dict) -> list[dict]:
    cfg = get_settings()
    advice = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    if metrics["dti"] > cfg.dti_high:
        advice.append(
            {
                "icon": "🚨",
                "title": "EMI load is critical",
                "desc": f"EMIs take {metrics['dti'] * 100:.0f}% of income. Don't add new loans. Focus on clearing one EMI.",
                "type": "bad",
            }
        )
    elif metrics["dti"] > cfg.dti_caution:
        advice.append(
            {
                "icon": "⚠️",
                "title": "Watch your EMI ratio",
                "desc": f"At {metrics['dti'] * 100:.0f}%, EMIs are manageable but leave little room.",
                "type": "warn",
            }
        )
    if metrics["emergency_fund_ratio"] < cfg.ef_months_recommended_min:
        gap = (cfg.ef_months_recommended_min - metrics["emergency_fund_ratio"]) * profile["total_expenses"]
        advice.append(
            {
                "icon": "🏦",
                "title": "Build your emergency fund",
                "desc": f"At {metrics['emergency_fund_ratio']:.1f}× coverage, you need about {fmt(gap)} more to reach {cfg.ef_months_recommended_min:.0f} months of expenses.",
                "type": "bad" if metrics["emergency_fund_ratio"] < 1 else "warn",
            }
        )
    if metrics["risk_level"] == "comfortable":
        advice.append(
            {
                "icon": "📈",
                "title": "Solid buffer",
                "desc": "Your plan looks sustainable at this horizon. Consider investing the surplus per your goals.",
                "type": "good",
            }
        )
    return advice[:3]
