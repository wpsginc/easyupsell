import argparse
import json
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZipFile
from xml.etree import ElementTree as ET


XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REQUIRED_SHEET = "New Product Opportunities"
DETAIL_SHEET = "Gap Detail"
REQUIRED_COLUMNS = ["Description", "Priority", "Price Low", "Price High"]


def _xml_to_dict(
    xml_bytes: bytes,
    *,
    include_namespace: bool = True,
) -> ET.Element:
    root = ET.fromstring(xml_bytes)
    if include_namespace:
        return root
    for elem in root.iter():
        if not isinstance(elem.tag, str) or "}" not in elem.tag:
            continue
        elem.tag = elem.tag.split("}", 1)[1]
    return root


def _col_letter_to_index(letter: str) -> int:
    total = 0
    for char in letter:
        total = total * 26 + (ord(char.upper()) - ord("A") + 1)
    return total


def _cell_ref_to_index(cell_ref: str) -> int:
    col = "".join(c for c in cell_ref if c.isalpha())
    return _col_letter_to_index(col)


def _read_shared_strings(root: Optional[ET.Element]) -> List[str]:
    if root is None:
        return []
    values = []
    for node in root.findall(f".//{{{XML_NS}}}t"):
        values.append(node.text or "")
    return values


def _cell_value(cell: ET.Element, shared_strings: List[str]) -> str:
    value_type = cell.attrib.get("t")
    if value_type == "inlineStr":
        text_node = cell.find(f"{{{XML_NS}}}is/{{{XML_NS}}}t")
        return text_node.text or "" if text_node is not None else ""
    if value_type == "s":
        raw = cell.findtext(f"{{{XML_NS}}}v")
        if raw is None:
            return ""
        try:
            return shared_strings[int(raw)]
        except (IndexError, ValueError):
            return ""

    raw = cell.findtext(f"{{{XML_NS}}}v")
    if raw is None:
        return ""
    return raw


def _normalize_sheet_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def _parse_sheet_xml(xml_text: bytes, shared_strings: List[str]) -> List[Dict]:
    root = _xml_to_dict(xml_text)
    rows = []

    for row in root.findall(f".//{{{XML_NS}}}sheetData/{{{XML_NS}}}row"):
        row_num = int(row.attrib.get("r", "0") or 0)
        cell_map: Dict[int, str] = {}
        style_map: Dict[int, int] = {}
        max_col = 0

        for cell in row.findall(f"{{{XML_NS}}}c"):
            ref = cell.attrib.get("r", "")
            if not ref:
                continue
            col_index = _cell_ref_to_index(ref)
            max_col = max(max_col, col_index)
            cell_map[col_index] = _cell_value(cell, shared_strings)
            style_map[col_index] = int(cell.attrib.get("s", "0") or 0)

        values = [""] * max_col
        styles = [0] * max_col
        for idx in range(1, max_col + 1):
            values[idx - 1] = cell_map.get(idx, "")
            styles[idx - 1] = style_map.get(idx, 0)

        rows.append({"row": row_num, "values": values, "style_ids": styles})

    rows.sort(key=lambda item: item["row"])
    return rows


def _sheet_relations(zip_handle: ZipFile, workbook_xml: ET.Element) -> Dict[str, str]:
    rel_root = ET.fromstring(zip_handle.read("xl/_rels/workbook.xml.rels"))
    id_to_target = {
        node.attrib["Id"]: node.attrib["Target"]
        for node in rel_root.findall(f".//{{*}}Relationship")
        if "Id" in node.attrib and "Target" in node.attrib
    }

    sheets = {}
    for node in workbook_xml.findall(f".//{{{XML_NS}}}sheet"):
        name = node.attrib.get("name", "")
        rid = node.attrib.get(f"{{{REL_NS}}}id")
        if not name or not rid:
            continue
        target = id_to_target.get(rid)
        if not target:
            continue
        sheets[name] = _normalize_sheet_target(target)
    return sheets


def _read_workbook_with_fallback(path: Path) -> Dict[str, List[Dict]]:
    with ZipFile(path, "r") as zf:
        workbook_xml = ET.fromstring(zf.read("xl/workbook.xml"))
        shared_strings = _read_shared_strings(
            ET.fromstring(zf.read("xl/sharedStrings.xml"))
            if "xl/sharedStrings.xml" in zf.namelist()
            else None
        )
        sheet_lookup = _sheet_relations(zf, workbook_xml)
        data = {}
        for name, rel in sheet_lookup.items():
            if rel in zf.namelist():
                data[name] = _parse_sheet_xml(zf.read(rel), shared_strings)
        return data


def _read_workbook_with_openpyxl(path: Path) -> Dict[str, List[Dict]]:
    openpyxl = importlib.import_module("openpyxl")
    load_workbook = openpyxl.load_workbook

    wb = load_workbook(path, data_only=True)
    data = {}
    for ws in wb.worksheets:
        rows = []
        for row_idx, row in enumerate(
            ws.iter_rows(min_row=1, values_only=False), start=1
        ):
            values = []
            styles = []
            for cell in row:
                values.append("" if cell.value is None else cell.value)
                styles.append(cell.style_id)
            rows.append({"row": row_idx, "values": values, "style_ids": styles})
        data[ws.title] = rows
    return data


def read_workbook_contract(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"workbook not found: {path}")

    try:
        data = _read_workbook_with_openpyxl(path)
    except Exception:
        data = _read_workbook_with_fallback(path)

    sheets = {}
    for name, rows in data.items():
        if not rows:
            sheets[name] = {
                "headers": [],
                "headers_style": [],
                "rows": [],
                "row_count": 0,
            }
            continue

        headers = ["" if v is None else str(v) for v in rows[0]["values"]]
        headers_style = [{"style_id": int(v)} for v in rows[0]["style_ids"]]
        detail_rows = [
            {
                "row": r["row"],
                "values": ["" if v is None else str(v) for v in r["values"]],
                "style_ids": r["style_ids"],
            }
            for r in rows[1:]
        ]

        sheets[name] = {
            "headers": headers,
            "headers_style": headers_style,
            "rows": detail_rows,
            "row_count": len(detail_rows),
        }

    return {"path": str(path), "sheets": sheets}


def _find_column_indices(headers: List[str]) -> Dict[str, int]:
    map_indices = {}
    for idx, col in enumerate(headers):
        if col in REQUIRED_COLUMNS:
            map_indices[col] = idx
    return map_indices


def validate_contract(path: Path) -> Dict[str, Any]:
    contract = read_workbook_contract(path)
    sheets = contract["sheets"]

    errors = []
    sheet_names = set(sheets)
    if REQUIRED_SHEET not in sheet_names:
        errors.append({"code": "missing_sheet", "sheet": REQUIRED_SHEET})
    if DETAIL_SHEET not in sheet_names:
        errors.append({"code": "missing_sheet", "sheet": DETAIL_SHEET})

    opportunities_rows = sheets.get(REQUIRED_SHEET, {}).get("rows", [])
    detail_rows = sheets.get(DETAIL_SHEET, {}).get("rows", [])

    if opportunities_rows:
        headers = sheets[REQUIRED_SHEET]["headers"]
        col_map = _find_column_indices(headers)
        missing_columns = [c for c in REQUIRED_COLUMNS if c not in col_map]
        if missing_columns:
            errors.append({"code": "missing_columns", "columns": missing_columns})
        else:
            for row in opportunities_rows:
                values = row["values"]
                for column in REQUIRED_COLUMNS:
                    value = (
                        values[col_map[column]] if col_map[column] < len(values) else ""
                    )
                    if not str(value).strip():
                        errors.append(
                            {
                                "code": "missing_field",
                                "sheet": REQUIRED_SHEET,
                                "row": row["row"],
                                "column": column,
                                "value": value,
                            }
                        )

        if any("missing_field" in e.get("code", "") for e in errors):
            enriched_rows = 0
        else:
            enriched_rows = len(opportunities_rows)
    else:
        enriched_rows = 0
        errors.append({"code": "missing_data_rows", "sheet": REQUIRED_SHEET})

    if not detail_rows:
        errors.append({"code": "missing_data_rows", "sheet": DETAIL_SHEET})

    status = "ok" if not errors else "fail"
    return {
        "status": status,
        "path": str(path),
        "sheet_names": sorted(sheet_names),
        "enriched_columns": REQUIRED_COLUMNS,
        "opportunities_rows": len(opportunities_rows),
        "detail_rows": len(detail_rows),
        "enriched_rows": enriched_rows,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate opportunities workbook enrichment fields"
    )
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()

    report = validate_contract(args.workbook)
    print(f"PHASE3_ENRICHMENT_STATUS={json.dumps(report, sort_keys=True)}")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
