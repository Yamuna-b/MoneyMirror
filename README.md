# 🪞 Money Mirror — Personal Financial Digital Twin

A full-stack web app that lets UPI-first Indian users simulate their financial future,
test what-if scenarios, and understand their money safety before committing to decisions.

---

## ⚡ Quick Start

### 1. Install dependencies

```bash
pip install fastapi "uvicorn[standard]" sqlalchemy "passlib[bcrypt]" "python-jose[cryptography]" pydantic
```

### 2. Put both files in the same folder

```
your-folder/
├── money_mirror_backend.py
└── money_mirror_app.html
```

### 3. Run the backend

```bash
python money_mirror_backend.py
```

### 4. Open the app

Visit: **http://localhost:8000**

---

## 🏗️ Architecture

```
Frontend  →  money_mirror_app.html  (served by FastAPI at /)
Backend   →  money_mirror_backend.py  (FastAPI + SQLite)
Database  →  money_mirror.db  (auto-created on first run)
```

### API Endpoints

| Method | Path                         | Description                    |
|--------|------------------------------|--------------------------------|
| POST   | /api/auth/register           | Create account                 |
| POST   | /api/auth/login              | Sign in, get JWT token         |
| GET    | /api/auth/me                 | Get current user               |
| GET    | /api/profile                 | Load financial profile         |
| PUT    | /api/profile                 | Save financial profile         |
| GET    | /api/scenarios               | List saved scenarios           |
| POST   | /api/scenarios               | Create new scenario            |
| PUT    | /api/scenarios/{id}          | Update scenario                |
| DELETE | /api/scenarios/{id}          | Delete scenario                |
| POST   | /api/simulate                | Run simulation                 |
| GET    | /api/simulations             | Simulation history (last 10)   |
| GET    | /api/simulations/{id}        | Load a past simulation         |
| GET    | /api/scenarios/templates     | Built-in scenario templates    |

---

## ✨ Features

- **Login & accounts** — JWT-based auth, data saved per user
- **Financial profile** — income, savings, rent, EMIs, lifestyle expenses
- **Safety target** — set a target like "3 months of expenses as safety"
  and see exactly how far you are and the ₹ gap
- **Scenario library** — save named scenarios (Salary Cut, Job Loss, New EMI, Rent Hike, etc.)
- **Side-by-side comparison** — see Baseline vs Scenario A vs Scenario B with
  "Safest option" and "Most risky" badges
- **4 safety metrics** — Safety Runway, DTI, Emergency Fund Ratio, Savings Ratio
- **Monte Carlo simulation** — 500 runs with randomised income/expense variation,
  shows p10/p50/p90 runway range and probability of staying safe
- **Simulation history** — last 10 runs saved and reloadable
- **Personalised insights & advice** — plain-language explanations with your actual numbers

---

## 🚀 Deploying to Production

### Option A: Simple VPS (EC2, DigitalOcean)

```bash
# Set a real secret key
export MM_SECRET_KEY="your-strong-random-secret-here"

# Optional: use PostgreSQL instead of SQLite
export MM_DATABASE_URL="postgresql://user:password@host/dbname"

# Run with gunicorn for production
pip install gunicorn
gunicorn money_mirror_backend:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Then put Nginx in front:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option B: Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install fastapi "uvicorn[standard]" sqlalchemy "passlib[bcrypt]" "python-jose[cryptography]" pydantic
COPY money_mirror_backend.py money_mirror_app.html ./
ENV MM_SECRET_KEY="change-this-in-production"
EXPOSE 8000
CMD ["uvicorn", "money_mirror_backend:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📊 Simulation Algorithms

| Algorithm | Description |
|-----------|-------------|
| Discrete-Time Cash-Flow | `balance(t+1) = balance(t) + income(t) - expenses(t)` applied month by month |
| Scenario Overlays | Each scenario modifies income/expenses for a defined range of months |
| Safety Metrics | DTI, Emergency Fund Ratio, Savings Ratio, Runway computed per simulation |
| Risk Classification | Rule-based: `emergency_fund < 3` or `runway < 2` or `DTI > 0.6` → High Risk |
| Monte Carlo | 500 runs with Gaussian noise on income (σ=4%) and variable expenses (σ=8%) |

---

## 🔒 Privacy

- No raw transaction logs or SMS data stored
- Only user-entered summarised financial data
- All simulation runs stored per user, encrypted via JWT sessions
- Change `MM_SECRET_KEY` before any public deployment
