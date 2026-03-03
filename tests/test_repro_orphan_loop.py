import pytest
from pathlib import Path
from src.db import RecommendationDB
from src.sync.netsuite import NetSuiteSyncJob
from unittest.mock import MagicMock


def test_infinite_orphan_loop(tmp_path):
    db_path = tmp_path / "repro.db"
    db = RecommendationDB(db_path)
    db.init_db()

    # Seed a record with missing target_netsuite_id
    db.upsert_recommendation(
        {
            "source_category": "Boots",
            "target_sku": "BOOT-001",
            "target_netsuite_id": None,  # Missing!
            "target_name": "Boot",
            "score": 0.9,
            "status": "active",
        }
    )

    # Verify initial state
    recs = db.get_pending_sync()
    assert len(recs) == 1
    assert recs[0]["ns_sync_status"] == "pending"

    # Run sync job
    ns_client = MagicMock()
    job = NetSuiteSyncJob(
        db, ns_client, max_rpm=60, batch_size=10, logs_dir=tmp_path / "logs"
    )

    # Run 1
    result1 = job.run(dry_run=False, force=False)
    assert result1.orphaned == 1

    # Verify it's STILL pending
    recs_after = db.get_pending_sync()
    assert len(recs_after) == 1
    assert recs_after[0]["ns_sync_status"] == "pending"

    # Run 2
    result2 = job.run(dry_run=False, force=False)
    assert result2.orphaned == 1  # Caught it again!

    # Check logs
    log_file = tmp_path / "logs" / "ns_sync_orphans.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2  # Logged twice
