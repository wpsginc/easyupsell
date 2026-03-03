import pytest
from pathlib import Path
import zipfile
import os
import csv
from scripts.migrate_csv_to_db import migrate_csv_to_db
from src.db import RecommendationDB

def test_xlsx_xxe_injection(tmp_path):
    """
    VULN-003: XML External Entity (XXE) Injection
    Tests if the XLSX parser (openpyxl) is vulnerable to XXE.
    """
    try:
        from openpyxl import Workbook
    except ImportError:
        pytest.skip("openpyxl not installed")

    # 1. Create a secret file to steal
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SUPER_SECRET_VALUE")
    
    # 2. Create a valid XLSX first
    wb = Workbook()
    ws = wb.active
    ws.title = "Reviewed Pairings"
    ws.append(["source_category", "target_sku", "target_category", "relevance_score"])
    # "placeholder" will be replaced by the entity &xxe;
    ws.append(["placeholder", "SKU-XXE", "Category", 0.9])
    
    xlsx_path = tmp_path / "malicious.xlsx"
    wb.save(xlsx_path)
    
    # 3. Unzip and inject payload
    extract_dir = tmp_path / "unzipped"
    with zipfile.ZipFile(xlsx_path, "r") as z:
        z.extractall(extract_dir)
        
    # We need to find where "placeholder" is stored.
    # It could be in xl/sharedStrings.xml or xl/worksheets/sheet1.xml
    
    injected = False
    
    # Check sharedStrings.xml
    shared_strings = extract_dir / "xl" / "sharedStrings.xml"
    if shared_strings.exists():
        original_xml = shared_strings.read_text(encoding="utf-8")
        # Inject DOCTYPE
        doctype = f'<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file://{secret_file}"> ]>'
        if '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' in original_xml:
            xml_with_doctype = original_xml.replace(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + doctype
            )
        else:
             # Fallback if header is different
             xml_with_doctype = doctype + "\n" + original_xml
             
        # Replace placeholder
        final_xml = xml_with_doctype.replace("placeholder", "&xxe;")
        shared_strings.write_text(final_xml, encoding="utf-8")
        injected = True
        
    if not injected:
        # Check sheet1.xml (inline strings)
        sheet1 = extract_dir / "xl" / "worksheets" / "sheet1.xml"
        if sheet1.exists():
            original_xml = sheet1.read_text(encoding="utf-8")
            doctype = f'<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file://{secret_file}"> ]>'
            
            if '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' in original_xml:
                xml_with_doctype = original_xml.replace(
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + doctype
                )
            else:
                xml_with_doctype = doctype + "\n" + original_xml
                
            final_xml = xml_with_doctype.replace("placeholder", "&xxe;")
            sheet1.write_text(final_xml, encoding="utf-8")
            injected = True

    if not injected:
        pytest.fail("Could not find 'placeholder' to inject payload into XLSX components")

    # 4. Repack XLSX
    malicious_repacked = tmp_path / "malicious_repacked.xlsx"
    with zipfile.ZipFile(malicious_repacked, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                full_path = Path(root) / file
                arcname = full_path.relative_to(extract_dir)
                z.write(full_path, arcname)

    # 5. Run Migration
    db_path = tmp_path / "xxe.db"
    dummy_csv = tmp_path / "dummy.csv"
    dummy_csv.write_text("source_category,target_sku\nA,B")

    try:
        migrate_csv_to_db(csv_path=dummy_csv, xlsx_path=malicious_repacked, db_path=db_path)
    except Exception as e:
        # It might fail due to XML parsing error if protection is active (Good)
        # or other reasons.
        print(f"Migration failed with: {e}")

    # 6. Verify if Secret was Stolen
    if db_path.exists():
        db = RecommendationDB(db_path)
        with db._connect(read_only=True) as conn:
            row = conn.execute("SELECT source_category FROM recommendations WHERE target_sku = 'SKU-XXE'").fetchone()
            if row:
                val = row["source_category"]
                if val == "SUPER_SECRET_VALUE":
                    pytest.fail("VULNERABILITY CONFIRMED: XXE Injection successful! Read local file content.")
                elif val == "&xxe;":
                    print("Entity not expanded (Safe)")
                else:
                    print(f"Value is: {val}")
            else:
                print("Row not found (Safe/Failed)")
    else:
        print("DB not created (Safe/Failed)")


def test_csv_dos_huge_field(tmp_path):
    """
    VULN-004: Denial of Service via Large CSV Field
    """
    csv_path = tmp_path / "huge.csv"
    db_path = tmp_path / "dos.db"
    
    # 50MB string (Python default limit is 131072 chars ~ 128KB)
    # If the script accepts 50MB, it means it's not enforcing limits.
    huge_string = "A" * (50 * 1024 * 1024)
    
    with open(csv_path, "w") as f:
        f.write("source_category,recommended_sku,recommended_name,llm_confidence\n")
        f.write(f"Normal,{huge_string},Item,0.9\n")
        
    try:
        migrate_csv_to_db(csv_path=csv_path, xlsx_path=None, db_path=db_path)
    except csv.Error as e:
        if "field larger than field limit" in str(e):
             print("Safe: field limit enforcement active.")
             return
        raise e
    except Exception:
        # Other errors might occur
        pass
        
    print("Warning: Accepted 50MB field.")
