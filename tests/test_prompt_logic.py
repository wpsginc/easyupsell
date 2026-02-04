import sys
from pathlib import Path
import json

# Add src/scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from config import settings
from validate_category_pairings import get_batch_llm_validation

def test_same_category_accessory():
    """Test that Helmet Lights are accepted for Helmets category."""
    print("Testing 'Helmet Light' (Same Category) logic...")
    
    source = "Fire Helmets"
    items = [
        {"name": "Streamlight Vantage Helmet Light", "sku": "STR-69140", "brand": "Streamlight"},
        {"name": "Leather Helmet Front Holder", "sku": "HOLDER-01", "brand": "Unknown"},
        {"name": "Random T-Shirt", "sku": "SHIRT-001", "brand": "Generic"} # Control: Should fail
    ]
    
    # Force use of a provider that works (assuming config is set or defaults work)
    # Using 'athena' if available, else standard fallback
    provider = "athena"
    
    print(f"Using provider: {provider}")
    
    results = get_batch_llm_validation(source, items, provider=provider)
    
    for r in results:
        status = "✅ VALID" if r.get("valid") else "❌ INVALID"
        print(f"  {r.get('item_name')}: {status} (Reason: {r.get('reason')})")
        
    # Check specific logic
    light = next((r for r in results if "Vantage" in r.get("item_name", "")), {})
    shirt = next((r for r in results if "T-Shirt" in r.get("item_name", "")), {})
    
    if light.get("valid") and not shirt.get("valid"):
        print("\nSUCCESS: Logic correctly distinguished accessory from random item.")
    else:
        print("\nFAILURE: Logic failed to distinguish.")

if __name__ == "__main__":
    test_same_category_accessory()
