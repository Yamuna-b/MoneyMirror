# Money Mirror 🪞

**Money Mirror** is a full-stack financial digital twin simulator. It allows users to model their financial profile, run stress-test simulations with dynamic "what-if" scenarios (job loss, salary cuts, rent hikes, medical emergencies), and analyze their safety runway, risk metrics, and cash flow trends.

---

## 🛠️ Tech Stack & Architecture

*   **Backend:** **FastAPI (Python)** — High-performance ASGI framework using Pydantic v2 for data validation and auto-generating OpenAPI documentation.
*   **Frontend:** **Vanilla HTML5, CSS3 & JS** — Zero-build glassmorphic Single Page App (SPA) with responsive styling and dynamic Chart.js dashboards.
*   **Database:** **SQLAlchemy (ORM)** — Uses SQLite for local development and cloud-native **Supabase PostgreSQL** in production.
*   **DevOps & CI/CD:** **Docker & GitHub Actions** — Containerized environment running a Pytest suite (15 tests) with automated deployment to Hugging Face Spaces.

---

## 📈 Key Simulation Features

*   **Growth Projections:** Models compound interest growth on savings based on risk profile (4% to 12%).
*   **Stress Testing:** Evaluates event-driven cash flows (e.g., job loss stops income, medical costs deduct flat sums).
*   **Safety metrics:** Calculates your safety runway (months of survival) and Debt-to-Income (DTI) ratio.

---

## 🚀 Quick Start (Local)

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run App
```bash
$env:MM_ENV="development"  # Windows Powershell
uvicorn main:app --reload --port 8000
```
*   App UI: [http://localhost:8000](http://localhost:8000)
*   API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Run Tests
```bash
pytest -v
```

---

## 🌐 Production Deployment

1.  Set `MM_ENV=production`.
2.  Set `MM_SECRET_KEY` (minimum 32 characters, required for security in production).
3.  Inject database connection URL into `MM_DATABASE_URL` (supports URL-encoded passwords).
