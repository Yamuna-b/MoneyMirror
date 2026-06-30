"""
Money Mirror — Sample Data Seeder
===================================
Populates the database with realistic demo users and one simulation run each.

Run AFTER starting the backend at least once (so DB tables exist).

Usage:
    python seed_data.py

Sample login credentials after seeding:
    Email:    yamuna@test.com
    Password: Yamuna@11

    Email:    arjun@test.com
    Password: Arjun@123
"""
from __future__ import annotations

import sys
from datetime import datetime

from auth_utils import hash_password
from database import FinancialProfile, Scenario, SessionLocal, SimulationRun, User
from routes import run_simulation_for_profile

USERS = [
    {
        "name": "Yamuna",
        "email": "yamuna@test.com",
        "password": "Yamuna@11",
        "profile": {
            "income": 52000,
            "other_income": 0,
            "savings": 85000,
            "min_balance": 8000,
            "safety_target": 3.0,
            "horizon_months": 12,
            "rent": 12000,
            "utilities": 1800,
            "insurance": 1200,
            "subscriptions": 700,
            "food": 5500,
            "transport": 2800,
            "dining": 3500,
            "shopping": 2500,
            "misc": 1500,
            "emis": [
                {"name": "Education Loan", "amount": 4200},
                {"name": "iPhone EMI", "amount": 2100},
            ],
        },
        "scenarios": [
            {"name": "What if my salary gets cut 25%?", "scenario_type": "salary-cut", "params": {"cut": 25, "dur": 4, "start": 2}},
            {"name": "Bike loan - Hero Splendor", "scenario_type": "new-emi", "params": {"amount": 3200, "dur": 24, "start": 1}},
            {"name": "Landlord hikes rent Rs. 2k", "scenario_type": "rent-hike", "params": {"amount": 2000, "start": 3}},
            {"name": "Job loss - worst case", "scenario_type": "job-loss", "params": {"dur": 3, "start": 1}},
        ],
    },
    {
        "name": "Arjun",
        "email": "arjun@test.com",
        "password": "Arjun@123",
        "profile": {
            "income": 88000,
            "other_income": 5000,
            "savings": 210000,
            "min_balance": 15000,
            "safety_target": 4.0,
            "horizon_months": 18,
            "rent": 18000,
            "utilities": 2500,
            "insurance": 2000,
            "subscriptions": 1200,
            "food": 7000,
            "transport": 4000,
            "dining": 6000,
            "shopping": 4000,
            "misc": 2000,
            "emis": [
                {"name": "Car Loan", "amount": 8500},
                {"name": "Laptop EMI", "amount": 1800},
                {"name": "Education Loan", "amount": 3500},
            ],
        },
        "scenarios": [
            {"name": "Switch to lower-paying startup", "scenario_type": "salary-cut", "params": {"cut": 30, "dur": 12, "start": 1}},
            {"name": "Medical emergency", "scenario_type": "medical", "params": {"amount": 80000, "month": 3}},
            {"name": "Lifestyle upgrade - new flat", "scenario_type": "lifestyle-up", "params": {"pct": 25, "start": 2}},
        ],
    },
]


def clear_existing(db) -> None:
    db.query(SimulationRun).delete()
    db.query(Scenario).delete()
    db.query(FinancialProfile).delete()
    db.query(User).delete()
    print("OK: Cleared existing data")


def seed() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).count()
        if existing > 0:
            ans = input(f"\n  Found {existing} existing user(s). Clear and reseed? (yes/no): ").strip().lower()
            if ans != "yes":
                print("  Cancelled. Existing data kept.")
                return
        clear_existing(db)
        db.commit()

        for ud in USERS:
            print(f"\n  Seeding user: {ud['name']} ({ud['email']}) ...")
            user = User(name=ud["name"], email=ud["email"], hashed_pw=hash_password(ud["password"]))
            db.add(user)
            db.flush()

            p_data = ud["profile"]
            profile = FinancialProfile(user_id=user.id, **p_data)
            db.add(profile)
            db.flush()
            print(f"    [OK] User + profile (ID={user.id})")

            scenario_rows: list[Scenario] = []
            for s in ud["scenarios"]:
                row = Scenario(
                    user_id=user.id,
                    name=s["name"],
                    scenario_type=s["scenario_type"],
                    params=s["params"],
                    is_active=True,
                )
                db.add(row)
                db.flush()
                scenario_rows.append(row)
                print(f"    [OK] Scenario: {s['name']}")

            db.refresh(profile)
            result = run_simulation_for_profile(profile, scenario_rows)
            scenario_ids = [s.id for s in scenario_rows]
            db.add(
                SimulationRun(
                    user_id=user.id,
                    profile_snapshot=result["profile"],
                    scenario_ids=scenario_ids,
                    result=result,
                    created_at=datetime.utcnow(),
                )
            )
            bm = result["baseline"]["metrics"]
            print(f"    [OK] Simulation run saved")
            print(f"\n    [REPORT] {ud['name']}: runway {bm['runway']} mo | risk {bm['risk_level']} | DTI {bm['dti']*100:.1f}%")

        db.commit()
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  [SUCCESS] SEEDING COMPLETE")
    print("=" * 60)
    print("\n  Log in at http://localhost:8000 with:")
    for ud in USERS:
        print(f"  *  {ud['email']}  /  {ud['password']}")
    print()


if __name__ == "__main__":
    try:
        seed()
    except Exception as exc:
        print(f"\n[ERROR] Seeding failed: {exc}", file=sys.stderr)
        print("    Start the backend once so tables exist: python money_mirror_backend.py\n", file=sys.stderr)
        sys.exit(1)
