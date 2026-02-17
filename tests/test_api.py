from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.db import RecommendationDB


def _seed_db(db_path: Path):
    db = RecommendationDB(db_path)
    db.init_db()

    db.upsert_recommendation(
        {
            "source_category": "Tactical Boots",
            "target_sku": "SKU-001",
            "target_netsuite_id": "42891",
            "target_name": "Boot Upgrade A",
            "target_price": 149.0,
            "score": 0.9,
            "reasoning": "high",
            "relationship_type": "up_sell",
            "status": "active",
            "copurchase_count": 10,
            "margin": 0.4,
            "velocity": 25,
        }
    )
    db.upsert_recommendation(
        {
            "source_category": "Tactical Boots",
            "target_sku": "SKU-002",
            "target_netsuite_id": "42892",
            "target_name": "Boot Upgrade B",
            "target_price": 99.0,
            "score": 0.5,
            "reasoning": "low",
            "relationship_type": "accessory",
            "status": "active",
            "copurchase_count": 3,
            "margin": 0.2,
            "velocity": 8,
        }
    )
    db.upsert_recommendation(
        {
            "source_category": "Tactical Boots",
            "target_sku": "SKU-003",
            "target_netsuite_id": "42893",
            "target_name": "Rejected Item",
            "target_price": 79.0,
            "score": 0.95,
            "reasoning": "no",
            "relationship_type": "complement",
            "status": "rejected",
            "copurchase_count": 1,
            "margin": 0.1,
            "velocity": 2,
        }
    )


def _make_client(monkeypatch, db_path: Path):
    monkeypatch.setenv("PRE_DB_PATH", str(db_path))
    monkeypatch.setenv("PRE_API_KEYS", "test-key")

    from src.api import create_app

    app = create_app()
    return TestClient(app)


def test_health_no_auth(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    client = _make_client(monkeypatch, db_path)

    res = client.get("/v1/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["counts"]["total"] == 3
    assert "request_id" in payload


def test_missing_and_invalid_api_key(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    client = _make_client(monkeypatch, db_path)

    missing = client.get("/v1/recommendations/category/Tactical Boots")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"
    assert "request_id" in missing.json()

    invalid = client.get(
        "/v1/recommendations/category/Tactical Boots",
        headers={"X-API-Key": "wrong"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "unauthorized"
    assert "request_id" in invalid.json()


def test_valid_api_key_and_category_filters(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    client = _make_client(monkeypatch, db_path)

    res = client.get(
        "/v1/recommendations/category/Tactical Boots?min_score=0.7&limit=1",
        headers={"X-API-Key": "test-key"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["count"] == 1
    assert payload["recommendations"][0]["target_sku"] == "SKU-001"
    assert payload["recommendations"][0]["score"] >= 0.7
    assert "request_id" in payload


def test_unknown_category_returns_404(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    client = _make_client(monkeypatch, db_path)

    res = client.get(
        "/v1/recommendations/category/Unknown Category",
        headers={"X-API-Key": "test-key"},
    )
    assert res.status_code == 404
    payload = res.json()
    assert payload["error"]["code"] == "not_found"
    assert "request_id" in payload


def test_sku_and_netsuite_endpoints(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    client = _make_client(monkeypatch, db_path)

    sku_res = client.get(
        "/v1/recommendations/sku/SKU-001",
        headers={"X-API-Key": "test-key"},
    )
    assert sku_res.status_code == 200
    assert sku_res.json()["count"] == 1
    assert sku_res.json()["recommendations"][0]["target_sku"] == "SKU-001"

    ns_res = client.get(
        "/v1/recommendations/netsuite/42891",
        headers={"X-API-Key": "test-key"},
    )
    assert ns_res.status_code == 200
    assert ns_res.json()["count"] == 1
    assert ns_res.json()["recommendations"][0]["target_netsuite_id"] == "42891"


def test_db_read_only_guard(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    _seed_db(db_path)
    _make_client(monkeypatch, db_path)

    from src.api import open_readonly_connection

    with open_readonly_connection(db_path) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO recommendations (source_category, target_sku, target_name, score) VALUES (?, ?, ?, ?)",
                ("A", "B", "C", 0.9),
            )
