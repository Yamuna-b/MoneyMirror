"""Integration tests for Goals CRUD and protected simulation API routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from deps import get_db
from main import app

# Set up test database (SQLite in-memory)
TEST_DATABASE_URL = "sqlite:///./test_money_mirror.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_user_flow_auth_and_goals(client):
    # 1. Register a test user
    reg_payload = {"name": "Test User", "email": "test@mimirror.com", "password": "Password1"}
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get profile (should be empty but auto-initialized)
    res = client.get("/api/profile", headers=headers)
    assert res.status_code == 200
    assert res.json()["income"] == 0

    # 3. Update profile with income and costs
    profile_payload = {
        "income": 60000,
        "other_income": 0,
        "savings": 100000,
        "min_balance": 10000,
        "rent": 15000,
        "utilities": 2000,
        "insurance": 1000,
        "subscriptions": 500,
        "food": 5000,
        "transport": 2000,
        "dining": 3000,
        "shopping": 2000,
        "misc": 1000,
        "emis": [],
        "horizon_months": 12,
        "safety_target": 6.0
    }
    res = client.put("/api/profile", json=profile_payload, headers=headers)
    assert res.status_code == 200

    # 4. Add a Goal (MS Goal)
    goal_payload = {"name": "New Laptop", "target_amount": 50000, "target_months": 6, "category": "gadget"}
    res = client.post("/api/goals", json=goal_payload, headers=headers)
    assert res.status_code == 200
    goal_id = res.json()["id"]
    assert res.json()["name"] == "New Laptop"

    # 5. List Goals
    res = client.get("/api/goals", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1

    # 6. Update Goal
    update_payload = {"name": "Macbook Pro", "target_amount": 60000, "target_months": 5, "category": "gadget"}
    res = client.put(f"/api/goals/{goal_id}", json=update_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Macbook Pro"
    assert res.json()["target_amount"] == 60000

    # 7. Run Simulation with aggressive mode
    sim_payload = {"scenario_ids": [], "simulation_mode": "aggressive"}
    res = client.post("/api/simulate", json=sim_payload, headers=headers)
    assert res.status_code == 200
    sim_res = res.json()
    assert "baseline" in sim_res
    # Ensure goal is included in baseline result list
    assert "goals" in sim_res["baseline"]
    assert len(sim_res["baseline"]["goals"]) == 1
    assert sim_res["baseline"]["goals"][0]["name"] == "Macbook Pro"

    # 8. Delete Goal
    res = client.delete(f"/api/goals/{goal_id}", headers=headers)
    assert res.status_code == 200

    # 9. Verify Goals is empty
    res = client.get("/api/goals", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 0
