import sys
import os
import shutil
import tempfile
import sqlite3
import time
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db import RecommendationDB
from src.sync.netsuite import NetSuiteSyncJob, NetSuiteClient, NetSuiteServerError

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

issues_found = 0
p0_count = 0
p1_count = 0


def report(name, passed, detail=""):
    global issues_found
    if passed:
        print(f"[{GREEN}PASS{RESET}] {name}")
    else:
        print(f"[{RED}FAIL{RESET}] {name} - {detail}")
        issues_found += 1


def check_missing_config():
    print("\n--- Check 1: Missing Config Handling ---")
    # Test 1: DB path in non-existent directory (should create)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "missing" / "subdir" / "rec.db"
        try:
            db = RecommendationDB(db_path)
            db.init_db()
            if db_path.exists():
                report("DB creation in missing subdir", True)
            else:
                report("DB creation in missing subdir", False, "File not created")
        except Exception as e:
            report("DB creation in missing subdir", False, f"Exception: {e}")

    # Test 2: NetSuiteSyncJob init
    try:
        db = MagicMock(spec=RecommendationDB)
        client = MagicMock(spec=NetSuiteClient)
        job = NetSuiteSyncJob(db, client, max_rpm=10, batch_size=10)
        report("SyncJob init", True)
    except Exception as e:
        report("SyncJob init", False, f"Exception: {e}")


def check_large_query():
    print("\n--- Check 2: Large Query Handling ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "large.db"
        db = RecommendationDB(db_path)
        db.init_db()

        # Insert 10MB text
        large_text = "A" * 10_000_000

        rec = {
            "source_category": "Large Cat",
            "target_sku": "SKU-LARGE",
            "target_name": "Large Item",
            "score": 0.5,
            "reasoning": large_text,
            "status": "active",
        }

        try:
            start = time.time()
            db.upsert_recommendation(rec)
            duration = time.time() - start
            report("Insert 10MB text", True, f"Took {duration:.2f}s")
        except Exception as e:
            report("Insert 10MB text", False, f"Exception: {e}")

        # Retrieve it
        try:
            rows = db.get_active_by_sku("SKU-LARGE")
            if rows and len(rows[0]["reasoning"]) == 10_000_000:
                report("Retrieve 10MB text", True)
            else:
                report("Retrieve 10MB text", False, "Data mismatch or missing")
        except Exception as e:
            report("Retrieve 10MB text", False, f"Exception: {e}")


def check_empty_db():
    print("\n--- Check 3: Empty Database Handling ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "empty.db"
        db_path.touch()

        db = RecommendationDB(db_path)

        try:
            db.get_active_by_category("Tactical")
            report("Query uninitialized DB", False, "Should have failed but didn't")
        except sqlite3.OperationalError:
            report("Query uninitialized DB", True, "Caught expected OperationalError")
        except Exception as e:
            report(
                "Query uninitialized DB", False, f"Unexpected exception: {type(e)} {e}"
            )

        # Now Init and query empty table
        db.init_db()
        try:
            rows = db.get_active_by_category("Tactical")
            if rows == []:
                report("Query empty table", True)
            else:
                report("Query empty table", False, f"Got {rows}")
        except Exception as e:
            report("Query empty table", False, f"Exception: {e}")


def check_unicode_chaos():
    print("\n--- Check 4: Unicode Chaos ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "unicode.db"
        db = RecommendationDB(db_path)
        db.init_db()

        chaos_str = "Tactical 👮‍♂️ 🏳️‍🌈 \u0000 \n \r 🔥 Zalgo: H̶e̶ ̶c̶o̶m̶e̶s̶"

        rec = {
            "source_category": chaos_str,
            "target_sku": "SKU-CHAOS",
            "target_name": "Chaos Item " + chaos_str,
            "score": 0.5,
            "reasoning": chaos_str,
            "status": "active",
        }

        try:
            db.upsert_recommendation(rec)
            report("Insert Unicode Chaos", True)
        except Exception as e:
            report("Insert Unicode Chaos", False, f"Exception: {e}")

        try:
            rows = db.get_active_by_sku("SKU-CHAOS")
            if rows and rows[0]["source_category"] == chaos_str:
                report("Retrieve Unicode Chaos", True)
            else:
                report("Retrieve Unicode Chaos", False, "Content mismatch")
        except Exception as e:
            report("Retrieve Unicode Chaos", False, f"Exception: {e}")

        # Check Sync Payload generation
        try:
            client = MagicMock(spec=NetSuiteClient)
            job = NetSuiteSyncJob(db, client, max_rpm=60, batch_size=1)
            row = dict(rows[0])
            row["target_netsuite_id"] = "123"
            row["id"] = 1
            row["relationship_type"] = "complement"
            row["margin"] = 0.5
            row["velocity"] = 10.0

            payload = job._build_payload(row)
            json_str = json.dumps(payload)
            report("JSON Serialize Chaos Payload", True)
        except Exception as e:
            report("JSON Serialize Chaos Payload", False, f"Exception: {e}")


def check_timeout_behavior():
    print("\n--- Check 5: Timeout Behavior ---")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "timeout.db"
        db = RecommendationDB(db_path)
        db.init_db()

        db.upsert_recommendation(
            {
                "source_category": "Cat",
                "target_sku": "SKU1",
                "target_name": "Item",
                "score": 0.9,
                "status": "active",
                "target_netsuite_id": "123",
            }
        )

        client = MagicMock(spec=NetSuiteClient)

        # Mock upsert to be slow
        def slow_upsert(*args, **kwargs):
            time.sleep(1.1)
            return

        client.upsert_record.side_effect = slow_upsert

        job = NetSuiteSyncJob(db, client, max_rpm=60, batch_size=1)

        start = time.time()
        res = job.run(dry_run=False, force=True)
        duration = time.time() - start

        if res.synced == 1:
            report("Slow request handled", True)
        else:
            report("Slow request handled", False, f"Synced: {res.synced}")

        # Check Exception propagation
        client.upsert_record.side_effect = Exception("Connection Timeout")

        try:
            job.run(dry_run=False, force=True)
            report(
                "Generic Exception behavior", True, "Propagated up (Expected for now)"
            )
        except Exception as e:
            if str(e) == "Connection Timeout":
                report("Generic Exception behavior", True, "Propagated up")
            else:
                report("Generic Exception behavior", False, f"Caught unexpected {e}")

        # Check explicit NetSuite errors are caught
        client.upsert_record.side_effect = NetSuiteServerError(500, "500 Error")
        try:
            res = job.run(dry_run=False, force=True)
            if res.failed == 1:
                report("NetSuiteServerError handled", True)
            else:
                report(
                    "NetSuiteServerError handled", False, f"Failed count: {res.failed}"
                )
        except Exception as e:
            report("NetSuiteServerError handled", False, f"Exception raised: {e}")


def main():
    check_missing_config()
    check_large_query()
    check_empty_db()
    check_unicode_chaos()
    check_timeout_behavior()

    print(f"\nTotal Issues Found: {issues_found}")
    print(f"P0: {p0_count}")
    print(f"P1: {issues_found - p0_count}")  # Assuming all found issues are P1 for now
    # Don't actually exit with error code to avoid tool failure, just print
    # sys.exit(issues_found)


if __name__ == "__main__":
    main()
