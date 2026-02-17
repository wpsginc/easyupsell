from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DDL_SQL = """
CREATE TABLE IF NOT EXISTS recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,

    source_category   TEXT    NOT NULL,
    source_sku        TEXT    NULL,

    target_sku        TEXT    NOT NULL,
    target_netsuite_id TEXT   NULL,

    target_name       TEXT    NOT NULL,
    target_price      REAL    NULL,

    score             REAL    NOT NULL CHECK(score >= 0.0 AND score <= 1.0),
    reasoning         TEXT    NULL,
    relationship_type TEXT    NULL,

    status            TEXT    NOT NULL DEFAULT 'pending_review'
                      CHECK(status IN ('pending_review', 'active', 'rejected')),

    copurchase_count  INTEGER NOT NULL DEFAULT 0,
    margin            REAL    NOT NULL DEFAULT 0.0,
    velocity          REAL    NOT NULL DEFAULT 0.0,

    ns_sync_status    TEXT    NOT NULL DEFAULT 'pending'
                      CHECK(ns_sync_status IN ('pending', 'synced', 'failed')),
    ns_sync_at        TEXT    NULL,
    ns_sync_error     TEXT    NULL,

    created_at        TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at        TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    UNIQUE(source_category, target_sku)
);

CREATE INDEX IF NOT EXISTS idx_target_sku           ON recommendations(target_sku);
CREATE INDEX IF NOT EXISTS idx_target_netsuite_id   ON recommendations(target_netsuite_id);
CREATE INDEX IF NOT EXISTS idx_source_category      ON recommendations(source_category);
CREATE INDEX IF NOT EXISTS idx_status               ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_ns_sync              ON recommendations(status, ns_sync_status);

CREATE TRIGGER IF NOT EXISTS trg_recommendations_updated_at
AFTER UPDATE ON recommendations
FOR EACH ROW
BEGIN
    UPDATE recommendations SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""


UPSERT_SQL = """
INSERT INTO recommendations (
    source_category,
    source_sku,
    target_sku,
    target_netsuite_id,
    target_name,
    target_price,
    score,
    reasoning,
    relationship_type,
    status,
    copurchase_count,
    margin,
    velocity
) VALUES (
    :source_category,
    :source_sku,
    :target_sku,
    :target_netsuite_id,
    :target_name,
    :target_price,
    :score,
    :reasoning,
    :relationship_type,
    :status,
    :copurchase_count,
    :margin,
    :velocity
)
ON CONFLICT(source_category, target_sku) DO UPDATE SET
    source_sku = excluded.source_sku,
    target_netsuite_id = excluded.target_netsuite_id,
    target_name = excluded.target_name,
    target_price = excluded.target_price,
    score = excluded.score,
    reasoning = excluded.reasoning,
    relationship_type = excluded.relationship_type,
    status = excluded.status,
    copurchase_count = excluded.copurchase_count,
    margin = excluded.margin,
    velocity = excluded.velocity,
    ns_sync_status = CASE
        WHEN excluded.score != recommendations.score
          OR excluded.status != recommendations.status
        THEN 'pending'
        ELSE recommendations.ns_sync_status
    END;
"""


class RecommendationDB:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _apply_pragmas(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")

    def _connect(self, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        self._apply_pragmas(conn)
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(DDL_SQL)
            conn.commit()

    def upsert_recommendation(self, rec: dict[str, Any]) -> None:
        required = ["source_category", "target_sku", "target_name", "score"]
        missing = [k for k in required if rec.get(k) in (None, "")]
        if missing:
            raise ValueError(f"Missing required recommendation fields: {', '.join(missing)}")

        score = float(rec["score"])
        if score < 0.0 or score > 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        margin = float(rec.get("margin", rec.get("enrichment_margin", 0.0)) or 0.0)
        if margin > 1.0:
            margin = margin / 100.0

        payload = {
            "source_category": rec.get("source_category"),
            "source_sku": rec.get("source_sku"),
            "target_sku": rec.get("target_sku", rec.get("recommended_sku")),
            "target_netsuite_id": rec.get("target_netsuite_id", rec.get("recommended_netsuite_id")) or None,
            "target_name": rec.get("target_name", rec.get("recommended_name")),
            "target_price": rec.get("target_price", rec.get("recommended_price")),
            "score": score,
            "reasoning": rec.get("reasoning", rec.get("llm_reason")),
            "relationship_type": rec.get("relationship_type") or "complement",
            "status": rec.get("status", "pending_review"),
            "copurchase_count": int(rec.get("copurchase_count", rec.get("enrichment_copurchase_count", 0)) or 0),
            "margin": margin,
            "velocity": float(rec.get("velocity", rec.get("enrichment_velocity", 0.0)) or 0.0),
        }

        with self._connect() as conn:
            conn.execute(UPSERT_SQL, payload)
            conn.commit()

    def get_active_by_category(
        self, category: str, min_score: float = 0.7, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self._connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE source_category = ?
                  AND status = 'active'
                  AND score >= ?
                ORDER BY score DESC, copurchase_count DESC
                LIMIT ?
                """,
                (category, min_score, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_by_sku(self, sku: str) -> list[dict[str, Any]]:
        with self._connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE target_sku = ?
                  AND status = 'active'
                ORDER BY score DESC, copurchase_count DESC
                """,
                (sku,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_by_netsuite_id(self, ns_id: str) -> list[dict[str, Any]]:
        with self._connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE target_netsuite_id = ?
                  AND status = 'active'
                ORDER BY score DESC, copurchase_count DESC
                """,
                (ns_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_pending_sync(self, force_all: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
        where = "status = 'active'" if force_all else "status = 'active' AND ns_sync_status IN ('pending', 'failed')"
        limit_sql = f" LIMIT {int(limit)}" if limit else ""
        with self._connect(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM recommendations
                WHERE {where}
                ORDER BY id ASC
                {limit_sql}
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def update_sync_status(
        self, rec_id: int, status: str, synced_at: str | None = None, error: str | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE recommendations
                SET ns_sync_status = ?,
                    ns_sync_at = ?,
                    ns_sync_error = ?
                WHERE id = ?
                """,
                (status, synced_at, error, rec_id),
            )
            conn.commit()

    def update_status(self, rec_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE recommendations SET status = ?, ns_sync_status = 'pending' WHERE id = ?",
                (status, rec_id),
            )
            conn.commit()

    def update_status_by_keys(self, source_category: str, target_sku: str, status: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE recommendations
                SET status = ?, ns_sync_status = 'pending'
                WHERE source_category = ? AND target_sku = ?
                """,
                (status, source_category, target_sku),
            )
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict[str, Any]:
        with self._connect(read_only=True) as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM recommendations").fetchone()["c"]

            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM recommendations GROUP BY status"
            ).fetchall()
            by_status = {row["status"]: row["c"] for row in status_rows}

            sync_rows = conn.execute(
                "SELECT ns_sync_status, COUNT(*) AS c FROM recommendations GROUP BY ns_sync_status"
            ).fetchall()
            by_sync_status = {row["ns_sync_status"]: row["c"] for row in sync_rows}

        return {
            "total": total,
            "active": by_status.get("active", 0),
            "pending_review": by_status.get("pending_review", 0),
            "rejected": by_status.get("rejected", 0),
            "by_status": by_status,
            "by_sync_status": by_sync_status,
        }
