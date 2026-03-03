from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.migrate_csv_to_db import migrate_csv_to_db
from src.db import RecommendationDB


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_migration.db"


@pytest.fixture
def malformed_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "malformed.csv"
    headers = [
        "source_category",
        "recommended_sku",
        "recommended_name",
        "llm_confidence",
        "llm_valid",
        "llm_reason",
    ]
    rows = [
        {
            "source_category": "Valid Category 1",
            "recommended_sku": "SKU1",
            "recommended_name": "Product 1",
            "llm_confidence": "0.9",
            "llm_valid": "true",
            "llm_reason": "Good match",
        },
        {
            "source_category": "",  # MISSING REQUIRED FIELD
            "recommended_sku": "SKU2",
            "recommended_name": "Product 2",
            "llm_confidence": "0.8",
            "llm_valid": "true",
            "llm_reason": "Missing category",
        },
        {
            "source_category": "Valid Category 3",
            "recommended_sku": "SKU3",
            "recommended_name": "Product 3",
            "llm_confidence": "0.7",
            "llm_valid": "true",
            "llm_reason": "Another good match",
        },
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def test_migration_skips_malformed_rows(temp_db: Path, malformed_csv: Path) -> None:
    # 1. Execution: Run migrate_csv_to_db
    # Expectation: The script should not raise an unhandled exception.
    summary = migrate_csv_to_db(csv_path=malformed_csv, xlsx_path=None, db_path=temp_db)

    # 2. Expectation: summary counts should reflect the skipped row
    assert summary["total"] == 2
    assert summary["errors"] == 1
    assert summary["active"] == 2

    # 3. Expectation: Valid rows should be successfully inserted into the DB
    db = RecommendationDB(temp_db)
    recs1 = db.get_active_by_category("Valid Category 1")
    assert len(recs1) == 1
    assert recs1[0]["target_sku"] == "SKU1"

    recs3 = db.get_active_by_category("Valid Category 3")
    assert len(recs3) == 1
    assert recs3[0]["target_sku"] == "SKU3"

    # Verify Row 2 is NOT there
    with db._connect(read_only=True) as conn:
        row2 = conn.execute(
            "SELECT * FROM recommendations WHERE target_sku = 'SKU2'"
        ).fetchone()
        assert row2 is None
