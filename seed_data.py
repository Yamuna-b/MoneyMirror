"""
Money Mirror — Sample Data Seeder
===================================
Populates your database with realistic test data so you can
explore every feature of the website immediately.

Run AFTER starting the backend at least once (so DB tables exist).

Usage:
    python seed_data.py

Sample login credentials after seeding:
    Email:    yamuna@test.com
    Password: Yamuna@11

    Email:    arjun@test.com
    Password: Arjun@123
"""

import sys, json, sqlite3, os, hashlib, re
from datetime import datetime, timedelta

# ── Try to use bcrypt directly ──────────────────────────────────
try:
    import bcrypt as _bcrypt
    def hash_pw(pw):
        salt = _bcrypt.gensalt(rounds=12)
        return _bcrypt.hashpw(pw.encode("utf-8")[:72], salt).decode("utf-8")
    print("✓ Using bcrypt for password hashing")
except ImportError:
    # Fallback: sha256 (only for testing, not production)
    def hash_pw(pw):
        return "sha256$" + hashlib.sha256(pw.encode()).hexdigest()
    print("⚠ bcrypt not found, using sha256 (install bcrypt for production)")

DB_PATH = os.path.join(os.path.dirname(__file__), "money_mirror.db")

def connect():
    if not os.path.exists(DB_PATH):
        print(f"\n❌  Database not found at: {DB_PATH}")
        print("    Please run the backend first:")
        print("    python money_mirror_backend.py\n")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def clear_existing(cur):
    """Remove all existing data for a clean seed."""
    cur.execute("DELETE FROM simulation_runs")
    cur.execute("DELETE FROM scenarios")
    cur.execute("DELETE FROM financial_profiles")
    cur.execute("DELETE FROM users")
    print("✓ Cleared existing data")

# ════════════════════════════════════════════════════════════════
#  SAMPLE USERS
# ════════════════════════════════════════════════════════════════
USERS = [
    {
        "name":     "Yamuna",
        "email":    "yamuna@test.com",
        "password": "Yamuna@11",
        # Profile — fresh graduate, Chennai
        "profile": {
            "income":         52000,   # ₹52k take-home
            "other_income":   0,
            "savings":        85000,   # ₹85k saved so far
            "min_balance":    8000,    # feels stressed below ₹8k
            "safety_target":  3.0,     # wants 3 months as buffer
            "horizon_months": 12,
            "rent":           12000,
            "utilities":      1800,
            "insurance":      1200,
            "subscriptions":  700,     # Netflix + Spotify
            "food":           5500,
            "transport":      2800,    # Metro + Ola
            "dining":         3500,
            "shopping":       2500,
            "misc":           1500,
            "emis": [
                {"name": "Education Loan", "amount": 4200},
                {"name": "iPhone EMI",     "amount": 2100},
            ],
        },
        # Scenarios she has saved
        "scenarios": [
            {
                "name":          "What if my salary gets cut 25%?",
                "scenario_type": "salary-cut",
                "params":        {"cut": 25, "dur": 4, "start": 2},
            },
            {
                "name":          "Bike loan — Hero Splendor",
                "scenario_type": "new-emi",
                "params":        {"amount": 3200, "dur": 24, "start": 1},
            },
            {
                "name":          "Landlord hikes rent ₹2k",
                "scenario_type": "rent-hike",
                "params":        {"pct": 17, "start": 3},
            },
            {
                "name":          "Job loss — worst case",
                "scenario_type": "job-loss",
                "params":        {"dur": 3, "start": 1},
            },
        ],
    },
    {
        "name":     "Arjun",
        "email":    "arjun@test.com",
        "password": "Arjun@123",
        # Profile — 3 years experience, Bangalore
        "profile": {
            "income":         88000,
            "other_income":   5000,    # freelance
            "savings":        210000,
            "min_balance":    15000,
            "safety_target":  4.0,
            "horizon_months": 18,
            "rent":           18000,
            "utilities":      2500,
            "insurance":      2000,
            "subscriptions":  1200,
            "food":           7000,
            "transport":      4000,
            "dining":         6000,
            "shopping":       4000,
            "misc":           2000,
            "emis": [
                {"name": "Car Loan",       "amount": 8500},
                {"name": "Laptop EMI",     "amount": 1800},
                {"name": "Education Loan", "amount": 3500},
            ],
        },
        "scenarios": [
            {
                "name":          "Switch to lower-paying startup",
                "scenario_type": "salary-cut",
                "params":        {"cut": 30, "dur": 12, "start": 1},
            },
            {
                "name":          "Medical emergency",
                "scenario_type": "medical",
                "params":        {"amount": 80000, "month": 3},
            },
            {
                "name":          "Lifestyle upgrade — new flat",
                "scenario_type": "lifestyle-up",
                "params":        {"pct": 25, "start": 2},
            },
        ],
    },
]

# ════════════════════════════════════════════════════════════════
#  SIMULATION ENGINE (mirrors backend logic)
# ════════════════════════════════════════════════════════════════
def build_profile(p):
    total_emi   = sum(e["amount"] for e in p["emis"])
    fixed       = p["rent"] + p["utilities"] + p["insurance"] + p["subscriptions"]
    variable    = p["food"] + p["transport"] + p["dining"] + p["shopping"] + p["misc"]
    total_inc   = p["income"] + p["other_income"]
    total_exp   = fixed + variable + total_emi
    return {
        "income": total_inc, "savings": p["savings"],
        "min_balance": p["min_balance"], "rent": p["rent"],
        "fixed": fixed, "variable": variable,
        "total_emi": total_emi, "total_expenses": total_exp,
        "horizon": p["horizon_months"],
        "safety_target": p["safety_target"],
        "expense_breakdown": {
            "Rent/PG": p["rent"], "Food": p["food"],
            "EMIs": total_emi,    "Transport": p["transport"],
            "Dining": p["dining"],"Shopping": p["shopping"],
            "Utilities/Subs": p["utilities"]+p["insurance"]+p["subscriptions"],
            "Misc": p["misc"]
        }
    }

def simulate(prof, scenario=None):
    months = prof["horizon"]
    balances = [prof["savings"]]
    for t in range(months):
        prev = balances[-1]
        inc  = prof["income"]
        exp  = prof["total_expenses"]
        m    = t + 1
        if scenario:
            st = scenario["scenario_type"]
            p  = scenario["params"]
            s  = int(p.get("start", 1))
            d  = int(p.get("dur", 3))
            if st == "salary-cut"   and s <= m <= s+d-1: inc *= (1 - p.get("cut",20)/100)
            elif st == "job-loss"   and s <= m <= s+d-1: inc  = 0
            elif st == "new-emi"    and s <= m <= s+int(p.get("dur",12))-1: exp += p.get("amount",5000)
            elif st == "rent-hike"  and m >= s: exp += prof["rent"] * p.get("pct",10)/100
            elif st == "lifestyle-up" and m >= s: exp += prof["variable"] * p.get("pct",20)/100
            elif st == "medical"    and m == int(p.get("month",1)): exp += p.get("amount",50000)
        balances.append(round(prev + inc - exp))
    return balances

def calc_metrics(prof, balances):
    months     = len(balances) - 1
    monthly_cf = prof["income"] - prof["total_expenses"]
    ef_ratio   = prof["savings"] / prof["total_expenses"] if prof["total_expenses"] > 0 else 0
    dti        = prof["total_emi"] / prof["income"] if prof["income"] > 0 else 0
    sav_ratio  = max(0, monthly_cf) / prof["income"] if prof["income"] > 0 else 0
    runway = 0
    first_risk = None
    for i in range(1, len(balances)):
        if balances[i] >= prof["min_balance"]: runway = i
        elif first_risk is None:               first_risk = i; break
    if all(b >= prof["min_balance"] for b in balances[1:]): runway = months
    if ef_ratio < 1 or runway < 2 or dti > 0.6:   risk = "high"
    elif ef_ratio < 3 or runway < 4 or dti > 0.4:  risk = "caution"
    else:                                            risk = "comfortable"
    gap = max(0, (prof["safety_target"] - ef_ratio) * prof["total_expenses"])
    return {
        "emergency_fund_ratio": round(ef_ratio, 2),
        "dti":                  round(dti, 3),
        "savings_ratio":        round(sav_ratio, 3),
        "runway":               runway,
        "first_risk_month":     first_risk,
        "risk_level":           risk,
        "monthly_cashflow":     round(monthly_cf),
        "safety_target":        prof["safety_target"],
        "safety_gap_months":    round(max(0, prof["safety_target"] - ef_ratio), 2),
        "safety_gap_amount":    round(gap),
    }

def make_labels(months):
    today  = datetime.utcnow()
    labels = ["Now"]
    for i in range(1, months + 1):
        d = datetime(today.year + (today.month + i - 1) // 12,
                     (today.month + i - 1) % 12 + 1, 1)
        labels.append(d.strftime("%b '%y"))
    return labels

def generate_insights(prof, bm, scenario_results):
    lines = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    if bm["monthly_cashflow"] < 0:
        lines.append(f"Your expenses exceed income by {fmt(-bm['monthly_cashflow'])}/month. Savings will run out in ~{bm['runway']} months.")
    else:
        lines.append(f"With your current plan, you have a safety runway of {bm['runway']} months and save {fmt(bm['monthly_cashflow'])}/month.")
    if bm["safety_gap_amount"] > 0:
        lines.append(f"Your safety target is {prof['safety_target']:.1f} months. You are at {bm['emergency_fund_ratio']:.1f} months — short by {fmt(bm['safety_gap_amount'])}.")
    if bm["dti"] > 0.5:
        lines.append(f"⚠️ EMIs take {bm['dti']*100:.0f}% of income — above the 50% safe limit.")
    elif bm["dti"] > 0.35:
        lines.append(f"EMI ratio is {bm['dti']*100:.0f}%. Manageable, but don't add more EMIs.")
    if bm["emergency_fund_ratio"] < 3:
        lines.append(f"Emergency fund covers {bm['emergency_fund_ratio']:.1f} months. Aim for at least 3 months.")
    names = {"salary-cut":"A salary cut","job-loss":"Job loss","new-emi":"Adding this EMI",
             "rent-hike":"A rent hike","lifestyle-up":"A lifestyle upgrade","medical":"A medical emergency"}
    for sr in scenario_results:
        diff = sr["metrics"]["runway"] - bm["runway"]
        name = names.get(sr["scenario_type"], sr["name"])
        if diff < -1:
            lines.append(f"{name} would reduce your safety runway from {bm['runway']} to {sr['metrics']['runway']} months.")
    return lines

def generate_advice(prof, m):
    advice = []
    fmt = lambda n: f"₹{abs(int(n)):,}"
    if m["dti"] > 0.5:
        advice.append({"icon":"🚨","title":"EMI load is critical","desc":f"EMIs take {m['dti']*100:.0f}% of income. Don't add new loans.","type":"bad"})
    elif m["dti"] > 0.35:
        advice.append({"icon":"⚠️","title":"Watch your EMI ratio","desc":f"At {m['dti']*100:.0f}%, EMIs are manageable but leave little room.","type":"warn"})
    if m["emergency_fund_ratio"] < 3:
        gap = (3 - m["emergency_fund_ratio"]) * prof["total_expenses"]
        advice.append({"icon":"🏦","title":"Build your emergency fund","desc":f"You need {fmt(gap)} more to reach 3 months' cover.","type":"warn" if m["emergency_fund_ratio"]>1 else "bad"})
    if m["risk_level"] == "comfortable":
        advice.append({"icon":"📈","title":"Great — put surplus to work","desc":"Finances are healthy. Consider SIPs, PPF, or NPS.","type":"good"})
    if prof["total_expenses"] > prof["income"] * 0.8:
        advice.append({"icon":"✂️","title":"Trim variable expenses","desc":f"Expenses are {prof['total_expenses']/prof['income']*100:.0f}% of income. Check dining and shopping first.","type":"warn"})
    return advice[:4]

# ════════════════════════════════════════════════════════════════
#  SEED
# ════════════════════════════════════════════════════════════════
def seed():
    conn = connect()
    cur  = conn.cursor()

    # Ask before clearing
    cur.execute("SELECT COUNT(*) FROM users")
    existing = cur.fetchone()[0]
    if existing > 0:
        ans = input(f"\n  Found {existing} existing user(s). Clear and reseed? (yes/no): ").strip().lower()
        if ans != "yes":
            print("  Cancelled. Existing data kept.")
            conn.close()
            return
    clear_existing(cur)
    conn.commit()

    for ud in USERS:
        print(f"\n  Seeding user: {ud['name']} ({ud['email']}) ...")

        # ── Insert user ──
        cur.execute(
            "INSERT INTO users (name, email, hashed_pw, created_at) VALUES (?,?,?,?)",
            (ud["name"], ud["email"], hash_pw(ud["password"]), datetime.utcnow())
        )
        user_id = cur.lastrowid
        print(f"    ✓ User created (ID={user_id})")

        # ── Insert profile ──
        p = ud["profile"]
        cur.execute("""
            INSERT INTO financial_profiles
            (user_id, income, other_income, savings, min_balance, safety_target,
             rent, utilities, insurance, subscriptions,
             food, transport, dining, shopping, misc,
             emis, horizon_months, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            user_id,
            p["income"], p["other_income"], p["savings"],
            p["min_balance"], p["safety_target"],
            p["rent"], p["utilities"], p["insurance"], p["subscriptions"],
            p["food"], p["transport"], p["dining"], p["shopping"], p["misc"],
            json.dumps(p["emis"]),
            p["horizon_months"],
            datetime.utcnow()
        ))
        print(f"    ✓ Profile saved")

        # ── Insert scenarios ──
        scenario_ids = []
        for s in ud["scenarios"]:
            cur.execute("""
                INSERT INTO scenarios (user_id, name, scenario_type, params, is_active, created_at)
                VALUES (?,?,?,?,1,?)
            """, (user_id, s["name"], s["scenario_type"],
                  json.dumps(s["params"]), datetime.utcnow()))
            sid = cur.lastrowid
            scenario_ids.append(sid)
            print(f"    ✓ Scenario: {s['name']}")

        # ── Run a simulation and store it ──
        prof   = build_profile(p)
        months = p["horizon_months"]
        labels = make_labels(months)

        base_balances = simulate(prof)
        base_metrics  = calc_metrics(prof, base_balances)

        # simulate all scenarios
        sc_results = []
        for i, s in enumerate(ud["scenarios"]):
            bals = simulate(prof, s)
            mets = calc_metrics(prof, bals)
            sc_results.append({
                "id":            scenario_ids[i],
                "name":          s["name"],
                "scenario_type": s["scenario_type"],
                "params":        s["params"],
                "balances":      bals,
                "metrics":       mets,
            })

        best  = max(sc_results, key=lambda r: r["metrics"]["runway"]) if sc_results else None
        worst = min(sc_results, key=lambda r: r["metrics"]["runway"]) if sc_results else None

        result = {
            "labels":            labels,
            "profile":           {k: round(v,2) if isinstance(v,float) else v
                                  for k,v in prof.items() if k != "expense_breakdown"},
            "expense_breakdown": prof["expense_breakdown"],
            "baseline":          {"balances": base_balances, "metrics": base_metrics},
            "scenarios":         sc_results,
            "best_scenario_id":  best["id"]  if best  else None,
            "worst_scenario_id": worst["id"] if worst else None,
            "insights":          generate_insights(prof, base_metrics, sc_results),
            "advice":            generate_advice(prof, base_metrics),
            "monte_carlo":       None,
        }

        cur.execute("""
            INSERT INTO simulation_runs (user_id, profile_snapshot, scenario_ids, result, created_at)
            VALUES (?,?,?,?,?)
        """, (
            user_id,
            json.dumps(prof),
            json.dumps(scenario_ids),
            json.dumps(result),
            datetime.utcnow()
        ))
        print(f"    ✓ Simulation run saved")

        # ── Print summary ──
        bm = base_metrics
        total_exp = prof["total_expenses"]
        print(f"\n    📊 Financial Summary for {ud['name']}:")
        print(f"       Income:         ₹{prof['income']:,.0f}/mo")
        print(f"       Total expenses: ₹{total_exp:,.0f}/mo")
        print(f"       Monthly saving: ₹{bm['monthly_cashflow']:+,.0f}/mo")
        print(f"       Safety runway:  {bm['runway']} months")
        print(f"       Risk level:     {bm['risk_level'].upper()}")
        print(f"       DTI ratio:      {bm['dti']*100:.1f}%")
        print(f"       Emergency fund: {bm['emergency_fund_ratio']:.1f}x")

    conn.commit()
    conn.close()

    print("\n" + "═"*60)
    print("  ✅  SEEDING COMPLETE")
    print("═"*60)
    print("\n  You can now log in with:")
    print()
    for ud in USERS:
        print(f"  👤  {ud['name']}")
        print(f"      Email:    {ud['email']}")
        print(f"      Password: {ud['password']}")
        print()
    print("  👉  Open: http://localhost:8000")
    print("      (make sure backend is running first)\n")

if __name__ == "__main__":
    seed()
