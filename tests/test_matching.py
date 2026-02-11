import pytest
from easyupsell.core.matching import InventoryMatcher

def test_inventory_matcher_exact_match():
    matcher = InventoryMatcher(["Boots", "Socks", "Gloves"])
    result = matcher.find_match("Socks")
    assert result is not None
    assert result["name"] == "Socks"
    assert result["score"] == 100

def test_inventory_matcher_fuzzy_match():
    matcher = InventoryMatcher(["Tactical Boots", "Wool Socks", "Leather Gloves"])
    # "Boot" should match "Tactical Boots"
    result = matcher.find_match("Boot")
    assert result is not None
    assert result["name"] == "Tactical Boots"
    assert result["score"] > 80

def test_inventory_matcher_no_match():
    matcher = InventoryMatcher(["Boots", "Socks"])
    result = matcher.find_match("Space Ship")
    assert result is None

def test_inventory_matcher_threshold():
    matcher = InventoryMatcher(["Boots", "Socks"])
    # "Boat" is close to "Boots" but maybe not close enough for high threshold?
    # rapidfuzz score for Boat vs Boots is 75-80.
    result = matcher.find_match("Boat", threshold=90)
    assert result is None
