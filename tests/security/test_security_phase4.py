import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Set env vars BEFORE importing api
os.environ["PRE_API_KEYS"] = "valid-key-1,valid-key-2"
os.environ["PRE_API_KEY_REQUIRED"] = "true"
os.environ["PRE_DB_PATH"] = "tests/security/test_security.db"

# Import app after setting env vars
from src.api import app
from src.db import RecommendationDB


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db_path = Path("tests/security/test_security.db")
    if db_path.exists():
        db_path.unlink()

    db = RecommendationDB(db_path)
    db.init_db()

    # Seed data
    db.upsert_recommendation(
        {
            "source_category": "Tactical Pants",
            "target_sku": "BELT-001",
            "target_name": "Tactical Belt",
            "score": 0.95,
            "reasoning": "Belts hold up pants.",
            "status": "active",
        }
    )

    # Seed with XSS payload
    db.upsert_recommendation(
        {
            "source_category": "XSS Category",
            "target_sku": "XSS-001",
            "target_name": "<script>alert(1)</script>",
            "score": 0.88,
            "reasoning": "<img src=x onerror=alert(1)>",
            "status": "active",
        }
    )

    yield db

    if db_path.exists():
        db_path.unlink()


def test_auth_bypass(client, db):
    """Verify API key enforcement."""
    # No key
    response = client.get("/v1/recommendations/category/Tactical%20Pants")
    assert response.status_code == 401

    # Invalid key
    response = client.get(
        "/v1/recommendations/category/Tactical%20Pants",
        headers={"X-API-Key": "invalid-key"},
    )
    assert response.status_code == 401

    # Valid key
    response = client.get(
        "/v1/recommendations/category/Tactical%20Pants",
        headers={"X-API-Key": "valid-key-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["recommendations"][0]["target_sku"] == "BELT-001"


def test_sql_injection_category(client, db):
    """Verify SQL injection resilience in category endpoint."""
    injection_payload = "' OR 1=1 --"
    response = client.get(
        f"/v1/recommendations/category/{injection_payload}",
        headers={"X-API-Key": "valid-key-1"},
    )
    # Should return 404 because no category matches literal string "' OR 1=1 --"
    # If injection worked, it might return all rows or 500 error
    assert response.status_code == 404
    assert "No active recommendations" in response.json()["error"]["message"]


def test_sql_injection_sku(client, db):
    """Verify SQL injection resilience in SKU endpoint."""
    injection_payload = "' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11,12,13,14 --"
    response = client.get(
        f"/v1/recommendations/sku/{injection_payload}",
        headers={"X-API-Key": "valid-key-1"},
    )
    assert response.status_code == 404


def test_validation_limits(client, db):
    """Verify input validation constraints."""
    # Limit too high
    response = client.get(
        "/v1/recommendations/category/Tactical%20Pants?limit=1000",
        headers={"X-API-Key": "valid-key-1"},
    )
    assert response.status_code == 422

    # Score out of bounds
    response = client.get(
        "/v1/recommendations/category/Tactical%20Pants?min_score=1.5",
        headers={"X-API-Key": "valid-key-1"},
    )
    assert response.status_code == 422


def test_stored_xss_retrieval(client, db):
    """Verify that stored XSS payloads are returned verbatim (JSON encoding saves them)."""
    response = client.get(
        "/v1/recommendations/category/XSS%20Category",
        headers={"X-API-Key": "valid-key-1"},
    )
    assert response.status_code == 200
    data = response.json()
    rec = data["recommendations"][0]

    # The payload is in the JSON string
    assert rec["target_name"] == "<script>alert(1)</script>"
    assert rec["reasoning"] == "<img src=x onerror=alert(1)>"

    # This confirms the API does NOT sanitize output.
    # Consumers MUST sanitize before rendering HTML.


def test_health_check_no_auth(client, db):
    """Verify health check is public."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
