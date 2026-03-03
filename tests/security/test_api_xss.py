
import csv
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from scripts.migrate_csv_to_db import migrate_csv_to_db
from src.api import create_app

def test_stored_xss_via_api(tmp_path):
    """
    VULN-003: Stored XSS via API
    Demonstrates that the API serves malicious payloads (e.g. <script>) 
    stored in the DB without sanitization.
    """
    # 1. Setup paths
    csv_path = tmp_path / "xss.csv"
    db_path = tmp_path / "xss.db"
    
    # 2. Create malicious CSV with XSS payload
    payload = "<script>alert(1)</script>"
    rows = [
        {
            "source_category": "Safe Category",
            "recommended_sku": "SKU-XSS",
            "recommended_name": payload,  # XSS in product name
            "recommended_price": "10.00",
            "llm_confidence": "1.0",
            "llm_valid": "True",
            "relationship_type": "accessory"
        }
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # 3. Migrate to DB
    migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)
    
    # 4. Initialize API with this DB
    os.environ["PRE_DB_PATH"] = str(db_path)
    os.environ["PRE_API_KEYS"] = "test-key"
    app = create_app()
    client = TestClient(app)
    
    # 5. Query API
    response = client.get(
        "/v1/recommendations/sku/SKU-XSS",
        headers={"X-API-Key": "test-key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # 6. Verify Payload
    # API returns the XSS payload as-is
    rec = data["recommendations"][0]
    assert rec["target_name"] == payload
    
    print(f"\n[!] Stored XSS confirmed. API returned: {rec['target_name']}")
