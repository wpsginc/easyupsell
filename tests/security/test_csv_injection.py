import sys
import csv
from pathlib import Path

# Add src to path to import core logic
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "easyupsell"))

from core.analyzer import save_recommendations

def test_csv_injection():
    """
    POC: Verify that malicious product names are written to CSV without escaping.
    If opened in Excel, this could execute commands.
    """
    # Malicious payload: Starts with =, attempts to run calculator (classic POC)
    malicious_name = "=cmd|' /C calc'!A0"
    
    recommendations = [{
        "source_category": "Test Category",
        "recommended_sku": "SKU-123",
        "recommended_name": malicious_name, # THE PAYLOAD
        "recommended_price": 10.0,
        "llm_valid": True,
        # ... other fields can be empty/default for this test
    }]
    
    output_path = Path("tests/security/exploit.csv")
    
    print(f"[*] Attempting to write malicious CSV to {output_path}")
    save_recommendations(recommendations, output_path)
    
    # Verify content
    with open(output_path, "r") as f:
        content = f.read()
        print(f"[*] CSV Content:\n{content}")
        
    if malicious_name in content:
        # Check if it's quoted/escaped properly to prevent execution?
        # Python's csv writer quotes fields containing delimiters, but NOT formulas.
        # If the raw string appears exactly as input, it's vulnerable.
        print("\n[!] VULNERABILITY CONFIRMED: Malicious payload written directly to CSV.")
        print("[!] Excel will execute this formula.")
    else:
        print("\n[?] Payload modified. Might be safe.")

if __name__ == "__main__":
    test_csv_injection()
