"""Tests for _parse_batch_json handling various LLM response wrapper formats."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_category_pairings import _parse_batch_json


SAMPLE_ITEMS = [
    {"item_index": 1, "valid": True, "confidence": 0.9, "reason": "good match"},
    {"item_index": 2, "valid": False, "confidence": 0.2, "reason": "unrelated"},
]


class TestParseBatchJson:
    """Test _parse_batch_json with various response formats."""

    def test_direct_array(self):
        """Direct JSON array (ideal case)."""
        import json
        result = _parse_batch_json(json.dumps(SAMPLE_ITEMS))
        assert len(result) == 2
        assert result[0]["valid"] is True

    def test_results_wrapper(self):
        """Wrapped in {"results": [...]}."""
        import json
        result = _parse_batch_json(json.dumps({"results": SAMPLE_ITEMS}))
        assert len(result) == 2

    def test_items_wrapper(self):
        """Wrapped in {"items": [...]} — common GPT-5.2 response."""
        import json
        result = _parse_batch_json(json.dumps({"items": SAMPLE_ITEMS}))
        assert len(result) == 2

    def test_evaluations_wrapper(self):
        """Wrapped in {"evaluations": [...]}."""
        import json
        result = _parse_batch_json(json.dumps({"evaluations": SAMPLE_ITEMS}))
        assert len(result) == 2

    def test_arbitrary_wrapper(self):
        """Wrapped in any key name."""
        import json
        result = _parse_batch_json(json.dumps({"upsell_recommendations": SAMPLE_ITEMS}))
        assert len(result) == 2

    def test_markdown_code_block(self):
        """JSON inside a markdown code fence."""
        import json
        content = f"```json\n{json.dumps(SAMPLE_ITEMS)}\n```"
        result = _parse_batch_json(content)
        assert len(result) == 2

    def test_empty_response(self):
        """Empty string returns empty list."""
        result = _parse_batch_json("")
        assert result == []

    def test_invalid_json(self):
        """Gibberish returns empty list."""
        result = _parse_batch_json("This is not JSON at all")
        assert result == []

    def test_dict_with_no_list_value(self):
        """Dict with no list-typed values returns empty list."""
        import json
        result = _parse_batch_json(json.dumps({"status": "ok", "count": 2}))
        assert result == []
