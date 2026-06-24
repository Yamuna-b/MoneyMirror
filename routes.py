"""HTTP routes — thin handlers; business logic lives in simulation.py."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth_utils import create_token, hash_password, validate_password, verify_password
from config import get_settings
from database import FinancialProfile, Scenario, SimulationRun, User
from deps import get_current_user, get_db
from schemas import ProfileIn, RegisterRequest, ScenarioIn, SimulateRequest, TokenResponse
from simulation import (
    SCENARIO_TYPES,
    build_profile_dict,
    calc_metrics,
    generate_advice,
    generate_baseline_explanation,
    generate_insights,
    generate_scenario_explanation,
    simulate_timeline,
)

router = APIRouter()


def _scenario_to_dict(s: Scenario) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "scenario_type": s.scenario_type,
        "params": s.params or {},
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _merge_profile_in(data: ProfileIn) -> dict:
    """Apply opinionated defaults when client sends 0 / omitted."""
    s = get_settings()
    raw = data.model_dump()
    if not raw.get("horizon_months"):
        raw["horizon_months"] = s.default_horizon_months
    if not raw.get("safety_target"):
        raw["safety_target"] = s.safety_target_months
    if not raw.get("min_balance"):
        raw["min_balance"] = s.default_min_balance
    return raw


def _validate_scenario(data: ScenarioIn) -> None:
    if not data.name.strip():
        raise HTTPException(400, "Scenario name cannot be empty.")
    if data.scenario_type not in SCENARIO_TYPES:
        raise HTTPException(400, f"Unknown scenario type. Allowed: {', '.join(sorted(SCENARIO_TYPES))}.")


def _month_labels(months: int) -> list[str]:
    today = datetime.utcnow()
    return ["Now"] + [
        (today.replace(day=1) + timedelta(days=32 * i)).strftime("%b '%y") for i in range(1, months + 1)
    ]


def run_simulation_for_profile(p: FinancialProfile, scenario_rows: list[Scenario]) -> dict:
    """Build full simulation payload from a profile and scenario ORM rows."""
    prof = build_profile_dict(p)
    months = p.horizon_months
    base_balances = simulate_timeline(prof, None, months)
    base_metrics = calc_metrics(prof, base_balances)

    scenario_results = []
    for s in scenario_rows:
        bals = simulate_timeline(prof, {"scenario_type": s.scenario_type, "params": s.params or {}}, months)
        mets = calc_metrics(prof, bals)
        scenario_results.append(
            {
                "id": s.id,
                "name": s.name,
                "scenario_type": s.scenario_type,
                "params": s.params,
                "balances": [round(b) for b in bals],
                "metrics": mets,
                "explanation": generate_scenario_explanation(
                    prof, s.scenario_type, s.params or {}, mets, base_metrics
                ),
            }
        )

    best = worst = None
    if scenario_results:
        best = max(scenario_results, key=lambda r: r["metrics"]["runway"])
        worst = min(scenario_results, key=lambda r: r["metrics"]["runway"])

    return {
        "labels": _month_labels(months),
        "profile": {
            k: round(v, 2) if isinstance(v, float) else v for k, v in prof.items() if k != "expense_breakdown"
        },
        "expense_breakdown": prof["expense_breakdown"],
        "baseline": {
            "balances": [round(b) for b in base_balances],
            "metrics": base_metrics,
            "explanation": generate_baseline_explanation(prof, base_metrics),
        },
        "scenarios": scenario_results,
        "best_scenario_id": best["id"] if best else None,
        "worst_scenario_id": worst["id"] if worst else None,
        "insights": generate_insights(prof, base_metrics, scenario_results),
        "advice": generate_advice(prof, base_metrics),
    }


# ── AUTH ──────────────────────────────────
@router.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(400, "Name cannot be empty.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.email):
        raise HTTPException(400, "Please enter a valid email address.")
    pw_error = validate_password(req.password)
    if pw_error:
        raise HTTPException(400, pw_error)
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "An account with this email already exists.")
    user = User(name=req.name, email=req.email, hashed_pw=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    profile = FinancialProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    token = create_token({"sub": user.email})
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)


@router.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_pw):
        raise HTTPException(401, "Incorrect email or password")
    token = create_token({"sub": user.email})
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


# ── PROFILE ───────────────────────────────
@router.get("/profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p:
        p = FinancialProfile(user_id=user.id)
        db.add(p)
        db.commit()
        db.refresh(p)
    return {k: v for k, v in p.__dict__.items() if not k.startswith("_")}


@router.put("/profile")
def update_profile(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    merged = _merge_profile_in(data)
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p:
        p = FinancialProfile(user_id=user.id)
        db.add(p)
    for k, v in merged.items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return {"message": "Profile saved", "profile": {k: v for k, v in p.__dict__.items() if not k.startswith("_")}}


# ── SCENARIOS ─────────────────────────────
@router.get("/scenarios")
def list_scenarios(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Scenario).filter(Scenario.user_id == user.id, Scenario.is_active == True).all()
    return [_scenario_to_dict(s) for s in rows]


@router.post("/scenarios")
def create_scenario(data: ScenarioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_scenario(data)
    s = Scenario(user_id=user.id, name=data.name.strip(), scenario_type=data.scenario_type, params=data.params)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _scenario_to_dict(s)


@router.put("/scenarios/{sid}")
def update_scenario(sid: int, data: ScenarioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _validate_scenario(data)
    s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    s.name = data.name.strip()
    s.scenario_type = data.scenario_type
    s.params = data.params
    db.commit()
    db.refresh(s)
    return _scenario_to_dict(s)


@router.delete("/scenarios/{sid}")
def delete_scenario(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    s.is_active = False
    db.commit()
    return {"message": "Deleted"}


@router.get("/scenarios/templates")
def scenario_templates():
    return [
        {
            "id": "salary-cut",
            "name": "−30% salary",
            "icon": "📉",
            "desc": "Temporary pay cut",
            "default_params": {"cut": 30, "dur": 6, "start": 1},
        },
        {
            "id": "job-loss",
            "name": "3-month job loss",
            "icon": "💼",
            "desc": "No salary for three months",
            "default_params": {"dur": 3, "start": 1},
        },
        {
            "id": "new-emi",
            "name": "New EMI (₹3,000)",
            "icon": "🏍️",
            "desc": "Phone or appliance loan",
            "default_params": {"amount": 3000, "dur": 12, "start": 1},
        },
        {
            "id": "rent-hike",
            "name": "+₹2,000 rent",
            "icon": "🏠",
            "desc": "Fixed monthly increase",
            "default_params": {"amount": 2000, "start": 1},
        },
        {
            "id": "lifestyle-up",
            "name": "Lifestyle upgrade (+15%)",
            "icon": "✨",
            "desc": "Higher variable spending",
            "default_params": {"pct": 15, "start": 1},
        },
        {
            "id": "medical",
            "name": "Medical emergency (₹50k)",
            "icon": "🏥",
            "desc": "One-time hospital bill",
            "default_params": {"amount": 50000, "month": 3},
        },
    ]


# ── SIMULATE ──────────────────────────────
@router.post("/simulate")
def simulate(req: SimulateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(400, "No profile found. Save your profile first.")
    if not p.income:
        raise HTTPException(400, "Please set your income in your profile first.")

    scenario_ids = list(dict.fromkeys(req.scenario_ids))
    scenario_rows: list[Scenario] = []
    missing: list[int] = []
    for sid in scenario_ids:
        s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id, Scenario.is_active == True).first()
        if not s:
            missing.append(sid)
        else:
            scenario_rows.append(s)
    if missing:
        raise HTTPException(404, f"Scenario(s) not found or inactive: {missing}")

    result = run_simulation_for_profile(p, scenario_rows)
    run = SimulationRun(user_id=user.id, profile_snapshot=build_profile_dict(p), scenario_ids=scenario_ids, result=result)
    db.add(run)
    db.commit()

    return result


@router.get("/simulations")
def list_simulations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
):
    cfg = get_settings()
    page_size = limit if limit is not None else cfg.history_default_limit
    page_size = min(page_size, cfg.history_max_limit)

    q = db.query(SimulationRun).filter(SimulationRun.user_id == user.id)
    total = q.count()
    runs = q.order_by(SimulationRun.created_at.desc()).offset(offset).limit(page_size).all()

    out = []
    for r in runs:
        res = r.result or {}
        baseline_risk = (res.get("baseline") or {}).get("metrics", {}).get("risk_level")
        names = []
        for sid in r.scenario_ids or []:
            sc = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
            if sc:
                names.append(sc.name)
        out.append(
            {
                "id": r.id,
                "created_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.created_at else None,
                "scenario_ids": r.scenario_ids,
                "scenario_names": names,
                "baseline_risk": baseline_risk,
            }
        )
    return {"total": total, "limit": page_size, "offset": offset, "items": out}


@router.get("/simulations/{run_id}")
def get_simulation(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id, SimulationRun.user_id == user.id).first()
    if not run:
        raise HTTPException(404, "Simulation not found")
    return run.result
