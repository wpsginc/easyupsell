import csv
import math
from pathlib import Path
from scripts.migrate_csv_to_db import migrate_csv_to_db
from src.db import RecommendationDB


def test_margin_corruption_above_100_percent(tmp_path: Path):
    """
    BUG: Margins > 100% (e.g., 200) are treated as percentage values > 1.0,
    but then re-divided by 100 in upsert logic?
    Let's trace:
    Input: "200"
    _parse_margin("200") -> 200.0 (float) -> 200 > 1.0 -> 200/100 -> 2.0.
    db.upsert_recommendation({"margin": 2.0})
    margin = 2.0
    if margin > 1.0: margin = 2.0 / 100.0 = 0.02.
    Result: 0.02 (2%). Expected: 2.0 (200%) or at least 1.0 if capped.
    """
    csv_path = tmp_path / "margin_test.csv"
    db_path = tmp_path / "margin_test.db"

    rows = [
        {
            "source_category": "High Margin",
            "recommended_sku": "SKU-200",
            "recommended_name": "Item 200",
            "llm_confidence": "1.0",
            "enrichment_margin": "200",  # 200% margin
            "llm_valid": "True",
        }
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)

    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT margin FROM recommendations WHERE target_sku='SKU-200'"
        ).fetchone()
        margin = row["margin"]

    # We expect 2.0 (200%), but suspect it will be 0.02
    # If it is 0.02, we have confirmed the bug.
    # The test should FAIL if the bug exists, or PASS if I assert the buggy behavior (to confirm it).
    # Since I want to report the bug, I will assert the EXPECTED behavior (2.0) and expect failure.
    assert margin == 2.0, f"Margin corrupted! Expected 2.0, got {margin}"


def test_nan_score_persistence(tmp_path: Path):
    """
    BUG: NaN scores might bypass clamps and be stored as NaN.
    """
    csv_path = tmp_path / "nan_test.csv"
    db_path = tmp_path / "nan_test.db"

    rows = [
        {
            "source_category": "NaN Category",
            "recommended_sku": "SKU-NaN",
            "recommended_name": "Item NaN",
            "llm_confidence": "nan",
            "llm_valid": "True",
        }
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)

    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT score FROM recommendations WHERE target_sku='SKU-NaN'"
        ).fetchone()
        score = row["score"]

    # Python float('nan') comparison is always False.
    # Check if it is valid float and not nan
    assert not math.isnan(score), f"Score stored as NaN! Got {score}"
    assert 0.0 <= score <= 1.0, f"Score out of bounds! Got {score}"
