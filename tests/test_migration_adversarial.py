import csv
import pytest
from scripts.migrate_csv_to_db import _parse_margin, _clamp_score
from pathlib import Path

def test_parse_margin_logic_flaw():
    """
    BUG: _parse_margin assumes values > 1.0 are percentage points (0-100 scale),
    incorrectly downscaling valid decimal margins > 1.0 (e.g. 150% = 1.5).
    """
    # Case 1: 50% as 0.5 -> 0.5 (Correct)
    assert _parse_margin("0.5") == 0.5
    
    # Case 2: 50% as 50 -> 0.5 (Correct)
    assert _parse_margin("50") == 0.5

    # Case 3: 150% as 1.5 -> Should be 1.5
    # The current logic: 1.5 > 1.0 -> 1.5 / 100 = 0.015
    # This is a Logic Bug.
    val = _parse_margin("1.5")
    if val == 0.015:
        pytest.fail(f"Logic Bug: Margin 1.5 parsed as {val} (1.5%), expected 1.5 (150%)")
    elif val == 1.5:
        pass # Correct behavior (if fixed)
    else:
        pytest.fail(f"Unexpected parsing: 1.5 -> {val}")

def test_parse_margin_negative():
    # Negative margins are possible (selling at loss)
    # -0.5 -> -0.5 (Correct)
    assert _parse_margin("-0.5") == -0.5
    
    # -50 -> -50? 
    # Logic: -50 > 1.0 is False. Returns -50.
    val = _parse_margin("-50")
    if val == -50:
        pytest.fail(f"Inconsistency: Positive 50 -> 0.5, but Negative -50 -> {val}")

def test_clamp_score_edge_cases():
    assert _clamp_score("1.0") == 1.0
    assert _clamp_score("0.0") == 0.0
    assert _clamp_score("-1.0") == 0.0 # Clamped
    assert _clamp_score("2.0") == 1.0 # Clamped
    assert _clamp_score(None) == 0.0
    assert _clamp_score("invalid") == 0.0
    assert _clamp_score("inf") == 1.0 # float("inf") > 1.0 -> 1.0
    assert _clamp_score("-inf") == 0.0

def test_csv_missing_columns(tmp_path):
    from scripts.migrate_csv_to_db import migrate_csv_to_db
    from src.db import RecommendationDB

    csv_path = tmp_path / "broken.csv"
    db_path = tmp_path / "broken.db"
    
    # Missing 'llm_valid' column entirely
    with open(csv_path, "w") as f:
        f.write("source_category,recommended_sku\nTest,SKU1")
        
    # Should not crash, should assume defaults
    migrate_csv_to_db(csv_path, None, db_path)
    
    db = RecommendationDB(db_path)
    with db._connect(read_only=True) as conn:
        row = conn.execute("SELECT * FROM recommendations").fetchone()
        
    assert row["source_category"] == "Test"
    assert row["status"] == "pending_review" # Default because llm_valid missing -> False -> pending_review
