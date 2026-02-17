"""
Tests for the review pipeline: checkpoint/resume + enriched output.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from easyupsell.core.review import (
    save_checkpoint,
    load_checkpoint,
    review_all_pairings,
    write_reviewed_excel,
)


# ── Fixtures ──

def _make_pairings(n: int) -> list:
    """Generate N fake pairings for testing."""
    return [
        {
            "source_category": f"Cat_{i}",
            "target_category": f"Target_{i}",
            "concept_matched": f"Concept_{i}",
            "match_confidence": 85.0,
            "relationship_type": "Accessory",
        }
        for i in range(n)
    ]


def _make_scored(pairings: list, score: int = 4) -> list:
    """Add review fields to pairings."""
    return [
        {**p, "relevance_score": score, "keep": True, "review_note": ""}
        for p in pairings
    ]


# ── Checkpoint Tests ──

class TestCheckpoint:
    def test_save_and_load_checkpoint(self, tmp_path):
        """Checkpoint round-trip: save then load preserves data."""
        cp_path = tmp_path / "test_checkpoint.json"
        scored = _make_scored(_make_pairings(5))

        save_checkpoint(scored, 5, cp_path)
        assert cp_path.exists()

        loaded_scored, next_index = load_checkpoint(cp_path)
        assert len(loaded_scored) == 5
        assert next_index == 5
        assert loaded_scored[0]["source_category"] == "Cat_0"
        assert loaded_scored[4]["source_category"] == "Cat_4"

    def test_load_nonexistent_checkpoint(self, tmp_path):
        """Loading a nonexistent checkpoint returns empty defaults."""
        cp_path = tmp_path / "missing.json"
        scored, idx = load_checkpoint(cp_path)
        assert scored == []
        assert idx == 0

    @patch("pre.core.review.review_batch")
    def test_resume_skips_already_scored(self, mock_review_batch, tmp_path):
        """Resume from checkpoint skips already-scored pairings."""
        cp_path = tmp_path / "resume_checkpoint.json"
        all_pairings = _make_pairings(10)

        # Pre-populate checkpoint with first 5 scored
        pre_scored = _make_scored(all_pairings[:5])
        save_checkpoint(pre_scored, 5, cp_path)

        # Mock review_batch to return scored versions of remaining pairings
        def fake_review(batch, provider="athena"):
            return [{**p, "relevance_score": 3, "keep": True, "review_note": ""} for p in batch]
        mock_review_batch.side_effect = fake_review

        result = review_all_pairings(
            all_pairings,
            batch_size=5,
            checkpoint_path=cp_path,
            resume=True,
        )

        # Should have all 10 scored
        assert len(result) == 10
        # review_batch should only be called once (for the remaining 5)
        assert mock_review_batch.call_count == 1
        # First 5 should have score=4 (from checkpoint), last 5 should have score=3
        assert result[0]["relevance_score"] == 4
        assert result[5]["relevance_score"] == 3

    @patch("pre.core.review.review_batch")
    def test_checkpoint_deleted_on_completion(self, mock_review_batch, tmp_path):
        """Checkpoint file is cleaned up after successful completion."""
        cp_path = tmp_path / "cleanup_checkpoint.json"
        pairings = _make_pairings(3)

        mock_review_batch.return_value = _make_scored(pairings)

        review_all_pairings(
            pairings,
            batch_size=10,
            checkpoint_path=cp_path,
        )

        assert not cp_path.exists(), "Checkpoint should be deleted after successful completion"

    @patch("pre.core.review.review_batch")
    def test_checkpoint_written_during_batches(self, mock_review_batch, tmp_path):
        """Checkpoint is written after each batch during processing."""
        cp_path = tmp_path / "batch_checkpoint.json"
        pairings = _make_pairings(6)
        checkpoint_snapshots = []

        def fake_review(batch, provider="athena"):
            return [{**p, "relevance_score": 4, "keep": True, "review_note": ""} for p in batch]
        mock_review_batch.side_effect = fake_review

        # Patch save_checkpoint to capture calls
        original_save = save_checkpoint
        def tracking_save(scored, next_idx, path):
            checkpoint_snapshots.append((len(scored), next_idx))
            original_save(scored, next_idx, path)
        
        with patch("pre.core.review.save_checkpoint", side_effect=tracking_save):
            review_all_pairings(pairings, batch_size=2, checkpoint_path=cp_path)

        # Should have saved 3 times (6 items / batch_size 2)
        assert len(checkpoint_snapshots) == 3
        assert checkpoint_snapshots[0] == (2, 2)
        assert checkpoint_snapshots[1] == (4, 4)
        assert checkpoint_snapshots[2] == (6, 6)


# ── Enriched Output Tests ──

class TestEnrichedExcel:
    def test_enriched_fields_in_excel(self, tmp_path):
        """Reviewed Excel contains all 11 enriched columns."""
        excel_path = tmp_path / "enriched.xlsx"

        scored = _make_scored(_make_pairings(2))
        for p in scored:
            p["target_sku"] = "SKU-123"
            p["sales_velocity"] = 42
            p["margin_pct"] = 0.35
            p["copurchase_count"] = 0
            p["high_priority"] = True

        write_reviewed_excel(scored, [], excel_path, min_score=2)

        from openpyxl import load_workbook
        wb = load_workbook(excel_path, read_only=True)
        ws = wb["Reviewed Pairings"]
        headers = [cell.value for cell in ws[1]]

        expected_headers = [
            "source_category", "target_category", "target_sku",
            "concept_matched", "match_confidence", "relationship_type",
            "sales_velocity", "margin_pct", "copurchase_count",
            "relevance_score", "review_note", "high_priority",
        ]
        assert headers == expected_headers

        # Check data in first row
        row = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))[0]
        row_dict = dict(zip(headers, row))
        assert row_dict["target_sku"] == "SKU-123"
        assert row_dict["sales_velocity"] == 42
        assert row_dict["high_priority"] == "★"
        wb.close()

    def test_high_priority_flag_logic(self, tmp_path):
        """High priority: margin >= 25% AND copurchase == 0."""
        excel_path = tmp_path / "priority.xlsx"

        scored = _make_scored(_make_pairings(3))
        # Case 1: High margin + zero copurchase → ★
        scored[0].update({"margin_pct": 0.30, "copurchase_count": 0, "high_priority": True,
                          "target_sku": "", "sales_velocity": ""})
        # Case 2: High margin but has copurchases → no flag
        scored[1].update({"margin_pct": 0.40, "copurchase_count": 5, "high_priority": False,
                          "target_sku": "", "sales_velocity": ""})
        # Case 3: Low margin + zero copurchase → no flag
        scored[2].update({"margin_pct": 0.10, "copurchase_count": 0, "high_priority": False,
                          "target_sku": "", "sales_velocity": ""})

        write_reviewed_excel(scored, [], excel_path, min_score=2)

        from openpyxl import load_workbook
        wb = load_workbook(excel_path, read_only=True)
        ws = wb["Reviewed Pairings"]
        headers = [cell.value for cell in ws[1]]

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        data = [dict(zip(headers, r)) for r in rows]

        assert data[0]["high_priority"] == "★", "High margin + zero copurchase should be flagged"
        assert not data[1]["high_priority"], "Has copurchases — should not be flagged"
        assert not data[2]["high_priority"], "Low margin — should not be flagged"
        wb.close()

    def test_empty_enrichment_graceful(self, tmp_path):
        """Pairings without enrichment data should still produce valid Excel."""
        excel_path = tmp_path / "no_enrichment.xlsx"

        scored = _make_scored(_make_pairings(1))
        # No enrichment fields set at all — should default gracefully
        scored[0].setdefault("target_sku", "")
        scored[0].setdefault("sales_velocity", "")
        scored[0].setdefault("margin_pct", "")
        scored[0].setdefault("copurchase_count", "")
        scored[0].setdefault("high_priority", False)

        write_reviewed_excel(scored, [], excel_path, min_score=2)

        from openpyxl import load_workbook
        wb = load_workbook(excel_path, read_only=True)
        ws = wb["Reviewed Pairings"]
        headers = [cell.value for cell in ws[1]]
        row = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))[0]
        row_dict = dict(zip(headers, row))

        assert not row_dict["target_sku"]  # None or empty string
        assert not row_dict["high_priority"]  # None or empty string
        wb.close()
