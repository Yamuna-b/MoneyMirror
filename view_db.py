"""
Money Mirror — Database Viewer
================================
Run this anytime to see what's stored in your database.

Usage:
    python view_db.py          → shows all users and their profiles
    python view_db.py users    → just users
    python view_db.py profile  → profiles
    python view_db.py scenarios → saved scenarios
    python view_db.py sims     → simulation history
    python view_db.py clear    → delete ALL data (fresh start)
"""

import sys, json, sqlite3, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "money_mirror.db")

def connect():
    if not os.path.exists(DB_PATH):
        print(f"❌  Database not found at: {DB_PATH}")
        print("    Run the backend first (python money_mirror_backend.py) to create it.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def fmt_row(row, cols):
    return {cols[i]: row[i] for i in range(len(cols))}

def show_users(cur):
    print("\n" + "─"*60)
    print("  👥  USERS")
    print("─"*60)
    cur.execute("SELECT id, name, email, created_at FROM users")
    rows = cur.fetchall()
    if not rows:
        print("  (no users yet)")
    for r in rows:
        print(f"  ID: {r[0]}  |  Name: {r[1]}  |  Email: {r[2]}")
        print(f"         Joined: {r[3]}")
    print(f"\n  Total users: {len(rows)}")

def show_profiles(cur):
    print("\n" + "─"*60)
    print("  💰  FINANCIAL PROFILES")
    print("─"*60)
    cur.execute("""
        SELECT p.id, u.name, u.email,
               p.income, p.other_income, p.savings, p.min_balance,
               p.rent, p.utilities, p.insurance, p.subscriptions,
               p.food, p.transport, p.dining, p.shopping, p.misc,
               p.emis, p.horizon_months, p.safety_target, p.updated_at
        FROM financial_profiles p
        JOIN users u ON p.user_id = u.id
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (no profiles yet)")
    for r in rows:
        print(f"\n  User: {r[1]} ({r[2]})")
        print(f"  ├─ Income:         ₹{r[3]:,.0f}/mo  +  Other: ₹{r[4]:,.0f}/mo")
        print(f"  ├─ Savings:        ₹{r[5]:,.0f}  (min comfortable: ₹{r[6]:,.0f})")
        print(f"  ├─ Rent:           ₹{r[7]:,.0f}/mo")
        total_fixed = (r[7] or 0) + (r[8] or 0) + (r[9] or 0) + (r[10] or 0)
        total_var   = (r[11] or 0) + (r[12] or 0) + (r[13] or 0) + (r[14] or 0) + (r[15] or 0)
        emis = json.loads(r[16]) if r[16] else []
        total_emi   = sum(e.get('amount', 0) for e in emis)
        print(f"  ├─ Fixed expenses: ₹{total_fixed:,.0f}/mo  |  Variable: ₹{total_var:,.0f}/mo")
        print(f"  ├─ EMIs:           ₹{total_emi:,.0f}/mo  ({len(emis)} active)")
        for e in emis:
            print(f"  │    • {e.get('name','EMI')}: ₹{e.get('amount',0):,.0f}/mo")
        total_exp   = total_fixed + total_var + total_emi
        total_inc   = (r[3] or 0) + (r[4] or 0)
        monthly_cf  = total_inc - total_exp
        print(f"  ├─ Total expenses: ₹{total_exp:,.0f}/mo")
        print(f"  ├─ Monthly surplus/deficit: ₹{monthly_cf:+,.0f}/mo")
        print(f"  ├─ Safety target:  {r[18]} months  |  Horizon: {r[17]} months")
        print(f"  └─ Last updated:   {r[19]}")

def show_scenarios(cur):
    print("\n" + "─"*60)
    print("  🎲  SAVED SCENARIOS")
    print("─"*60)
    cur.execute("""
        SELECT s.id, u.name, s.name, s.scenario_type, s.params, s.created_at
        FROM scenarios s
        JOIN users u ON s.user_id = u.id
        WHERE s.is_active = 1
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (no saved scenarios yet)")
    for r in rows:
        params = json.loads(r[4]) if r[4] else {}
        print(f"\n  [{r[0]}] {r[2]}  (by {r[1]})")
        print(f"       Type: {r[3]}")
        print(f"       Params: {json.dumps(params)}")
        print(f"       Created: {r[5]}")
    print(f"\n  Total active scenarios: {len(rows)}")

def show_simulations(cur):
    print("\n" + "─"*60)
    print("  🔮  SIMULATION RUNS (last 10)")
    print("─"*60)
    cur.execute("""
        SELECT r.id, u.name, r.scenario_ids, r.result, r.created_at
        FROM simulation_runs r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (no simulations run yet)")
    for r in rows:
        result = json.loads(r[3]) if r[3] else {}
        sc_ids = json.loads(r[2]) if r[2] else []
        bm = result.get('baseline', {}).get('metrics', {})
        print(f"\n  Run #{r[0]}  by {r[1]}  at {r[4]}")
        print(f"  ├─ Scenarios tested: {len(sc_ids)}  (IDs: {sc_ids})")
        if bm:
            print(f"  ├─ Baseline runway:  {bm.get('runway','?')} months")
            print(f"  ├─ Risk level:       {bm.get('risk_level','?').upper()}")
            print(f"  ├─ DTI:              {bm.get('dti',0)*100:.1f}%")
            print(f"  └─ Emergency fund:   {bm.get('emergency_fund_ratio',0):.1f}x")
    print(f"\n  Total simulation runs: {len(rows)}")

def clear_db(cur, conn):
    confirm = input("\n  ⚠️  This will DELETE ALL data. Type 'yes' to confirm: ").strip()
    if confirm.lower() == 'yes':
        cur.execute("DELETE FROM simulation_runs")
        cur.execute("DELETE FROM scenarios")
        cur.execute("DELETE FROM financial_profiles")
        cur.execute("DELETE FROM users")
        conn.commit()
        print("  ✓ Database cleared.")
    else:
        print("  Cancelled.")

def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    conn = connect()
    cur  = conn.cursor()

    print(f"\n  📦  Database: {DB_PATH}")

    # Show table sizes
    for tbl in ["users", "financial_profiles", "scenarios", "simulation_runs"]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        n = cur.fetchone()[0]
        print(f"      {tbl}: {n} row{'s' if n!=1 else ''}")

    if cmd in ("all", "users"):     show_users(cur)
    if cmd in ("all", "profile"):   show_profiles(cur)
    if cmd in ("all", "scenarios"): show_scenarios(cur)
    if cmd in ("all", "sims"):      show_simulations(cur)
    if cmd == "clear":              clear_db(cur, conn)

    conn.close()
    print()

if __name__ == "__main__":
    main()
