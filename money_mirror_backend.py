"""
Money Mirror — FastAPI Backend
================================
Run with:
    pip install fastapi uvicorn[standard] sqlalchemy passlib[bcrypt] python-jose[cryptography] pydantic
    python money_mirror_backend.py

Then open: http://localhost:8000
The frontend (money_mirror_app.html) should be served from the same directory,
or configure CORS to allow your frontend domain.
"""

from __future__ import annotations
import os, json, math, random
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    JSON, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship

from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
SECRET_KEY   = os.getenv("MM_SECRET_KEY", "money-mirror-dev-secret-change-in-production")
ALGORITHM    = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7   # 7 days
DATABASE_URL = os.getenv("MM_DATABASE_URL", "sqlite:///./money_mirror.db")

# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────
engine   = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base     = declarative_base()

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, index=True, nullable=False)
    name       = Column(String, nullable=False)
    hashed_pw  = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    profiles   = relationship("FinancialProfile", back_populates="user", cascade="all, delete")
    scenarios  = relationship("Scenario",         back_populates="user", cascade="all, delete")
    simulations= relationship("SimulationRun",    back_populates="user", cascade="all, delete")

class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    income          = Column(Float, default=0)
    other_income    = Column(Float, default=0)
    savings         = Column(Float, default=0)
    min_balance     = Column(Float, default=10000)
    rent            = Column(Float, default=0)
    utilities       = Column(Float, default=0)
    insurance       = Column(Float, default=0)
    subscriptions   = Column(Float, default=0)
    food            = Column(Float, default=0)
    transport       = Column(Float, default=0)
    dining          = Column(Float, default=0)
    shopping        = Column(Float, default=0)
    misc            = Column(Float, default=0)
    emis            = Column(JSON, default=list)   # [{"name":"Bike","amount":3500}, ...]
    horizon_months  = Column(Integer, default=12)
    safety_target   = Column(Float, default=3.0)   # months of expenses as safety target
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user            = relationship("User", back_populates="profiles")

class Scenario(Base):
    __tablename__ = "scenarios"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String, nullable=False)
    scenario_type = Column(String, nullable=False)  # salary-cut, job-loss, etc.
    params      = Column(JSON, default=dict)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    user        = relationship("User", back_populates="scenarios")

class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_snapshot= Column(JSON)   # snapshot of profile at time of run
    scenario_ids    = Column(JSON)   # list of scenario IDs used
    result          = Column(JSON)   # full simulation result
    created_at      = Column(DateTime, default=datetime.utcnow)
    user            = relationship("User", back_populates="simulations")

Base.metadata.create_all(bind=engine)

# ─────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────
# passlib + bcrypt 4.x compatibility fix
import warnings
warnings.filterwarnings("ignore", ".*bcrypt.*")
try:
    import bcrypt
    # bcrypt 4.x changed the API; patch passlib to work with it
    if not hasattr(bcrypt, '__about__'):
        bcrypt.__about__ = type('about', (), {'__version__': bcrypt.__version__})()
except Exception:
    pass

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw.encode('utf-8')[:72].decode('utf-8', errors='ignore'))

def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw.encode('utf-8')[:72].decode('utf-8', errors='ignore'), hashed)

def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:    yield db
    finally: db.close()

def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    cred_ex = HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email: raise cred_ex
    except JWTError:
        raise cred_ex
    user = db.query(User).filter(User.email == email).first()
    if not user: raise cred_ex
    return user

# ─────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    user_email: str

class ProfileIn(BaseModel):
    income: float = 0
    other_income: float = 0
    savings: float = 0
    min_balance: float = 10000
    rent: float = 0
    utilities: float = 0
    insurance: float = 0
    subscriptions: float = 0
    food: float = 0
    transport: float = 0
    dining: float = 0
    shopping: float = 0
    misc: float = 0
    emis: list = []
    horizon_months: int = 12
    safety_target: float = 3.0

class ScenarioIn(BaseModel):
    name: str
    scenario_type: str
    params: dict = {}

class SimulateRequest(BaseModel):
    scenario_ids: List[int] = []
    run_monte_carlo: bool = False
    mc_runs: int = 500

# ─────────────────────────────────────────
# SIMULATION ENGINE
# ─────────────────────────────────────────
def build_profile_dict(p: FinancialProfile) -> dict:
    total_emi = sum(e.get("amount", 0) for e in (p.emis or []))
    fixed = p.rent + p.utilities + p.insurance + p.subscriptions
    variable = p.food + p.transport + p.dining + p.shopping + p.misc
    total_income = p.income + p.other_income
    total_expenses = fixed + variable + total_emi
    return {
        "income": total_income, "savings": p.savings, "min_balance": p.min_balance,
        "rent": p.rent, "fixed": fixed, "variable": variable,
        "total_emi": total_emi, "total_expenses": total_expenses,
        "horizon": p.horizon_months, "safety_target": p.safety_target,
        "emis": p.emis or [],
        "expense_breakdown": {
            "Rent/PG": p.rent, "Food": p.food, "EMIs": total_emi,
            "Transport": p.transport, "Dining": p.dining, "Shopping": p.shopping,
            "Utilities/Subs": p.utilities + p.insurance + p.subscriptions, "Misc": p.misc
        }
    }

def simulate_timeline(profile: dict, scenario: dict | None, months: int) -> list[float]:
    balances = [profile["savings"]]
    for t in range(months):
        prev = balances[-1]
        inc = profile["income"]
        exp = profile["total_expenses"]
        m   = t + 1  # 1-based month

        if scenario:
            st  = scenario.get("scenario_type")
            p   = scenario.get("params", {})
            s   = int(p.get("start", 1))
            dur = int(p.get("dur", 3))

            if st == "salary-cut" and s <= m <= s + dur - 1:
                inc *= (1 - float(p.get("cut", 20)) / 100)
            elif st == "job-loss" and s <= m <= s + dur - 1:
                inc = 0
            elif st == "new-emi" and s <= m <= s + int(p.get("dur", 12)) - 1:
                exp += float(p.get("amount", 5000))
            elif st == "rent-hike" and m >= s:
                exp += profile["rent"] * float(p.get("pct", 10)) / 100
            elif st == "lifestyle-up" and m >= s:
                exp += profile["variable"] * float(p.get("pct", 20)) / 100
            elif st == "medical" and m == int(p.get("month", 1)):
                exp += float(p.get("amount", 50000))

        balances.append(prev + inc - exp)
    return balances

def calc_metrics(profile: dict, balances: list[float]) -> dict:
    months = len(balances) - 1
    monthly_cf = profile["income"] - profile["total_expenses"]
    ef_ratio  = profile["savings"] / profile["total_expenses"] if profile["total_expenses"] > 0 else 0
    dti        = profile["total_emi"] / profile["income"] if profile["income"] > 0 else 0
    sav_ratio  = max(0, monthly_cf) / profile["income"] if profile["income"] > 0 else 0

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

    if ef_ratio < 1 or runway < 2 or dti > 0.6:   risk = "high"
    elif ef_ratio < 3 or runway < 4 or dti > 0.4:  risk = "caution"
    else:                                            risk = "comfortable"

    safety_gap_months = profile.get("safety_target", 3.0) - ef_ratio
    safety_gap_amount = max(0, safety_gap_months * profile["total_expenses"])

    return {
        "emergency_fund_ratio": round(ef_ratio, 2),
        "dti": round(dti, 3),
        "savings_ratio": round(sav_ratio, 3),
        "runway": runway,
        "first_risk_month": first_risk,
        "risk_level": risk,
        "monthly_cashflow": round(monthly_cf),
        "safety_target": profile.get("safety_target", 3.0),
        "safety_gap_months": round(safety_gap_months, 2),
        "safety_gap_amount": round(safety_gap_amount)
    }

def run_monte_carlo(profile: dict, n: int = 500) -> dict:
    mu_i, sig_i = profile["income"], profile["income"] * 0.04
    mu_e, sig_e = profile["variable"], profile["variable"] * 0.08
    months = int(profile["horizon"])
    runways = []
    for _ in range(n):
        bal = profile["savings"]
        rw  = 0
        for t in range(months):
            inc = max(0, random.gauss(mu_i, sig_i))
            exp = max(0, profile["fixed"] + profile["total_emi"] + random.gauss(mu_e, sig_e))
            bal = bal + inc - exp
            if bal >= profile["min_balance"]:
                rw = t + 1
            else:
                break
        else:
            rw = months
        runways.append(rw)
    runways.sort()
    return {
        "p10":  runways[int(n * 0.10)],
        "p50":  runways[int(n * 0.50)],
        "p90":  runways[int(n * 0.90)],
        "prob_safe": round(sum(1 for r in runways if r == months) / n * 100, 1),
        "runs": n
    }

def generate_insights(profile: dict, base_metrics: dict, scenario_results: list) -> list[str]:
    lines = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    m = base_metrics

    if m["monthly_cashflow"] < 0:
        lines.append(f"Your current expenses exceed income by {fmt(-m['monthly_cashflow'])}/month. Your savings will be depleted in approximately {m['runway']} months.")
    else:
        lines.append(f"With your current plan, you have a safety runway of {m['runway']} month{'s' if m['runway']!=1 else ''} and are saving {fmt(m['monthly_cashflow'])}/month.")

    if m["safety_gap_amount"] > 0:
        lines.append(f"Your safety target is {profile.get('safety_target',3.0):.1f} months of expenses. You are at {m['emergency_fund_ratio']:.1f} months — short by {fmt(m['safety_gap_amount'])}.")

    if m["dti"] > 0.5:
        lines.append(f"⚠️ Your EMIs consume {m['dti']*100:.0f}% of income — above the 50% safe limit. Avoid new loans until you clear one.")
    elif m["dti"] > 0.35:
        lines.append(f"Your EMI ratio is {m['dti']*100:.0f}%. Manageable, but adding any new EMI would push you toward the risk zone.")

    if m["emergency_fund_ratio"] < 3:
        lines.append(f"Your emergency fund covers {m['emergency_fund_ratio']:.1f} months of expenses. The recommended minimum is 3 months.")

    names = {"salary-cut":"A salary cut","job-loss":"Job loss","new-emi":"Adding this EMI",
             "rent-hike":"A rent hike","lifestyle-up":"A lifestyle upgrade","medical":"A medical emergency"}
    base_rw = m["runway"]
    for sr in scenario_results:
        diff = sr["metrics"]["runway"] - base_rw
        name = names.get(sr["scenario_type"], sr["name"])
        if diff < -1:
            lines.append(f"{name} would reduce your safety runway from {base_rw} to {sr['metrics']['runway']} month{'s' if sr['metrics']['runway']!=1 else ''}.")
        elif diff >= 0:
            lines.append(f"{name} (as configured) has a manageable impact on your plan.")
    return lines

def generate_advice(profile: dict, metrics: dict) -> list[dict]:
    advice = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    if metrics["dti"] > 0.5:
        advice.append({"icon":"🚨","title":"EMI load is critical","desc":f"EMIs take {metrics['dti']*100:.0f}% of income. Don't add new loans. Focus on clearing one EMI to reduce pressure.","type":"bad"})
    elif metrics["dti"] > 0.35:
        advice.append({"icon":"⚠️","title":"Watch your EMI ratio","desc":f"At {metrics['dti']*100:.0f}%, EMIs are manageable but leave little room. Aim to bring this below 35%.","type":"warn"})
    if metrics["emergency_fund_ratio"] < 3:
        gap = (3 - metrics["emergency_fund_ratio"]) * profile["total_expenses"]
        advice.append({"icon":"🏦","title":"Build your emergency fund","desc":f"At {metrics['emergency_fund_ratio']:.1f}× coverage, you need {fmt(gap)} more to reach the 3-month safety buffer.","type":"warn" if metrics["emergency_fund_ratio"]>1 else "bad"})
    if metrics["risk_level"] == "comfortable":
        advice.append({"icon":"📈","title":"Great position — put surplus to work","desc":"Your finances are healthy. Consider SIPs, PPF, or NPS to make your monthly surplus work harder.","type":"good"})
    if profile["total_expenses"] > profile["income"] * 0.8:
        advice.append({"icon":"✂️","title":"Trim variable expenses","desc":f"Expenses are {profile['total_expenses']/profile['income']*100:.0f}% of income. Check dining, shopping, or subscriptions for quick wins.","type":"warn" if profile["total_expenses"]<profile["income"] else "bad"})
    if metrics["savings_ratio"] < 0.1 and metrics["monthly_cashflow"] > 0:
        target = fmt(profile["income"] * 0.2)
        advice.append({"icon":"💰","title":"Increase savings rate","desc":f"You're saving {metrics['savings_ratio']*100:.0f}% of income. Try reaching 20% — that's {target}/month as a target.","type":"warn"})
    return advice[:4]

# ─────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────
app = FastAPI(title="Money Mirror API", version="1.0.0")

# Always return JSON errors, never HTML
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})

app.add_middleware(CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── AUTH ──────────────────────────────────
@app.post("/api/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(name=req.name, email=req.email, hashed_pw=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    # create default empty profile
    profile = FinancialProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    token = create_token({"sub": user.email})
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)

@app.post("/api/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_pw):
        raise HTTPException(401, "Incorrect email or password")
    token = create_token({"sub": user.email})
    return TokenResponse(access_token=token, user_name=user.name, user_email=user.email)

@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}

# ── PROFILE ───────────────────────────────
@app.get("/api/profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p:
        p = FinancialProfile(user_id=user.id)
        db.add(p); db.commit(); db.refresh(p)
    # exclude SQLAlchemy internal state key
    data = {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
    return data

@app.put("/api/profile")
def update_profile(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p:
        p = FinancialProfile(user_id=user.id)
        db.add(p)
    for k, v in data.dict().items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit(); db.refresh(p)
    return {"message": "Profile saved", "profile": p.__dict__}

# ── SCENARIOS ─────────────────────────────
@app.get("/api/scenarios")
def list_scenarios(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Scenario).filter(Scenario.user_id == user.id, Scenario.is_active == True).all()

@app.post("/api/scenarios")
def create_scenario(data: ScenarioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = Scenario(user_id=user.id, name=data.name, scenario_type=data.scenario_type, params=data.params)
    db.add(s); db.commit(); db.refresh(s)
    return s

@app.put("/api/scenarios/{sid}")
def update_scenario(sid: int, data: ScenarioIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
    if not s: raise HTTPException(404, "Scenario not found")
    s.name = data.name; s.scenario_type = data.scenario_type; s.params = data.params
    db.commit(); db.refresh(s)
    return s

@app.delete("/api/scenarios/{sid}")
def delete_scenario(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
    if not s: raise HTTPException(404, "Scenario not found")
    s.is_active = False
    db.commit()
    return {"message": "Deleted"}

# ── SIMULATE ──────────────────────────────
@app.post("/api/simulate")
def simulate(req: SimulateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(FinancialProfile).filter(FinancialProfile.user_id == user.id).first()
    if not p: raise HTTPException(400, "No profile found. Save your profile first.")
    if not p.income: raise HTTPException(400, "Please set your income in your profile first.")

    prof = build_profile_dict(p)
    months = p.horizon_months

    # baseline
    base_balances = simulate_timeline(prof, None, months)
    base_metrics  = calc_metrics(prof, base_balances)

    # month labels
    today = datetime.utcnow()
    labels = ["Now"] + [
        (today.replace(day=1) + timedelta(days=32*i)).strftime("%b '%y")
        for i in range(1, months + 1)
    ]

    # scenarios
    scenario_results = []
    saved_scenarios  = []
    for sid in req.scenario_ids:
        s = db.query(Scenario).filter(Scenario.id == sid, Scenario.user_id == user.id).first()
        if not s: continue
        saved_scenarios.append(s)
        bals = simulate_timeline(prof, {"scenario_type": s.scenario_type, "params": s.params}, months)
        mets = calc_metrics(prof, bals)
        scenario_results.append({
            "id": s.id, "name": s.name,
            "scenario_type": s.scenario_type, "params": s.params,
            "balances": [round(b) for b in bals],
            "metrics": mets
        })

    insights = generate_insights(prof, base_metrics, scenario_results)
    advice   = generate_advice(prof, base_metrics)

    # find safest / riskiest
    best = None; worst = None
    if scenario_results:
        best  = max(scenario_results, key=lambda r: r["metrics"]["runway"])
        worst = min(scenario_results, key=lambda r: r["metrics"]["runway"])

    # monte carlo
    mc = None
    if req.run_monte_carlo:
        mc = run_monte_carlo(prof, req.mc_runs)

    result = {
        "labels": labels,
        "profile": {k: round(v,2) if isinstance(v,float) else v for k,v in prof.items() if k != "expense_breakdown"},
        "expense_breakdown": prof["expense_breakdown"],
        "baseline": {"balances": [round(b) for b in base_balances], "metrics": base_metrics},
        "scenarios": scenario_results,
        "best_scenario_id":  best["id"]  if best  else None,
        "worst_scenario_id": worst["id"] if worst else None,
        "insights": insights,
        "advice":   advice,
        "monte_carlo": mc
    }

    # save run
    run = SimulationRun(user_id=user.id, profile_snapshot=prof,
                        scenario_ids=req.scenario_ids, result=result)
    db.add(run); db.commit()

    return result

@app.get("/api/simulations")
def list_simulations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    runs = db.query(SimulationRun).filter(SimulationRun.user_id == user.id)\
             .order_by(SimulationRun.created_at.desc()).limit(10).all()
    return [{"id": r.id, "created_at": r.created_at, "scenario_ids": r.scenario_ids} for r in runs]

@app.get("/api/simulations/{run_id}")
def get_simulation(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id, SimulationRun.user_id == user.id).first()
    if not run: raise HTTPException(404, "Simulation not found")
    return run.result

# ── SCENARIO TEMPLATES ────────────────────
@app.get("/api/scenarios/templates")
def scenario_templates():
    return [
        {"id": "salary-cut",   "name": "Salary Cut",          "icon": "📉", "desc": "What if your pay reduces?",            "default_params": {"cut": 20,    "dur": 3, "start": 1}},
        {"id": "job-loss",     "name": "Job Loss",             "icon": "💼", "desc": "What if income stops temporarily?",    "default_params": {"dur": 3,             "start": 1}},
        {"id": "new-emi",      "name": "New EMI",              "icon": "🏍️", "desc": "Bike, phone, or appliance?",          "default_params": {"amount": 5000,"dur":12,"start":1}},
        {"id": "rent-hike",    "name": "Rent Hike",            "icon": "🏠", "desc": "Landlord raises rent — how bad?",      "default_params": {"pct": 10,            "start": 1}},
        {"id": "lifestyle-up", "name": "Lifestyle Upgrade",    "icon": "✨", "desc": "Spending more on dining, travel?",     "default_params": {"pct": 20,            "start": 1}},
        {"id": "medical",      "name": "Medical Emergency",    "icon": "🏥", "desc": "One-time large unexpected expense",    "default_params": {"amount": 50000,      "month": 1}},
    ]

# ── SERVE FRONTEND ────────────────────────
@app.get("/")
def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "money_mirror_app.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Money Mirror API running. Place money_mirror_app.html in the same directory."}

@app.get("/health")
def health():
    return {"status": "ok", "service": "Money Mirror API", "version": "1.0.0"}

# ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n🪞  Money Mirror API starting...")
    print("    → API docs:  http://localhost:8000/docs")
    print("    → Frontend:  http://localhost:8000/\n")
    uvicorn.run("money_mirror_backend:app", host="0.0.0.0", port=8000, reload=True)
