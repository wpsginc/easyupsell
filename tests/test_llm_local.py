import pytest
from unittest.mock import patch, MagicMock
from scripts.validate_category_pairings import get_llm_validation
from src.config import settings

def test_get_llm_validation_local():
    """Test get_llm_validation with provider='local' calls the correct endpoint."""
    
    # Mock response
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": true, "confidence": 0.9, "reason": "Test reason", "relationship_type": "complementary", "suggested_weight": 80}'
                }
            }
        ]
    }
    
    with patch("scripts.validate_category_pairings.requests.post") as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        # Call function
        result = get_llm_validation("Source", "Target", provider="local")
        
        # Verify result
        assert result["valid"] is True
        assert result["confidence"] == 0.9
        
        # Verify call arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        assert kwargs["json"]["model"] == settings.LOCAL_LLM_MODEL
        assert settings.LOCAL_LLM_HOST in args[0]
