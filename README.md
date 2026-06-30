---
title: MoneyMirror
emoji: 🪞
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Money Mirror 🪞

**Money Mirror** is a full-stack, personal financial digital twin simulator built for modern personal finance tracking. It allows users to model their financial profile (income, EMIs, fixed and variable expenses, and baseline savings), run stress-test simulations with dynamic "what-if" scenarios (job loss, salary cuts, rent hikes, medical emergencies), and view a month-by-month cash flow trajectory, safety runway, and risk ratings.

---

## 🛠️ Architecture & Tech Stack Rationale

This project is built using a modern, lightweight, and cloud-agnostic architecture optimized for high performance, ease of local development, and seamless cloud scalability:

### 1. Backend: FastAPI (Python)
*   **Why FastAPI:** High-performance ASGI framework. It leverages native Python asynchronous routing and strict type validation using **Pydantic v2**.
*   **Features Used:** Automatic OpenAPI/Swagger generation (`/docs`), custom dependency injection for database sessions, and clean route separating models, controllers, and services.

### 2. Frontend: Vanilla HTML5 & CSS3 (Glassmorphism design)
*   **Why Vanilla CSS/JS:** Zero build steps, zero bundle bloat, and lightning-fast load performance. It ensures maximum design flexibility and control.
*   **UI/UX Details:** Sleek dark-mode aesthetic with CSS Glassmorphism (`backdrop-filter`), responsive grid layout, dynamic Chart.js dashboards, and a single-click student sandbox demo flow.

### 3. Database: Supabase PostgreSQL (Production) & SQLite (Local)
*   **Why SQL:** Financial data has strict relational constraints (e.g., matching scenarios and run history to specific users). 
*   **ORM:** SQLAlchemy handles migrations and connects seamlessly to local SQLite for development, and cloud-native Supabase PostgreSQL in production.

### 4. Containerization & DevOps: Docker
*   **Why Docker:** Standardizes execution environments. The exact same container runs in local developer environments, on Hugging Face Spaces (using port `7860`), and on Render.

### 5. Automated CI/CD: GitHub Actions
*   **Why CI/CD:** Automates testing and deployment. A custom YAML pipeline runs the **Pytest suite (15 unit/integration tests)** upon every push. On success, it automatically authenticates and deploys the working build to Hugging Face Spaces.

---

## 📈 Financial Simulation Engine Features

*   **Compound Interest growth:** Dynamically models growth on general savings depending on market risk profile (Conservative: 4% annual, Moderate: 8%, Aggressive: 12%).
*   **Stress Scenario deductions:** Models dynamic cash events (e.g., job loss stops income, medical emergencies deduct flat sums, lifestyle upgrades increase variable costs).
*   **Safety Runway calculation:** Predicts how many months the user can survive before cash balances hit a configurable minimum comfort limit.
*   **Debt-to-Income (DTI) metrics:** Warns users if their fixed debt obligations exceed safe thresholds.

---

## 📂 Project Directory Structure

```
├── .github/workflows/   # CI/CD pipelines (GitHub Actions)
├── tests/              # 15 unit and integration tests (Pytest)
├── main.py             # ASGI application factory & security middlewares
├── routes.py           # REST API endpoints (Auth, Profile, Scenarios, Sims)
├── database.py         # SQLAlchemy schemas (User, Profile, Scenario, Run)
├── schemas.py          # Pydantic input/output validation models
├── simulation.py       # Pure mathematical cash flow engine logic
├── config.py           # Env variable parser & threshold definitions
├── auth_utils.py       # JWT creation, decoding, and password hashing
├── money_mirror_app.html# Modern responsive SPA frontend
├── requirements.txt    # Application dependencies
├── Dockerfile          # Multi-platform production Dockerfile
└── README.md           # Documentation (this file)
```

---

## 🚀 Quick Start (Local Development)

### 1. Setup Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the App
```bash
# Set development environment
$env:MM_ENV="development" # Powershell

# Start development server with reload
uvicorn main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to view the app, or **[http://localhost:8000/docs](http://localhost:8000/docs)** to view the interactive API swagger docs.

### 3. Run Automated Tests
```bash
pytest -v
```

---

## 🌐 Production Deployment Configurations

To deploy this application to production (e.g., Render, Hugging Face, or AWS):

1.  Set the environment mode `MM_ENV=production`.
2.  Configure a secure random secret key `MM_SECRET_KEY` of at least 32 characters (the app will raise a boot error if it's missing or too short).
3.  Inject your PostgreSQL connection string into `MM_DATABASE_URL` (SQLAlchemy parses url-encoded passwords dynamically).

For Hugging Face Spaces specifically, the default port is dynamically routed through port `7860` as specified in the YAML frontmatter.
