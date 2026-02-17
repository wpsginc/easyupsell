from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.db import RecommendationDB
from src.netsuite.client import (
    NetSuiteAuthError,
    NetSuiteClient,
    NetSuiteServerError,
    NetSuiteValidationError,
)


@dataclass
class SyncResult:
    synced: int
    failed: int
    orphaned: int
    skipped: int
    duration: timedelta
    job_id: str


class NetSuiteSyncJob:
    def __init__(
        self,
        db: RecommendationDB,
        ns_client: NetSuiteClient,
        max_rpm: int,
        batch_size: int,
        logs_dir: str | Path = "logs",
        record_type: str = "customrecord_wpsg_pre_rec",
    ):
        self.db = db
        self.ns_client = ns_client
        self.max_rpm = max(1, int(max_rpm))
        self.batch_size = max(1, int(batch_size))
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.record_type = record_type
        self.min_interval = 60.0 / float(self.max_rpm)

    def run(self, dry_run: bool, force: bool) -> SyncResult:
        started = time.monotonic()
        job_id = f"sync-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        records = self.db.get_pending_sync(force_all=force)

        synced = 0
        failed = 0
        orphaned = 0
        skipped = 0

        for rec in records:
            if not rec.get("target_netsuite_id"):
                orphaned += 1
                self._append_jsonl(
                    self.logs_dir / "ns_sync_orphans.jsonl",
                    {
                        "timestamp": self._now_iso(),
                        "job_id": job_id,
                        "rec_id": rec["id"],
                        "source_category": rec["source_category"],
                        "target_sku": rec["target_sku"],
                        "reason": "missing target_netsuite_id",
                    },
                )
                continue

            payload = self._build_payload(rec)
            external_id = self._build_external_id(rec)

            if dry_run:
                skipped += 1
                continue

            state = self._sync_record(rec, external_id, payload, job_id)
            if state == "synced":
                synced += 1
            elif state == "failed":
                failed += 1
            elif state == "auth_halt":
                failed += 1
                break

        return SyncResult(
            synced=synced,
            failed=failed,
            orphaned=orphaned,
            skipped=skipped,
            duration=timedelta(seconds=time.monotonic() - started),
            job_id=job_id,
        )

    def _sync_record(self, rec: dict[str, Any], external_id: str, payload: dict[str, Any], job_id: str) -> str:
        backoff_seconds = [0, 2, 4, 8]
        last_error = "unknown"

        for attempt in range(1, 5):
            if attempt > 1:
                time.sleep(backoff_seconds[attempt - 1])

            request_started = time.monotonic()
            try:
                self.ns_client.upsert_record(self.record_type, external_id, payload)
                self.db.update_sync_status(rec["id"], "synced", synced_at=self._now_iso(), error=None)
                return "synced"
            except NetSuiteAuthError as exc:
                last_error = str(exc)
                self._mark_failed(rec, payload, job_id, exc.status_code, str(exc))
                return "auth_halt"
            except NetSuiteValidationError as exc:
                last_error = str(exc)
                self._mark_failed(rec, payload, job_id, exc.status_code, str(exc))
                return "failed"
            except NetSuiteServerError as exc:
                last_error = str(exc)
                if attempt == 4:
                    self._mark_failed(rec, payload, job_id, exc.status_code, str(exc))
                    return "failed"
            finally:
                elapsed = time.monotonic() - request_started
                sleep_time = max(0.0, self.min_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        self._mark_failed(rec, payload, job_id, 500, last_error)
        return "failed"

    def _build_external_id(self, rec: dict[str, Any]) -> str:
        return f"{rec['source_category']}::{rec['target_sku']}"

    def _build_payload(self, rec: dict[str, Any]) -> dict[str, Any]:
        relationship_type = rec.get("relationship_type") or "complement"
        margin_pct = float(rec.get("margin") or 0.0) * 100.0
        velocity = int(float(rec.get("velocity") or 0.0))
        reasoning = (rec.get("reasoning") or "")[:4000]
        synced_at = self._now_iso()

        return {
            "custrecord_pre_external_id": self._build_external_id(rec),
            "custrecord_pre_source_cat": rec["source_category"],
            "custrecord_pre_target_item": {"id": str(rec["target_netsuite_id"])},
            "custrecord_pre_score": float(rec.get("score") or 0.0),
            "custrecord_pre_reason": reasoning,
            "custrecord_pre_type": {"value": relationship_type},
            "custrecord_pre_active": rec.get("status") == "active",
            "custrecord_pre_margin": margin_pct,
            "custrecord_pre_velocity": velocity,
            "custrecord_pre_synced_at": synced_at,
        }

    def _mark_failed(
        self,
        rec: dict[str, Any],
        payload: dict[str, Any],
        job_id: str,
        http_status: int,
        error: str,
    ) -> None:
        self.db.update_sync_status(rec["id"], "failed", synced_at=None, error=error)
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._append_jsonl(
            self.logs_dir / "ns_sync_deadletter.jsonl",
            {
                "timestamp": self._now_iso(),
                "job_id": job_id,
                "rec_id": rec["id"],
                "external_id": self._build_external_id(rec),
                "http_status": http_status,
                "error": error,
                "payload_hash": f"sha256:{payload_hash}",
            },
        )

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, separators=(",", ":")) + "\n")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
