# Money Mirror

**Personal financial digital twin for Indian UPI-era money life** — enter monthly income, EMIs, fixed and variable expenses, and savings; add what‑if scenarios (salary cut, job loss, new EMI, rent hike, lifestyle change); run a deterministic month‑by‑month simulation and see balance over time, safety runway, risk label, and short explanations.

Screenshots (optional): save `docs/screenshots/dashboard.png` and embed with `![Dashboard](docs/screenshots/dashboard.png)`.

## Features (focused)

| Area | What you get |
|------|----------------|
| Profile | Income, EMIs (list), fixed + variable expenses, savings, 6‑month emergency‑fund target (default), 12‑month horizon (default) |
| Scenarios | Salary cut, job loss, new EMI, rent hike (₹/month **or** %), lifestyle upgrade |
| Simulation | Baseline + any selected scenarios over N months |
| Results | Balance chart, runway + risk, 2–3 sentence insights per scenario |
| History | Last **3** runs with scenario names + baseline risk |

Risk thresholds and targets are **configurable via environment variables** (see `.env.example`).

## Quick start

### pip

```bash
cd Money_Mirror
pip install -r requirements.txt
python money_mirror_backend.py
```

Open **http://localhost:8000** — register, fill **My Profile**, use **Save & run baseline**, then add scenarios and **Run simulation**.

### uv (optional)

```bash
uv pip install -r requirements.txt
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker build -t money-mirror .
docker run -p 8000:8000 -e MM_SECRET_KEY=your-secret money-mirror
```

Copy `.env.example` to `.env` and adjust values as needed.

## Project layout

| Module | Role |
|--------|------|
| `config.py` | Thresholds and defaults from `MM_*` env vars |
| `schemas.py` | Pydantic request/response models |
| `simulation.py` | Pure cash-flow and risk logic (no FastAPI) |
| `database.py` | SQLAlchemy models + SQLite engine |
| `auth_utils.py` | bcrypt + JWT helpers |
| `deps.py` | DB session + `get_current_user` |
| `routes.py` | FastAPI routes calling `simulation` |
| `main.py` | App factory, CORS, static `money_mirror_app.html` |
| `money_mirror_app.html` | Single-page UI |

## API: `POST /api/simulate`

**Auth:** `Authorization: Bearer <token>` (obtain via `POST /api/auth/login`).

**Request**

```json
{
  "scenario_ids": [1, 2]
}
```

Use `[]` for **baseline only**. Scenario IDs belong to the logged-in user.

**Response (abbreviated)**

```json
{
  "labels": ["Now", "Apr '26", "May '26"],
  "baseline": {
    "balances": [120000, 118000, 116000],
    "metrics": {
      "runway": 10,
      "risk_level": "comfortable",
      "dti": 0.22,
      "emergency_fund_ratio": 4.5
    },
    "explanation": "Your baseline plan keeps a safety runway..."
  },
  "scenarios": [
    {
      "id": 1,
      "name": "−30% salary",
      "scenario_type": "salary-cut",
      "balances": [120000, 115000, 110000],
      "metrics": { "runway": 6, "risk_level": "caution" },
      "explanation": "Compared to baseline, this scenario cuts..."
    }
  ],
  "insights": ["..."],
  "advice": []
}
```

Full interactive docs: **http://localhost:8000/docs**

## Opinionated defaults

| Setting | Default |
|---------|---------|
| Forecast horizon | 12 months |
| Emergency fund **target** | 6 months of expenses |
| Min comfortable balance | ₹10,000 |

Scenario templates (also in the UI under **Quick add**) include e.g. −30% salary for 6 months, 3‑month job loss, +₹2,000 rent, etc. Override via `.env` and `config.py` keys.

## Seed data (optional)

```bash
python seed_data.py
```

## License

Use and modify for your hackathon or personal project as needed.
