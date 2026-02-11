import pytest
from unittest.mock import patch, MagicMock
from easyupsell.core.discovery import brainstorm_concepts

def test_brainstorm_concepts():
    """Test brainstorm_concepts parses LLM output correctly."""
    
    mock_llm_response = {
        "concepts": [
            "Socks",
            "Laces",
            "Insoles"
        ]
    }
    
    # Mock the LLM call (which will likely be imported/used inside discovery)
    # Assuming discovery uses a helper or calls the script function.
    # To keep it clean, I'll assume discovery calls a validation function or similar client.
    # For now, let's assume it calls `get_llm_validation` or a new `call_llm` wrapper.
    # Since I just implemented `_call_local_llm` in `scripts/validate_category_pairings.py`, 
    # I should probably expose a generic `call_llm` there or use it.
    
    # Let's assume `brainstorm_concepts` calls a mocked function.
    
    with patch("easyupsell.core.discovery.call_llm_generic") as mock_call:
        mock_call.return_value = mock_llm_response
        
        concepts = brainstorm_concepts("Tactical Boots", provider="local")
        
        assert len(concepts) == 3
        assert "Socks" in concepts
        assert "Laces" in concepts
        
        # Verify prompt contains category
        args, _ = mock_call.call_args
        prompt = args[0]
        assert "Tactical Boots" in prompt
