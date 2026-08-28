import os
import tempfile
import pytest

os.environ["TESTING"] = "1"

import app as application

@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    old = application.DB_PATH
    application.DB_PATH = path
    application.init_db()
    application.app.config.update(TESTING=True)

    with application.app.test_client() as client:
        yield client

    os.unlink(path)
    application.DB_PATH = old

def test_budget_and_dashboard(client):
    r = client.post("/api/budget", json={
        "month": "2026-08",
        "income": 20000,
        "savings_goal": 3000,
        "food": 5000,
        "transport": 2000
    })
    assert r.status_code == 200

    r = client.get("/api/dashboard?month=2026-08")
    assert r.status_code == 200
    data = r.get_json()
    assert data["budget"]["income"] == 20000

def test_expense(client):
    r = client.post("/api/expenses", json={
        "amount": 120,
        "category": "Food",
        "description": "Lunch",
        "spent_on": "2026-08-20"
    })
    assert r.status_code == 200

    r = client.get("/api/expenses?month=2026-08")
    assert r.status_code == 200
    assert len(r.get_json()) == 1

def test_affordability(client):
    r = client.post("/api/afford", json={
        "monthly_income": 20000,
        "current_month_spend": 10000,
        "savings_goal": 3000,
        "price": 2000,
        "essential": False
    })
    assert r.status_code == 200
    assert "remaining_after_purchase" in r.get_json()

def test_loan(client):
    r = client.post("/api/loan", json={
        "principal": 100000,
        "annual_rate": 10,
        "years": 2
    })
    assert r.status_code == 200
    assert r.get_json()["emi"] > 0
