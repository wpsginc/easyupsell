import pytest
from pathlib import Path
from src.db import RecommendationDB


def test_margin_scaling_ambiguity(tmp_path):
    db = RecommendationDB(tmp_path / "margin.db")
    db.init_db()

    # Case 1: 50% margin
    # Input: 0.5 (decimal)
    db.upsert_recommendation(
        {
            "source_category": "C1",
            "target_sku": "S1",
            "target_name": "N1",
            "score": 0.9,
            "margin": 0.5,
        }
    )
    rec1 = db.get_active_by_sku("S1")
    # Status default is pending_review, so we need to fetch it differently or set status active
    # actually upsert sets status to pending_review by default.
    # Let's use internal connection to verify
    with db._connect() as conn:
        row1 = conn.execute(
            "SELECT margin FROM recommendations WHERE target_sku='S1'"
        ).fetchone()
        assert row1["margin"] == 0.5

    # Case 2: 50% margin passed as 50
    db.upsert_recommendation(
        {
            "source_category": "C2",
            "target_sku": "S2",
            "target_name": "N2",
            "score": 0.9,
            "margin": 50,
        }
    )
    with db._connect() as conn:
        row2 = conn.execute(
            "SELECT margin FROM recommendations WHERE target_sku='S2'"
        ).fetchone()
        assert row2["margin"] == 0.5

    # Case 3: 150% margin (High margin item)
    # Input: 1.5 (decimal)
    db.upsert_recommendation(
        {
            "source_category": "C3",
            "target_sku": "S3",
            "target_name": "N3",
            "score": 0.9,
            "margin": 1.5,
        }
    )
    with db._connect() as conn:
        row3 = conn.execute(
            "SELECT margin FROM recommendations WHERE target_sku='S3'"
        ).fetchone()
        # If the code treats 1.5 as 1.5%, it will be 0.015
        # If it treats it as 150%, it should be 1.5
        print(f"Margin 1.5 resulted in: {row3['margin']}")
        # I expect this to fail if my hypothesis is correct (it will be 0.015)
        # But is 150% margin valid? Yes.
        # If I want 150%, I must pass 150?

    # Case 4: 150% margin passed as 150
    db.upsert_recommendation(
        {
            "source_category": "C4",
            "target_sku": "S4",
            "target_name": "N4",
            "score": 0.9,
            "margin": 150,
        }
    )
    with db._connect() as conn:
        row4 = conn.execute(
            "SELECT margin FROM recommendations WHERE target_sku='S4'"
        ).fetchone()
        print(f"Margin 150 resulted in: {row4['margin']}")
        assert row4["margin"] == 1.5
