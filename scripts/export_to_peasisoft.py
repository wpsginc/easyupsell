#!/usr/bin/env python3
"""
Peasisoft Export Tool

Filters reviewed recommendations for "Approved" items and formats them 
for the Easy-Upsell app import.
"""

import argparse
import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

def export_approved(input_csv: Path, output_csv: Path):
    if not input_csv.exists():
        print(f"Error: Input file {input_csv} not found.")
        return

    approved_count = 0
    total_count = 0
    
    # Target columns for Peasisoft (Assumed based on app type)
    # Most apps want: Source Identifier, Target Identifier, Optional Weight
    fieldnames = [
        "source_category", "recommended_netsuite_id", "recommended_sku", 
        "recommended_name", "suggested_weight"
    ]

    try:
        with open(input_csv, "r", encoding="utf-8") as f_in:
            reader = csv.DictReader(f_in)
            
            with open(output_csv, "w", newline="", encoding="utf-8") as f_out:
                writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                
                for row in reader:
                    total_count += 1
                    # Check for approval
                    if row.get("human_status") == "Approved":
                        # Ensure weight has a default
                        if not row.get("suggested_weight"):
                            row["suggested_weight"] = 50
                            
                        writer.writerow(row)
                        approved_count += 1
                        
        print(f"Export Complete!")
        print(f"Total Rows Scanned: {total_count}")
        print(f"Approved Items Exported: {approved_count}")
        print(f"Saved to: {output_csv}")
        
    except Exception as e:
        print(f"Error during export: {e}")

def main():
    parser = argparse.ArgumentParser(description="Export approved items for Peasisoft")
    parser.add_argument("file", nargs="?", default="full_recommendations_v2.csv", help="Reviewed CSV file")
    parser.add_argument("--output", default="peasisoft_import.csv", help="Output filename")
    args = parser.parse_args()
    
    input_path = Path(args.file)
    if not input_path.exists():
        input_path = settings.DATA_DIR / args.file
        
    output_path = settings.DATA_DIR / args.output
    
    export_approved(input_path, output_path)

if __name__ == "__main__":
    main()
