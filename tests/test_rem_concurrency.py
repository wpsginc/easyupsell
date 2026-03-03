import threading
import time
from pathlib import Path
from scripts.migrate_csv_to_db import migrate_csv_to_db
import csv


def test_concurrent_writes(tmp_path: Path):
    """
    Test concurrency: Two threads writing to the same DB.
    SQLite with WAL mode should handle this, but let's verify no data loss.
    """
    db_path = tmp_path / "concurrent.db"
    csv_path_1 = tmp_path / "thread1.csv"
    csv_path_2 = tmp_path / "thread2.csv"

    # Generate 100 rows for each
    rows1 = [
        {
            "source_category": "Thread1",
            "recommended_sku": f"T1-{i}",
            "recommended_name": f"Item T1-{i}",
            "score": "0.9",
        }
        for i in range(100)
    ]
    rows2 = [
        {
            "source_category": "Thread2",
            "recommended_sku": f"T2-{i}",
            "recommended_name": f"Item T2-{i}",
            "score": "0.9",
        }
        for i in range(100)
    ]

    # Write CSVs
    def write_csv(path, rows):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_category",
                    "recommended_sku",
                    "recommended_name",
                    "score",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

    write_csv(csv_path_1, rows1)
    write_csv(csv_path_2, rows2)

    def run_migration(csv_file):
        migrate_csv_to_db(csv_file, None, db_path)

    t1 = threading.Thread(target=run_migration, args=(csv_path_1,))
    t2 = threading.Thread(target=run_migration, args=(csv_path_2,))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    from src.db import RecommendationDB

    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        count = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]

    assert count == 200, f"Expected 200 rows, got {count}. Concurrency issue?"
