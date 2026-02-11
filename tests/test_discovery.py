import pytest
from unittest.mock import patch, MagicMock
from easyupsell.core.discovery import brainstorm_concepts, discover_dark_horses

def test_brainstorm_concepts():
    """Test brainstorm_concepts parses LLM output correctly."""
    
    mock_llm_response = {
        "concepts": [
            "Socks",
            "Laces",
            "Insoles"
        ]
    }
    
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

def test_discover_dark_horses():
    """Test full discovery pipeline."""
    # Mock brainstorm response
    with patch("easyupsell.core.discovery.brainstorm_concepts") as mock_brainstorm:
        mock_brainstorm.return_value = ["Socks", "Spaceship"]
        
        # Mock Inventory Matcher
        # We need to ensure discover_dark_horses instantiates InventoryMatcher
        # We can pass all_categories to the function
        all_cats = ["Wool Socks", "Tactical Boots", "Flashlights"]
        
        # Mock Validation
        # "Socks" -> "Wool Socks" (Match) -> Validate -> True
        # "Spaceship" -> No Match -> Gap
        
        with patch("easyupsell.core.discovery.get_llm_validation") as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "confidence": 0.9,
                "reason": "Good match",
                "relationship_type": "accessory",
                "suggested_weight": 80
            }
            
            results = discover_dark_horses("Tactical Boots", all_cats, provider="local")
            
            # Check Results
            pairings = results["pairings"]
            gaps = results["gaps"]
            
            assert len(pairings) == 1
            assert pairings[0]["source"] == "Tactical Boots"
            assert pairings[0]["target"] == "Wool Socks"
            assert pairings[0]["concept"] == "Socks"
            assert pairings[0]["validation"]["valid"] is True
            
            assert len(gaps) == 1
            assert gaps[0]["source"] == "Tactical Boots"
            assert gaps[0]["missing_concept"] == "Spaceship"