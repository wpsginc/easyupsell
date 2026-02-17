"""
Dark Horse Review — Post-processing pass to score and filter pairings.

Reads the raw dark horse Excel, sends pairings to an LLM in batches
for relevance scoring, and outputs a cleaned workbook with scores.

Designed to use a different (faster/stricter) model than the one
that generated the pairings. E.g. GLM brainstorms → GPT-OSS reviews.
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from validate_category_pairings import call_llm_generic


def load_pairings_from_excel(excel_path: Path) -> List[Dict]:
    """Load pairings from the Dark Horse Excel workbook."""
    from openpyxl import load_workbook
    
    wb = load_workbook(excel_path, read_only=True)
    ws = wb["Dark Horse Pairings"]
    
    # Read headers from row 1
    headers = [cell.value for cell in ws[1]]
    
    pairings = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        record = dict(zip(headers, row))
        if record.get("source_category"):  # skip empty rows
            pairings.append(record)
    
    wb.close()
    return pairings


def review_batch(pairings_batch: List[Dict], provider: str = "athena") -> List[Dict]:
    """
    Send a batch of pairings to an LLM for relevance scoring.
    
    Returns list of dicts with:
      - source_category, target_category, concept_matched (from input)
      - relevance_score (1-5)
      - keep (bool)
      - review_note (optional explanation for rejects)
    """
    # Build a compact summary for the LLM
    batch_text = "\n".join(
        f"{i+1}. {p['source_category']} → {p['target_category']} "
        f"(concept: {p.get('concept_matched', 'unknown')}, "
        f"type: {p.get('relationship_type', 'unknown')})"
        for i, p in enumerate(pairings_batch)
    )
    
    prompt = f"""You are a retail merchandising quality reviewer.

Review these product pairing recommendations and score each one on relevance (1-5):
  5 = Essential pairing (batteries for flashlights)
  4 = Strong pairing (socks for boots)
  3 = Reasonable pairing (might cross-sell)
  2 = Weak pairing (tenuous connection)
  1 = Irrelevant/hallucination (fertilizer for rescue equipment)

Pairings to review:
{batch_text}

For each pairing, output:
{{
  "reviews": [
    {{"index": 1, "score": 5, "keep": true}},
    {{"index": 2, "score": 1, "keep": false, "note": "reason for rejection"}},
    ...
  ]
}}"""
    
    try:
        response = call_llm_generic(prompt, provider=provider)
    except Exception as e:
        # On failure, keep everything (don't silently drop)
        return [
            {**p, "relevance_score": -1, "keep": True, "review_note": f"Review failed: {e}"}
            for p in pairings_batch
        ]
    
    reviews = response.get("reviews", [])
    
    # Merge review scores back into pairings
    scored = []
    for i, p in enumerate(pairings_batch):
        # Find matching review by index (1-based)
        review = next((r for r in reviews if r.get("index") == i + 1), None)
        
        if review:
            scored.append({
                **p,
                "relevance_score": review.get("score", 3),
                "keep": review.get("keep", True),
                "review_note": review.get("note", ""),
            })
        else:
            # Review didn't return score for this item — keep it
            scored.append({
                **p,
                "relevance_score": -1,
                "keep": True,
                "review_note": "Missing from review response",
            })
    
    return scored


def save_checkpoint(scored: List[Dict], next_index: int, checkpoint_path: Path):
    """Save review progress to a JSON checkpoint file."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"scored": scored, "next_index": next_index}
    # Write to temp file first, then rename for atomicity
    tmp_path = checkpoint_path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    tmp_path.rename(checkpoint_path)
    logger.debug(f"Checkpoint saved: {len(scored)} scored, next_index={next_index}")


def load_checkpoint(checkpoint_path: Path) -> tuple:
    """Load review progress from a JSON checkpoint file.
    
    Returns:
        (scored_list, next_index) or ([], 0) if no checkpoint exists.
    """
    if not checkpoint_path.exists():
        return [], 0
    
    with open(checkpoint_path, "r") as f:
        data = json.load(f)
    
    scored = data.get("scored", [])
    next_index = data.get("next_index", 0)
    logger.debug(f"Checkpoint loaded: {len(scored)} scored, next_index={next_index}")
    return scored, next_index


def review_all_pairings(
    pairings: List[Dict],
    provider: str = "athena",
    batch_size: int = 15,
    progress_callback=None,
    checkpoint_path: Optional[Path] = None,
    resume: bool = False,
) -> List[Dict]:
    """Review all pairings in batches. Returns scored pairings.
    
    Args:
        checkpoint_path: Path for checkpoint file. If None, no checkpointing.
        resume: If True and checkpoint exists, resume from last checkpoint.
    """
    all_scored = []
    start_index = 0
    
    # Resume from checkpoint if requested
    if resume and checkpoint_path:
        all_scored, start_index = load_checkpoint(checkpoint_path)
        if all_scored:
            logger.info(f"Resuming from checkpoint: {len(all_scored)} already scored, starting at index {start_index}")
    
    for i in range(start_index, len(pairings), batch_size):
        batch = pairings[i:i + batch_size]
        scored = review_batch(batch, provider=provider)
        all_scored.extend(scored)
        
        # Save checkpoint after each batch
        if checkpoint_path:
            save_checkpoint(all_scored, i + len(batch), checkpoint_path)
        
        if progress_callback:
            progress_callback(len(all_scored), len(pairings))
    
    # Clean up checkpoint on successful completion
    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.debug("Checkpoint removed after successful completion")
    
    return all_scored


def write_reviewed_excel(
    scored_pairings: List[Dict],
    gaps: List[Dict],
    excel_path: Path,
    min_score: int = 2,
):
    """
    Write reviewed results to Excel with scores.
    
    Sheets:
      - 'Reviewed Pairings' — all pairings with relevance_score, sorted by score desc
      - 'Rejected' — pairings scored below min_score (red)
      - 'Catalog Gaps' — gaps (unchanged from discovery)
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    excel_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, size=11, color="FFFFFF")
    keep_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    reject_fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
    gap_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    priority_fill = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")

    fields = [
        "source_category",
        "target_category",
        "target_sku",
        "concept_matched",
        "match_confidence",
        "relationship_type",
        "sales_velocity",
        "margin_pct",
        "copurchase_count",
        "relevance_score",
        "review_note",
        "high_priority",
    ]

    # Split into keeps and rejects
    keeps = [p for p in scored_pairings if p.get("keep", True) and p.get("relevance_score", 0) >= min_score]
    rejects = [p for p in scored_pairings if not p.get("keep", True) or p.get("relevance_score", 0) < min_score]

    # Sort keeps by relevance score descending
    keeps.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    def _write_sheet(ws, data, fill, sheet_fields):
        for col_idx, field in enumerate(sheet_fields, 1):
            cell = ws.cell(row=1, column=col_idx, value=field)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for row_idx, p in enumerate(data, 2):
            is_priority = p.get("high_priority", False)
            row_fill = priority_fill if is_priority else fill
            for col_idx, field in enumerate(sheet_fields, 1):
                value = p.get(field, "")
                if field == "match_confidence":
                    try:
                        value = float(value) if value else 0.0
                    except (ValueError, TypeError):
                        value = 0.0
                elif field == "margin_pct":
                    try:
                        value = float(value) if value else 0.0
                    except (ValueError, TypeError):
                        value = 0.0
                elif field == "high_priority":
                    value = "★" if value else ""
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.fill = row_fill
                if field == "match_confidence":
                    cell.number_format = '0%'
                elif field == "margin_pct":
                    cell.number_format = '0.0%'

        for col_idx in range(1, len(sheet_fields) + 1):
            col_letter = get_column_letter(col_idx)
            max_len = max(
                len(str(ws.cell(row=r, column=col_idx).value or ""))
                for r in range(1, max(ws.max_row, 2) + 1)
            )
            ws.column_dimensions[col_letter].width = min(max_len + 3, 50)

    # Sheet 1: Reviewed (keeps)
    ws_keep = wb.active
    ws_keep.title = "Reviewed Pairings"
    _write_sheet(ws_keep, keeps, keep_fill, fields)

    # Sheet 2: Rejected
    if rejects:
        ws_reject = wb.create_sheet("Rejected")
        _write_sheet(ws_reject, rejects, reject_fill, fields)

    # Sheet 3: Catalog Gaps
    ws_gaps = wb.create_sheet("Catalog Gaps")
    gap_fields = ["source_category", "missing_product_type"]
    for col_idx, field in enumerate(gap_fields, 1):
        cell = ws_gaps.cell(row=1, column=col_idx, value=field)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    for row_idx, g in enumerate(gaps, 2):
        row_data = {
            "source_category": g.get("source_category", g.get("source", "")),
            "missing_product_type": g.get("missing_product_type", g.get("missing_concept", "")),
        }
        for col_idx, field in enumerate(gap_fields, 1):
            cell = ws_gaps.cell(row=row_idx, column=col_idx, value=row_data.get(field, ""))
            cell.fill = gap_fill
    for col_idx in range(1, len(gap_fields) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(str(ws_gaps.cell(row=r, column=col_idx).value or ""))
            for r in range(1, max(ws_gaps.max_row, 2) + 1)
        )
        ws_gaps.column_dimensions[col_letter].width = min(max_len + 3, 50)

    wb.save(excel_path)
    
    return {"keeps": len(keeps), "rejects": len(rejects), "gaps": len(gaps)}
