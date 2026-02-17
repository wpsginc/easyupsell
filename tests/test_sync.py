from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.db import RecommendationDB
from src.netsuite.client import (
    NetSuiteAuthError,
    NetSuiteServerError,
    NetSuiteValidationError,
)
from src.sync.netsuite import NetSuiteSyncJob


def _seed_sync_db(db_path: Path, with_orphan: bool = False, count: int = 2) -> RecommendationDB:
    db = RecommendationDB(db_path)
    db.init_db()
    for i in range(count):
        db.upsert_recommendation(
            {
                "source_category": f"Tactical Boots {i}",
                "target_sku": f"SKU-{i:03d}",
                "target_netsuite_id": None if (with_orphan and i == 0) else str(42000 + i),
                "target_name": f"Item {i}",
                "target_price": 100 + i,
                "score": 0.9,
                "reasoning": "R" * 5005,
                "relationship_type": "up_sell",
                "status": "active",
                "copurchase_count": 10,
                "margin": 0.42,
                "velocity": 120,
            }
        )
    return db


def test_dry_run_makes_zero_api_calls(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=2)
    ns = MagicMock()
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=40, batch_size=50, logs_dir=tmp_path / "logs")

    result = job.run(dry_run=True, force=False)
    assert ns.upsert_record.call_count == 0
    assert result.synced == 0
    assert result.failed == 0


def test_successful_sync_updates_db(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    ns = MagicMock()
    ns.upsert_record.return_value = {"id": "999"}
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=tmp_path / "logs")

    result = job.run(dry_run=False, force=False)
    assert result.synced == 1

    with db._connect(read_only=True) as conn:
        row = conn.execute("SELECT ns_sync_status, ns_sync_at, ns_sync_error FROM recommendations").fetchone()
    assert row["ns_sync_status"] == "synced"
    assert row["ns_sync_at"] is not None
    assert row["ns_sync_error"] is None


def test_retryable_error_retries_then_success(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    ns = MagicMock()
    ns.upsert_record.side_effect = [
        NetSuiteServerError(503, "busy"),
        NetSuiteServerError(503, "busy"),
        NetSuiteServerError(503, "busy"),
        {"id": "999"},
    ]
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=tmp_path / "logs")

    result = job.run(dry_run=False, force=False)
    assert result.synced == 1
    assert ns.upsert_record.call_count == 4


def test_terminal_error_marks_failed_and_writes_deadletter(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    ns = MagicMock()
    ns.upsert_record.side_effect = NetSuiteValidationError(422, "invalid field")
    logs_dir = tmp_path / "logs"
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=logs_dir)

    result = job.run(dry_run=False, force=False)
    assert result.failed == 1

    with db._connect(read_only=True) as conn:
        row = conn.execute("SELECT ns_sync_status, ns_sync_error FROM recommendations").fetchone()
    assert row["ns_sync_status"] == "failed"
    assert "invalid field" in (row["ns_sync_error"] or "")

    deadletter = logs_dir / "ns_sync_deadletter.jsonl"
    assert deadletter.exists()
    payload = json.loads(deadletter.read_text(encoding="utf-8").splitlines()[0])
    assert payload["http_status"] == 422


def test_auth_error_halts_job(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=2)
    ns = MagicMock()
    ns.upsert_record.side_effect = NetSuiteAuthError(401, "bad token")
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=tmp_path / "logs")

    result = job.run(dry_run=False, force=False)
    assert result.failed == 1
    assert ns.upsert_record.call_count == 1

    with db._connect(read_only=True) as conn:
        statuses = conn.execute("SELECT ns_sync_status FROM recommendations ORDER BY id").fetchall()
    assert statuses[0]["ns_sync_status"] == "failed"
    assert statuses[1]["ns_sync_status"] == "pending"


def test_per_request_throttle(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    ns = MagicMock()
    ns.upsert_record.return_value = {"id": "999"}
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=40, batch_size=10, logs_dir=tmp_path / "logs")

    with patch("src.sync.netsuite.time.sleep") as sleep_mock:
        job.run(dry_run=False, force=False)
    assert sleep_mock.call_count >= 1
    assert sleep_mock.call_args[0][0] >= 0


def test_orphan_skipped_and_logged(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", with_orphan=True, count=1)
    ns = MagicMock()
    logs_dir = tmp_path / "logs"
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=logs_dir)

    result = job.run(dry_run=False, force=False)
    assert result.orphaned == 1
    assert ns.upsert_record.call_count == 0

    orphan_file = logs_dir / "ns_sync_orphans.jsonl"
    assert orphan_file.exists()
    payload = json.loads(orphan_file.read_text(encoding="utf-8").splitlines()[0])
    assert payload["reason"] == "missing target_netsuite_id"


def test_payload_margin_conversion_and_reasoning_truncation(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    ns = MagicMock()
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=tmp_path / "logs")

    rec = db.get_pending_sync()[0]
    payload = job._build_payload(rec)
    assert payload["custrecord_pre_margin"] == 42.0
    assert len(payload["custrecord_pre_reason"]) == 4000


def test_force_flag_includes_synced_records(tmp_path: Path):
    db = _seed_sync_db(tmp_path / "recommendations.db", count=1)
    with db._connect() as conn:
        row = conn.execute("SELECT id FROM recommendations").fetchone()
    db.update_sync_status(row["id"], "synced", synced_at="2026-02-17T00:00:00Z", error=None)

    ns = MagicMock()
    ns.upsert_record.return_value = {"id": "999"}
    job = NetSuiteSyncJob(db=db, ns_client=ns, max_rpm=1000, batch_size=10, logs_dir=tmp_path / "logs")
    job.run(dry_run=False, force=True)

    assert ns.upsert_record.call_count == 1


def test_external_id_url_encoded_in_client_upsert():
    from src.netsuite.auth import NetSuiteCredentials
    from src.netsuite.client import NetSuiteClient

    creds = NetSuiteCredentials(
        account_id="5001161_SB1",
        consumer_key="ck",
        consumer_secret="cs",
        token_id="tk",
        token_secret="ts",
    )
    client = NetSuiteClient(creds)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "1"}
    mock_response.raise_for_status.return_value = None
    client.session.request = MagicMock(return_value=mock_response)

    client.upsert_record("customrecord_wpsg_pre_rec", "Tactical Boots::SKU 1", {"x": 1})
    called_url = client.session.request.call_args.kwargs["url"]
    assert "Tactical%20Boots%3A%3ASKU%201" in called_url
