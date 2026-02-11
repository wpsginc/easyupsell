import pytest
from unittest.mock import MagicMock
from easyupsell.core.analyzer import get_all_leaf_categories

def test_get_all_leaf_categories():
    """Test that only leaf categories are returned."""
    mock_client = MagicMock()
    mock_client.get_categories.return_value = [
        {"id": 1, "name": "Parent", "parent_id": 0},
        {"id": 2, "name": "Child 1", "parent_id": 1},
        {"id": 3, "name": "Child 2", "parent_id": 1},
        {"id": 4, "name": "Grandchild 1", "parent_id": 2},
    ]
    
    # Leaves: 
    # 3 (Child 2) - parent is 1, no children
    # 4 (Grandchild 1) - parent is 2, no children
    # 1 is parent of 2, 3
    # 2 is parent of 4
    
    leaves = get_all_leaf_categories(mock_client)
    
    ids = [c["id"] for c in leaves]
    assert 1 not in ids
    assert 2 not in ids
    assert 3 in ids
    assert 4 in ids
    assert len(leaves) == 2

def test_get_all_leaf_categories_empty():
    """Test empty list."""
    mock_client = MagicMock()
    mock_client.get_categories.return_value = []
    
    leaves = get_all_leaf_categories(mock_client)
    assert len(leaves) == 0
