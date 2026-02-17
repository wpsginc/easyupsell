from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from src.db import RecommendationDB


def _write_fixture_csv(path: Path) -> None:
    rows = []
    for i in range(10):
        rows.append(
            {
                "source_category": "Tactical Boots" if i < 5 else "Duty Belts",
                "recommended_sku": f"SKU-{i:03d}",
                "recommended_netsuite_id": "" if i == 3 else str(40000 + i),
                "recommended_name": f"Item {i}",
                "recommended_price": f"{49.99 + i}",
                "llm_confidence": "0.95" if i % 2 == 0 else "0.55",
                "llm_reason": f"reason-{i}",
                "relationship_type": "accessory",
                "enrichment_copurchase_count": str(i),
                "enrichment_margin": "0.42",
                "enrichment_velocity": str(100 + i),
                "llm_valid": "True" if i % 2 == 0 else "False",
            }
        )

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_csv_fixture_migration(tmp_path: Path):
    csv_path = tmp_path / "full_recommendations_v2.csv"
    db_path = tmp_path / "recommendations.db"
    _write_fixture_csv(csv_path)

    from scripts.migrate_csv_to_db import migrate_csv_to_db

    summary = migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)
    assert summary["total"] == 10
    assert summary["active"] == 5
    assert summary["pending_review"] == 5

    db = RecommendationDB(db_path)
    stats = db.get_stats()
    assert stats["total"] == 10
    assert stats["active"] == 5
    assert stats["pending_review"] == 5


def test_duplicate_handling_idempotent(tmp_path: Path):
    csv_path = tmp_path / "full_recommendations_v2.csv"
    db_path = tmp_path / "recommendations.db"
    _write_fixture_csv(csv_path)

    from scripts.migrate_csv_to_db import migrate_csv_to_db

    first = migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)
    second = migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)
    assert first["total"] == 10
    assert second["total"] == 10

    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        count = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    assert count == 10


def test_missing_netsuite_id_becomes_null(tmp_path: Path):
    csv_path = tmp_path / "full_recommendations_v2.csv"
    db_path = tmp_path / "recommendations.db"
    _write_fixture_csv(csv_path)

    from scripts.migrate_csv_to_db import migrate_csv_to_db

    migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)

    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        row = conn.execute(
            "SELECT target_netsuite_id FROM recommendations WHERE target_sku = ?",
            ("SKU-003",),
        ).fetchone()
    assert row["target_netsuite_id"] is None


def test_summary_output(tmp_path: Path):
    csv_path = tmp_path / "full_recommendations_v2.csv"
    db_path = tmp_path / "recommendations.db"
    _write_fixture_csv(csv_path)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_csv_to_db.py",
            "--csv",
            str(csv_path),
            "--db",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Migrated 10 recommendations" in result.stdout
    assert "active" in result.stdout
    assert "pending_review" in result.stdout
