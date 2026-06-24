# Money Mirror

**Personal financial digital twin for Indian UPI-era money life** — enter monthly income, EMIs, fixed and variable expenses, and savings; add what‑if scenarios (salary cut, job loss, new EMI, rent hike, lifestyle change, medical emergency); run a deterministic month‑by‑month simulation and see balance over time, safety runway, risk label, and short explanations.

## Features

| Area | What you get |
|------|----------------|
| Profile | Income, EMIs (list), fixed + variable expenses, savings, 6‑month emergency‑fund target (default), 12‑month horizon (default) |
| Scenarios | Salary cut, job loss, new EMI, rent hike (₹/month **or** %), lifestyle upgrade, medical emergency |
| Simulation | Baseline + any selected scenarios over N months |
| Results | Balance chart, runway + risk, insights and advice per scenario |
| History | Paginated run history (default 10, max 50) |

Risk thresholds and targets are **configurable via environment variables** (see `.env.example`).

## Quick start (development)

```bash
cd Money_Mirror
pip install -r requirements.txt
python money_mirror_backend.py
```

Open **http://localhost:8000** — register, fill **My Profile**, use **Save & run baseline**, then add scenarios and **Run simulation**.

Optional demo data:

```bash
python seed_data.py
# yamuna@test.com / Yamuna@11
```

Run tests:

```bash
pytest
```

### Docker (development)

```bash
docker build -t money-mirror .
docker run -p 8000:8000 money-mirror
```

## Production deployment

1. Copy `.env.example` to `.env` and set:
   - `MM_ENV=production`
   - `MM_SECRET_KEY` — random string, **at least 32 characters**
   - `MM_CORS_ORIGINS` — your frontend origin(s), comma-separated
   - `MM_DATABASE_URL` — Postgres recommended, e.g. `postgresql+psycopg2://user:pass@host/dbname`

2. Install Postgres driver if needed: `pip install psycopg2-binary`

3. Run with uvicorn (Dockerfile uses this):

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Production behavior:
- Refuses to start with the default dev secret when `MM_ENV=production`
- Generic 500 responses (no stack traces leaked to clients)
- Security headers on all responses
- CORS locked to configured origins
- Invalid scenario IDs return **404** instead of being silently skipped
- Simulation history supports `?limit=` and `?offset=` query params

## Project layout

| Module | Role |
|--------|------|
| `config.py` | Thresholds and defaults from `MM_*` env vars |
| `schemas.py` | Pydantic request/response models |
| `simulation.py` | Pure cash-flow and risk logic (no FastAPI) |
| `database.py` | SQLAlchemy models + SQLite/Postgres engine |
| `auth_utils.py` | bcrypt + JWT helpers |
| `deps.py` | DB session + `get_current_user` |
| `routes.py` | FastAPI routes calling `simulation` |
| `main.py` | App factory, CORS, security headers |
| `money_mirror_app.html` | Single-page UI |
| `tests/` | Pytest suite for simulation + auth validation |

## API: `POST /api/simulate`

**Auth:** `Authorization: Bearer <token>` (obtain via `POST /api/auth/login`).

```json
{ "scenario_ids": [1, 2] }
```

Use `[]` for baseline only. All scenario IDs must belong to the logged-in user and be active.

Full interactive docs: **http://localhost:8000/docs**

## Opinionated defaults

| Setting | Default |
|---------|---------|
| Forecast horizon | 12 months |
| Emergency fund **target** | 6 months of expenses |
| Min comfortable balance | ₹10,000 |
| History page size | 10 runs |

## License

Use and modify for your hackathon or personal project as needed.
