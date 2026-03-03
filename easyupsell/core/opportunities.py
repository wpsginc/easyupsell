"""
Phase 3: New Product Opportunities — Core Module

Identifies products we DON'T carry but SHOULD, based on catalog gaps
discovered during Phase 2 Dark Horse analysis.

Pipeline:
    1. Load catalog_gaps.csv → deduplicate by product type
    2. (Optional) Batch-enrich via LLM with descriptions, price ranges, priority
    3. Write polished Excel workbook for merchandising team
"""

import csv
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import LLM caller (following existing project pattern)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from validate_category_pairings import call_llm_generic  # type: ignore[reportMissingImports]


def _normalize_priority(value: str) -> str:
    normalized = value if isinstance(value, str) else "Unknown"
    return (
        normalized if normalized in {"High", "Medium", "Low", "Unknown"} else "Unknown"
    )


def load_and_deduplicate_gaps(csv_path: Path) -> tuple:
    """
    Load catalog_gaps.csv and deduplicate by missing_product_type.

    Returns:
        (unique_opportunities, detail_rows)

        unique_opportunities: list of dicts with:
            - product_type: str
            - source_categories: list[str]  (all categories that need this)
            - category_count: int
            - description: str (empty, filled by LLM later)
            - price_range_low: str
            - price_range_high: str
            - priority: str
            - sourcing_notes: str

        detail_rows: list of original CSV rows for the detail sheet
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Catalog gaps file not found: {csv_path}")

    detail_rows = []
    product_type_map = defaultdict(list)

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_category", "").strip()
            product_type = row.get("missing_product_type", "").strip()

            if not product_type:
                continue

            detail_rows.append(row)
            product_type_map[product_type].append(source)

    # Build deduplicated list, sorted by how many categories need this product
    unique = []
    for product_type, categories in product_type_map.items():
        # Deduplicate category names
        unique_cats = sorted(set(c for c in categories if c))
        unique.append(
            {
                "product_type": product_type,
                "source_categories": unique_cats,
                "category_count": len(unique_cats),
                "description": "",
                "price_range_low": "",
                "price_range_high": "",
                "priority": "",
                "sourcing_notes": "",
            }
        )

    # Sort by category count descending (most-needed products first)
    unique.sort(key=lambda x: x["category_count"], reverse=True)

    logger.info(f"Loaded {len(detail_rows)} gaps → {len(unique)} unique product types")
    return unique, detail_rows


def enrich_opportunities_batch(
    opportunities: List[Dict],
    provider: str = "azure",
    batch_size: int = 20,
    progress_callback=None,
) -> List[Dict]:
    """
    Batch-enrich opportunities with LLM-generated details.

    For each batch, asks the LLM to provide:
    - description: 1-line product description for a merchandiser
    - price_range_low / price_range_high: estimated retail price range
    - priority: High/Medium/Low based on public safety/tactical market fit
    - sourcing_notes: typical suppliers or brands
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    enriched = []

    for i in range(0, len(opportunities), batch_size):
        batch = opportunities[i : i + batch_size]

        # Build batch prompt
        items_text = "\n".join(
            f'{j + 1}. "{item["product_type"]}" (needed by {item["category_count"]} categories: {", ".join(item["source_categories"][:3])}{"..." if len(item["source_categories"]) > 3 else ""})'
            for j, item in enumerate(batch)
        )

        prompt = f"""You are a product sourcing analyst for a public safety and tactical equipment distributor.
Our stores sell to firefighters, police, EMS, military, and industrial workers.

For each product type below, provide sourcing intelligence:

{items_text}

For EACH item, return:
{{
  "opportunities": [
    {{
      "index": 1,
      "description": "Brief 1-line product description for a merchandiser",
      "price_range_low": 9.99,
      "price_range_high": 29.99,
      "priority": "High",
      "sourcing_notes": "Common brands: X, Y. Available from Z."
    }},
    ...
  ]
}}

Priority guidelines:
- HIGH = Essential consumable/accessory with clear demand (batteries, cleaning supplies, replacement parts)
- MEDIUM = Useful complementary product (cases, covers, organizers)
- LOW = Nice-to-have or niche (specialty tools, luxury upgrades)"""

        try:
            response = call_llm_generic(prompt, provider=provider)
            llm_items = response.get("opportunities", [])
            if not isinstance(llm_items, list):
                llm_items = []

            matched_items = {}
            for entry in llm_items:
                if not isinstance(entry, dict):
                    continue
                raw_index = entry.get("index")
                if not isinstance(raw_index, (int, float, str)):
                    continue
                try:
                    mapped_index = int(raw_index)
                except (TypeError, ValueError):
                    continue
                if mapped_index <= 0:
                    continue
                matched_items[mapped_index] = entry

            for j, item in enumerate(batch):
                llm_match = matched_items.get(j + 1)
                if llm_match:
                    item["description"] = llm_match.get("description", "")
                    item["price_range_low"] = llm_match.get("price_range_low", "")
                    item["price_range_high"] = llm_match.get("price_range_high", "")
                    item["priority"] = _normalize_priority(
                        llm_match.get("priority", "Unknown")
                    )
                    item["sourcing_notes"] = llm_match.get("sourcing_notes", "")
                enriched.append(item)

        except Exception as e:
            logger.warning(
                f"LLM enrichment failed for batch {i // batch_size + 1}: {e}"
            )
            # Keep items without enrichment
            for item in batch:
                item["priority"] = "Unknown"
                item["sourcing_notes"] = f"LLM enrichment failed: {e}"
                enriched.append(item)

        if progress_callback:
            progress_callback(len(enriched), len(opportunities))

    return enriched


def write_opportunities_excel(
    opportunities: List[Dict],
    detail_rows: List[Dict],
    excel_path: Path,
):
    """
    Write New Product Opportunities to a formatted Excel workbook.

    Sheets:
      - 'New Product Opportunities' — deduplicated, enriched, sorted by priority
      - 'Gap Detail' — full source_category → missing_product_type for drill-down
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    excel_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # Styles
    header_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )
    header_font = Font(bold=True, size=11, color="FFFFFF")
    high_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    medium_fill = PatternFill(
        start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"
    )
    low_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    detail_fill = PatternFill(
        start_color="E8F0FE", end_color="E8F0FE", fill_type="solid"
    )

    priority_order = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3, "": 4}

    # ── Sheet 1: New Product Opportunities ──
    ws_opp: Any = wb.active
    ws_opp.title = "New Product Opportunities"

    opp_fields = [
        ("Product Type", "product_type"),
        ("Description", "description"),
        ("Priority", "priority"),
        ("Price Low", "price_range_low"),
        ("Price High", "price_range_high"),
        ("# Categories", "category_count"),
        ("Needed By", "source_categories_text"),
        ("Sourcing Notes", "sourcing_notes"),
    ]

    # Headers
    for col_idx, (header, _) in enumerate(opp_fields, 1):
        cell = ws_opp.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Sort by priority then by category count
    sorted_opps = sorted(
        opportunities,
        key=lambda x: (
            priority_order.get(x.get("priority", ""), 4),
            -x.get("category_count", 0),
        ),
    )

    # Data
    for row_idx, opp in enumerate(sorted_opps, 2):
        priority = opp.get("priority", "")
        fill = (
            high_fill
            if priority == "High"
            else medium_fill
            if priority == "Medium"
            else low_fill
        )

        for col_idx, (_, field) in enumerate(opp_fields, 1):
            if field == "source_categories_text":
                cats = opp.get("source_categories", [])
                value = ", ".join(cats[:5])
                if len(cats) > 5:
                    value += f" (+{len(cats) - 5} more)"
            elif field in ("price_range_low", "price_range_high"):
                raw = opp.get(field, "")
                try:
                    value = float(raw) if raw else ""
                except (ValueError, TypeError):
                    value = raw
            else:
                value = opp.get(field, "")

            cell = ws_opp.cell(row=row_idx, column=col_idx, value=value)
            cell.fill = fill

            if field in ("price_range_low", "price_range_high") and isinstance(
                value, (int, float)
            ):
                cell.number_format = "$#,##0.00"

    # Auto-size columns
    for col_idx in range(1, len(opp_fields) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(str(ws_opp.cell(row=r, column=col_idx).value or ""))
            for r in range(1, max(ws_opp.max_row, 2) + 1)
        )
        ws_opp.column_dimensions[col_letter].width = min(max_len + 3, 60)

    # ── Sheet 2: Gap Detail ──
    ws_detail: Any = wb.create_sheet("Gap Detail")

    detail_fields = [
        ("Source Category", "source_category"),
        ("Missing Product Type", "missing_product_type"),
    ]

    for col_idx, (header, _) in enumerate(detail_fields, 1):
        cell = ws_detail.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Sort detail rows by source category
    sorted_detail = sorted(detail_rows, key=lambda x: x.get("source_category", ""))

    for row_idx, row in enumerate(sorted_detail, 2):
        for col_idx, (_, field) in enumerate(detail_fields, 1):
            cell = ws_detail.cell(row=row_idx, column=col_idx, value=row.get(field, ""))
            cell.fill = detail_fill

    for col_idx in range(1, len(detail_fields) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(str(ws_detail.cell(row=r, column=col_idx).value or ""))
            for r in range(1, max(ws_detail.max_row, 2) + 1)
        )
        ws_detail.column_dimensions[col_letter].width = min(max_len + 3, 50)

    # ── Summary row at top of Sheet 1 ──
    # (We'll add a summary as a frozen pane header instead)
    ws_opp.freeze_panes = "A2"
    ws_detail.freeze_panes = "A2"

    wb.save(excel_path)

    stats = {
        "total_opportunities": len(opportunities),
        "high_priority": sum(1 for o in opportunities if o.get("priority") == "High"),
        "medium_priority": sum(
            1 for o in opportunities if o.get("priority") == "Medium"
        ),
        "low_priority": sum(1 for o in opportunities if o.get("priority") == "Low"),
        "detail_rows": len(detail_rows),
    }

    return stats
