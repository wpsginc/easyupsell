import json
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts import check_phase3_enrichment as checker


XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _build_sheet_xml(rows, header_style_id=1, numeric_style_ids=None):
    root = ET.Element(f"{{{XML_NS}}}worksheet")
    sheet_data = ET.SubElement(root, f"{{{XML_NS}}}sheetData")

    for row_idx, row in enumerate(rows, start=1):
        row_el = ET.SubElement(sheet_data, f"{{{XML_NS}}}row", {"r": str(row_idx)})
        for col_idx, value in enumerate(row, start=1):
            cell_ref = f"{_col_letter(col_idx)}{row_idx}"
            if row_idx == 1:
                style_id = header_style_id
            else:
                style_id = (
                    numeric_style_ids.get(col_idx - 1, 0) if numeric_style_ids else 0
                )

            attrs = {"r": cell_ref}
            if style_id:
                attrs["s"] = str(style_id)

            cell = ET.SubElement(row_el, f"{{{XML_NS}}}c", attrs)

            if isinstance(value, (int, float)):
                value_el = ET.SubElement(cell, f"{{{XML_NS}}}v")
                value_el.text = str(value)
                continue

            cell.attrib.setdefault("t", "inlineStr")
            inline = ET.SubElement(cell, f"{{{XML_NS}}}is")
            text = ET.SubElement(inline, f"{{{XML_NS}}}t")
            text.text = "" if value is None else str(value)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_styles_xml() -> bytes:
    root = ET.Element(f"{{{XML_NS}}}styleSheet")

    num_fmts = ET.SubElement(root, f"{{{XML_NS}}}numFmts", {"count": "1"})
    ET.SubElement(
        num_fmts,
        f"{{{XML_NS}}}numFmt",
        {"numFmtId": "164", "formatCode": "$#,##0.00"},
    )

    fonts = ET.SubElement(root, f"{{{XML_NS}}}fonts", {"count": "2"})
    ET.SubElement(fonts, f"{{{XML_NS}}}font")
    font_bold = ET.SubElement(fonts, f"{{{XML_NS}}}font")
    ET.SubElement(font_bold, f"{{{XML_NS}}}b")

    fills = ET.SubElement(root, f"{{{XML_NS}}}fills", {"count": "3"})
    ET.SubElement(fills, f"{{{XML_NS}}}fill")
    ET.SubElement(fills, f"{{{XML_NS}}}fill")
    header_fill = ET.SubElement(fills, f"{{{XML_NS}}}fill")
    pattern_fill = ET.SubElement(
        header_fill, f"{{{XML_NS}}}patternFill", {"patternType": "solid"}
    )
    fg = ET.SubElement(pattern_fill, f"{{{XML_NS}}}fgColor", {"rgb": "FF4472C4"})
    ET.SubElement(pattern_fill, f"{{{XML_NS}}}bgColor", {"rgb": "FF4472C4"})

    borders = ET.SubElement(root, f"{{{XML_NS}}}borders", {"count": "1"})
    ET.SubElement(
        borders,
        f"{{{XML_NS}}}border",
        {"diagonalUp": "0", "diagonalDown": "0", "diagonalDirection": "0"},
    )

    cell_style_xfs = ET.SubElement(root, f"{{{XML_NS}}}cellStyleXfs", {"count": "1"})
    ET.SubElement(
        cell_style_xfs,
        f"{{{XML_NS}}}xf",
        {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0"},
    )

    cell_xfs = ET.SubElement(root, f"{{{XML_NS}}}cellXfs", {"count": "3"})
    ET.SubElement(
        cell_xfs,
        f"{{{XML_NS}}}xf",
        {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0", "xfId": "0"},
    )
    ET.SubElement(
        cell_xfs,
        f"{{{XML_NS}}}xf",
        {
            "numFmtId": "0",
            "fontId": "1",
            "fillId": "2",
            "borderId": "0",
            "xfId": "0",
            "applyFont": "1",
            "applyFill": "1",
        },
    )
    ET.SubElement(
        cell_xfs,
        f"{{{XML_NS}}}xf",
        {
            "numFmtId": "164",
            "fontId": "0",
            "fillId": "0",
            "borderId": "0",
            "xfId": "0",
            "applyNumberFormat": "1",
        },
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_content_types() -> bytes:
    types = ET.Element(
        "Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types"
    )
    ET.SubElement(
        types,
        "Default",
        Extension="rels",
        ContentType="application/vnd.openxmlformats-package.relationships+xml",
    )
    ET.SubElement(types, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(
        types,
        "Override",
        PartName="/xl/workbook.xml",
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    )
    ET.SubElement(
        types,
        "Override",
        PartName="/xl/worksheets/sheet1.xml",
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
    )
    ET.SubElement(
        types,
        "Override",
        PartName="/xl/worksheets/sheet2.xml",
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
    )
    ET.SubElement(
        types,
        "Override",
        PartName="/xl/styles.xml",
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
    )
    return ET.tostring(types, encoding="utf-8", xml_declaration=True)


def _build_workbook_xml() -> bytes:
    root = ET.Element(f"{{{XML_NS}}}workbook", xmlns=XML_NS)
    sheets = ET.SubElement(root, f"{{{XML_NS}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{XML_NS}}}sheet",
        {
            "name": "New Product Opportunities",
            "sheetId": "1",
            f"{{{REL_NS}}}id": "rId1",
        },
    )
    ET.SubElement(
        sheets,
        f"{{{XML_NS}}}sheet",
        {
            "name": "Gap Detail",
            "sheetId": "2",
            f"{{{REL_NS}}}id": "rId2",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _build_workbook_rels(sheet_target_prefix: str = "worksheets") -> bytes:
    rels = ET.Element(
        "Relationships",
        xmlns="http://schemas.openxmlformats.org/package/2006/relationships",
    )
    ET.SubElement(
        rels,
        "Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": f"{sheet_target_prefix}/sheet1.xml",
        },
    )
    ET.SubElement(
        rels,
        "Relationship",
        {
            "Id": "rId2",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": f"{sheet_target_prefix}/sheet2.xml",
        },
    )
    ET.SubElement(
        rels,
        "Relationship",
        {
            "Id": "rId3",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
            "Target": "styles.xml",
        },
    )
    return ET.tostring(rels, encoding="utf-8", xml_declaration=True)


def _build_package_rels() -> bytes:
    rels = ET.Element(
        "Relationships",
        xmlns="http://schemas.openxmlformats.org/package/2006/relationships",
    )
    ET.SubElement(
        rels,
        "Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    return ET.tostring(rels, encoding="utf-8", xml_declaration=True)


def _write_workbook_fixture(
    path: Path, opportunities, details, sheet_target_prefix: str = "worksheets"
):
    headers = [
        "Product Type",
        "Description",
        "Priority",
        "Price Low",
        "Price High",
        "# Categories",
        "Needed By",
        "Sourcing Notes",
    ]

    opp_rows = [headers]
    for opp in opportunities:
        opp_rows.append(
            [
                opp["product_type"],
                opp["description"],
                opp["priority"],
                opp["price_range_low"],
                opp["price_range_high"],
                opp["category_count"],
                ", ".join(opp["source_categories"]),
                opp["sourcing_notes"],
            ]
        )

    detail_rows = [["Source Category", "Missing Product Type"]]
    for detail in details:
        detail_rows.append([detail["source_category"], detail["missing_product_type"]])

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _build_content_types())
        zf.writestr("_rels/.rels", _build_package_rels())
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            _build_workbook_rels(sheet_target_prefix=sheet_target_prefix),
        )
        zf.writestr("xl/workbook.xml", _build_workbook_xml())
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            _build_sheet_xml(
                opp_rows,
                header_style_id=1,
                numeric_style_ids={
                    3: 2,
                    4: 2,
                },
            ),
        )
        zf.writestr(
            "xl/worksheets/sheet2.xml",
            _build_sheet_xml(detail_rows, header_style_id=1),
        )
        zf.writestr("xl/styles.xml", _build_styles_xml())


def _run_checker(path: Path):
    return subprocess.run(
        [sys.executable, "scripts/check_phase3_enrichment.py", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def _parse_checker_payload(output: str):
    marker = "PHASE3_ENRICHMENT_STATUS="
    for line in output.splitlines():
        if line.startswith(marker):
            return json.loads(line[len(marker) :])
    return {}


def test_workbook_contract_success(tmp_path):
    workbook = tmp_path / "success_opportunities.xlsx"
    opportunities = [
        {
            "product_type": "Tactical Helmet",
            "source_categories": ["Protective Gear", "Rescue Gear"],
            "category_count": 2,
            "description": "Protective helmet for high-risk environments",
            "price_range_low": 39.99,
            "price_range_high": 79.99,
            "priority": "High",
            "sourcing_notes": "Vendors include A and B",
        },
    ]
    details = [
        {
            "source_category": "Protective Gear",
            "missing_product_type": "Tactical Helmet",
        },
        {
            "source_category": "Rescue Gear",
            "missing_product_type": "Tactical Helmet",
        },
    ]

    _write_workbook_fixture(workbook, opportunities, details)
    contract = checker.read_workbook_contract(workbook)

    assert contract["sheets"].keys() == {"New Product Opportunities", "Gap Detail"}

    opp = contract["sheets"]["New Product Opportunities"]
    assert opp["headers"] == [
        "Product Type",
        "Description",
        "Priority",
        "Price Low",
        "Price High",
        "# Categories",
        "Needed By",
        "Sourcing Notes",
    ]
    assert len(opp["rows"]) == len(opportunities)
    assert contract["sheets"]["Gap Detail"]["row_count"] == len(details)
    assert opp["row_count"] == len(opportunities)
    assert all(cell.get("style_id") == 1 for cell in opp["headers_style"])
    assert opp["rows"][0]["style_ids"] == [0, 0, 0, 2, 2, 0, 0, 0]


def test_workbook_contract_handles_prefixed_relationship_targets(tmp_path):
    workbook = tmp_path / "prefixed_targets.xlsx"
    opportunities = [
        {
            "product_type": "Tactical Helmet",
            "source_categories": ["Protective Gear"],
            "category_count": 1,
            "description": "Protective helmet",
            "price_range_low": 39.99,
            "price_range_high": 79.99,
            "priority": "High",
            "sourcing_notes": "Vendors include A and B",
        }
    ]
    details = [
        {
            "source_category": "Protective Gear",
            "missing_product_type": "Tactical Helmet",
        }
    ]

    _write_workbook_fixture(
        workbook,
        opportunities,
        details,
        sheet_target_prefix="/xl/worksheets",
    )
    contract = checker.read_workbook_contract(workbook)

    assert contract["sheets"].keys() == {"New Product Opportunities", "Gap Detail"}
    assert contract["sheets"]["New Product Opportunities"]["row_count"] == len(
        opportunities
    )
    assert contract["sheets"]["Gap Detail"]["row_count"] == len(details)


def test_checker_accepts_enriched_workbook(tmp_path):
    workbook = tmp_path / "check_pass.xlsx"
    opportunities = [
        {
            "product_type": "Tactical Helmet",
            "source_categories": ["Protective Gear"],
            "category_count": 1,
            "description": "Protective helmet",
            "price_range_low": 39.99,
            "price_range_high": 79.99,
            "priority": "High",
            "sourcing_notes": "Sourced from approved suppliers",
        },
    ]
    details = [
        {
            "source_category": "Protective Gear",
            "missing_product_type": "Tactical Helmet",
        }
    ]

    _write_workbook_fixture(workbook, opportunities, details)

    result = _run_checker(workbook)
    payload = _parse_checker_payload(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "ok"
    assert payload["enriched_rows"] == 1
    assert payload["enriched_columns"] == [
        "Description",
        "Priority",
        "Price Low",
        "Price High",
    ]


def test_checker_rejects_blank_enrichment_fields(tmp_path):
    workbook = tmp_path / "check_fail.xlsx"
    opportunities = [
        {
            "product_type": "Tactical Helmet",
            "source_categories": ["Protective Gear"],
            "category_count": 1,
            "description": "",
            "price_range_low": "",
            "price_range_high": "",
            "priority": "",
            "sourcing_notes": "",
        }
    ]
    details = [
        {
            "source_category": "Protective Gear",
            "missing_product_type": "Tactical Helmet",
        }
    ]

    _write_workbook_fixture(workbook, opportunities, details)

    result = _run_checker(workbook)
    payload = _parse_checker_payload(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "fail"
    assert payload["errors"]
    assert any(
        item["column"] == "Description" and item["row"] == 2
        for item in payload["errors"]
    )
