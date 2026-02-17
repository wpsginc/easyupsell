from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from src.db import RecommendationDB


def _base_rec(**overrides):
    rec = {
        "source_category": "Tactical Boots",
        "target_sku": "SKU-001",
        "target_netsuite_id": "42891",
        "target_name": "Boot Upgrade",
        "target_price": 189.99,
        "score": 0.92,
        "reasoning": "Strong complement",
        "relationship_type": "up_sell",
        "status": "active",
        "copurchase_count": 47,
        "margin": 0.42,
        "velocity": 128,
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def db(tmp_path: Path) -> RecommendationDB:
    database = RecommendationDB(tmp_path / "recommendations.db")
    database.init_db()
    return database


def test_schema_creation(db: RecommendationDB):
    with db._connect() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(recommendations)")]
        assert "source_category" in columns
        assert "target_sku" in columns
        assert "score" in columns
        assert "status" in columns
        assert "ns_sync_status" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(recommendations)")}
        assert "idx_target_sku" in indexes
        assert "idx_target_netsuite_id" in indexes
        assert "idx_source_category" in indexes
        assert "idx_status" in indexes
        assert "idx_ns_sync" in indexes


def test_unique_constraint_and_upsert_updates_same_row(db: RecommendationDB):
    db.upsert_recommendation(_base_rec(score=0.8))
    db.upsert_recommendation(_base_rec(score=0.95, reasoning="Updated reason"))

    with db._connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM recommendations").fetchone()["c"]
        assert count == 1

        row = conn.execute(
            "SELECT score, reasoning FROM recommendations WHERE source_category=? AND target_sku=?",
            ("Tactical Boots", "SKU-001"),
        ).fetchone()
        assert row["score"] == pytest.approx(0.95)
        assert row["reasoning"] == "Updated reason"


def test_score_bounds_check_constraint(db: RecommendationDB):
    with db._connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendations (
                    source_category, target_sku, target_name, score
                ) VALUES (?, ?, ?, ?)
                """,
                ("A", "B", "C", -0.1),
            )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendations (
                    source_category, target_sku, target_name, score
                ) VALUES (?, ?, ?, ?)
                """,
                ("A2", "B2", "C2", 1.1),
            )


def test_status_enum_check_constraint(db: RecommendationDB):
    with db._connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendations (
                    source_category, target_sku, target_name, score, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("A", "B", "C", 0.9, "invalid"),
            )


def test_updated_at_trigger(db: RecommendationDB):
    db.upsert_recommendation(_base_rec())

    with db._connect() as conn:
        before = conn.execute(
            "SELECT id, created_at, updated_at FROM recommendations WHERE source_category=? AND target_sku=?",
            ("Tactical Boots", "SKU-001"),
        ).fetchone()

        time.sleep(1.1)
        conn.execute(
            "UPDATE recommendations SET score=? WHERE id=?",
            (0.99, before["id"]),
        )
        after = conn.execute(
            "SELECT created_at, updated_at FROM recommendations WHERE id=?",
            (before["id"],),
        ).fetchone()

    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] > before["updated_at"]


def test_ns_sync_status_resets_to_pending_when_score_changes(db: RecommendationDB):
    db.upsert_recommendation(_base_rec(score=0.8, status="active"))
    row = db.get_active_by_category("Tactical Boots")[0]
    db.update_sync_status(row["id"], "synced", synced_at="2026-02-17T02:15:33Z", error=None)

    db.upsert_recommendation(_base_rec(score=0.9, status="active"))

    with db._connect() as conn:
        status = conn.execute(
            "SELECT ns_sync_status FROM recommendations WHERE source_category=? AND target_sku=?",
            ("Tactical Boots", "SKU-001"),
        ).fetchone()["ns_sync_status"]
    assert status == "pending"


def test_wal_mode_active(db: RecommendationDB):
    with db._connect() as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    assert mode.lower() == "wal"


def test_read_only_connection_rejects_writes(db: RecommendationDB):
    with db._connect(read_only=True) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                """
                INSERT INTO recommendations (
                    source_category, target_sku, target_name, score
                ) VALUES (?, ?, ?, ?)
                """,
                ("X", "Y", "Z", 0.8),
            )


def test_concurrent_read_write_succeeds(db: RecommendationDB):
    errors = []
    done = threading.Event()

    def writer():
        try:
            for i in range(50):
                db.upsert_recommendation(
                    _base_rec(target_sku=f"SKU-{i:03d}", score=0.7 + (i % 10) * 0.01)
                )
                time.sleep(0.005)
        except Exception as exc:  # pragma: no cover - assertion below handles this
            errors.append(exc)
        finally:
            done.set()

    def reader():
        try:
            while not done.is_set():
                with db._connect(read_only=True) as conn:
                    conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()
                time.sleep(0.002)
        except Exception as exc:  # pragma: no cover - assertion below handles this
            errors.append(exc)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors
