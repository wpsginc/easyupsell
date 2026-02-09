"""
Candidate Filter — Unified filtering for recommendation candidates.

Replaces the ad-hoc filtering logic in recommend_items.py,
recommend_items_full.py, and analyzer.py with a single, tested function.

Key design decision: We do NOT exclude items that share a category_id
with the source. Instead, we tag them with same_category=True and let
the LLM decide if the pairing is valid (accessory, part, upgrade).
"""


def filter_candidates(
    category: dict,
    items: list[dict],
    exclude_exact_match: bool = True,
) -> list[dict]:
    """
    Filter candidate items for a source category.

    Args:
        category: Source category dict with "id" and "name" keys.
        items: List of candidate item dicts, each with at least
               "name" (str) and "categories" (list[int]).
        exclude_exact_match: If True, exclude items whose name
                             exactly matches the category name
                             (case-insensitive, stripped).

    Returns:
        Filtered list of items, each augmented with a "same_category"
        boolean flag indicating whether the item shares a category_id
        with the source.
    """
    cat_id = category.get("id")
    cat_name = category.get("name", "").strip().lower()

    filtered = []
    for item in items:
        item_name = item.get("name", "").strip().lower()

        # Exclude items whose name exactly equals the category name.
        # e.g., a product literally called "Fire Helmets" for the
        # "Fire Helmets" category — that's a duplicate, not a recommendation.
        if exclude_exact_match and item_name == cat_name:
            continue

        # Tag whether this item shares a category_id with the source.
        item_categories = item.get("categories", [])
        same_category = cat_id is not None and cat_id in item_categories

        # Shallow copy to avoid mutating the original item dict.
        tagged_item = {**item, "same_category": same_category}
        filtered.append(tagged_item)

    return filtered
