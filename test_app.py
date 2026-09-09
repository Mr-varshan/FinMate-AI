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
    application.app.config.update(TESTING=True, SECRET_KEY="test-secret-key")

    with application.app.test_client() as client:
        client.post("/register", data={
            "name": "Test Student",
            "email": "student@example.com",
            "password": "password123",
        })
        response = client.post("/login", data={
            "email": "student@example.com",
            "password": "password123",
        })
        assert response.status_code == 302
        yield client

    os.unlink(path)
    application.DB_PATH = old


def test_budget_and_dashboard(client):
    r = client.post("/api/budget", json={
        "month": "2026-08",
        "income": 20000,
        "savings_goal": 3000,
        "food": 5000,
        "transport": 2000,
    })
    assert r.status_code == 200

    r = client.get("/api/dashboard?month=2026-08")
    assert r.status_code == 200
    data = r.get_json()
    assert data["budget"]["income"] == 20000
    assert data["budget"]["food"] == 5000


def test_expense(client):
    r = client.post("/api/expenses", json={
        "amount": 120,
        "category": "Food",
        "description": "Lunch",
        "spent_on": "2026-08-20",
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
        "essential": False,
    })
    assert r.status_code == 200
    assert "remaining_after_purchase" in r.get_json()


def test_loan_advice(client):
    r = client.post("/api/loan-advice", json={
        "purpose": "Laptop / computer",
        "amount": 100000,
        "study_level": "Undergraduate",
    })
    assert r.status_code == 200
    assert "answer" in r.get_json()


def test_scholarship_guidance(client):
    r = client.post("/api/scholarships", json={
        "study_level": "Undergraduate",
        "field": "Computer Science",
        "need": "Both merit and need",
        "family_income": 400000,
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["suggestions"]
    assert "live list" in data["note"]


def test_budget_rejects_negative_values(client):
    r = client.post("/api/budget", json={
        "month": "2026-08",
        "income": -1,
    })
    assert r.status_code == 400


def test_expense_rejects_invalid_category(client):
    r = client.post("/api/expenses", json={
        "amount": 100,
        "category": "Not A Category",
        "spent_on": "2026-08-20",
    })
    assert r.status_code == 400
