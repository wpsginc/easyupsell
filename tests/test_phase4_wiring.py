from __future__ import annotations

from pathlib import Path

from easyupsell.core.analyzer import save_recommendations
from easyupsell.core.review import sync_review_decisions_to_db
from src.db import RecommendationDB


def test_analyzer_save_recommendations_dual_writes_csv_and_db(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "recommendations.csv"
    db_path = tmp_path / "recommendations.db"
    monkeypatch.setenv("PRE_DB_PATH", str(db_path))

    recommendations = [
        {
            "source_category": "Tactical Boots",
            "src_orders_6mo": 100,
            "src_revenue_6mo": 5000.0,
            "recommended_sku": "SKU-001",
            "recommended_netsuite_id": "42891",
            "same_category": False,
            "recommended_name": "Boot Upgrade",
            "recommended_price": 189.99,
            "recommended_categories": "Boots",
            "item_orders_6mo": 50,
            "item_units_6mo": 120,
            "item_revenue_6mo": 9300.0,
            "enrichment_copurchase_count": 47,
            "enrichment_margin": 0.42,
            "enrichment_velocity": 128,
            "llm_valid": True,
            "llm_confidence": 0.92,
            "relationship_type": "up_sell",
            "llm_reason": "Strong pairing",
        }
    ]

    save_recommendations(recommendations, csv_path)

    assert csv_path.exists()

    db = RecommendationDB(db_path)
    rows = db.get_active_by_category("Tactical Boots", min_score=0.0, limit=10)
    assert len(rows) == 1
    assert rows[0]["target_sku"] == "SKU-001"
    assert rows[0]["score"] == 0.92
    assert rows[0]["status"] == "active"


def test_review_sync_updates_status_in_db(tmp_path: Path):
    db_path = tmp_path / "recommendations.db"
    db = RecommendationDB(db_path)
    db.init_db()

    db.upsert_recommendation(
        {
            "source_category": "Tactical Boots",
            "target_sku": "SKU-001",
            "target_name": "Boot Upgrade",
            "score": 0.8,
            "status": "pending_review",
        }
    )
    db.upsert_recommendation(
        {
            "source_category": "Duty Belts",
            "target_sku": "SKU-002",
            "target_name": "Belt Upgrade",
            "score": 0.7,
            "status": "pending_review",
        }
    )

    scored_pairings = [
        {"source_category": "Tactical Boots", "target_sku": "SKU-001", "keep": True, "relevance_score": 4},
        {"source_category": "Duty Belts", "target_sku": "SKU-002", "keep": False, "relevance_score": 1},
    ]

    updated = sync_review_decisions_to_db(scored_pairings, db_path=db_path, min_score=2)
    assert updated == 2

    with db._connect(read_only=True) as conn:
        s1 = conn.execute(
            "SELECT status FROM recommendations WHERE source_category=? AND target_sku=?",
            ("Tactical Boots", "SKU-001"),
        ).fetchone()["status"]
        s2 = conn.execute(
            "SELECT status FROM recommendations WHERE source_category=? AND target_sku=?",
            ("Duty Belts", "SKU-002"),
        ).fetchone()["status"]

    assert s1 == "active"
    assert s2 == "rejected"
