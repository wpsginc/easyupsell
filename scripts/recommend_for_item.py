#!/usr/bin/env python3
"""
Item-Specific Recommendation Analysis

Finds upsell candidates for a SPECIFIC source product (by SKU).
Focuses on finding accessories and complementary items.

Usage:
    python scripts/recommend_for_item.py --sku STR-69140
"""

import argparse
import sys
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce.client import BigCommerceClient
from config import settings
from validate_category_pairings import get_batch_llm_validation

console = Console()

def get_candidates(client: BigCommerceClient, source_product: dict, limit: int = 50) -> list[dict]:
    """
    Get candidate items for upsell.
    Strategies:
    1. Items in the same category (likely accessories if source is a main item).
    2. High-value general items (flashlights, tools).
    """
    candidates = []
    seen_ids = {source_product["id"]}
    
    # Strategy 1: Same Category Items (Top 30)
    cat_ids = source_product.get("categories", [])
    if cat_ids:
        # Get items from the first category
        # Note: In a real DB, we'd query by category_id directly. 
        # API doesn't allow easy filtering by category in basic call without iterating.
        # But we can try fetching products and filtering.
        pass
        
    # Fallback/General: Get top items generally (reusing logic from full recommendation)
    # Ideally, we should have a cached list of "good upsells".
    # For now, we'll fetch a batch of products and filter.
    
    products = client.get_products(limit=200) # Fetch a batch
    
    priority_brands = ["streamlight", "benchmade", "channellock", "pelican", "gerber"]
    
    for p in products:
        if p["id"] in seen_ids:
            continue
            
        # Basic viability filter
        price = float(p.get("price", 0) or 0)
        if not (10 <= price <= 200):
            continue
            
        candidates.append({
            "id": p["id"],
            "name": p["name"],
            "sku": p["sku"],
            "price": price,
            "brand": p.get("brand_id", 0), # Name would be better but ID is what we get often
            "categories": p.get("categories", [])
        })
        
        if len(candidates) >= limit:
            break
            
    return candidates

def validate_item_upsells(source_item: dict, candidates: list[dict], provider: str) -> list[dict]:
    """
    Validate pairings using Item->Item prompt logic.
    """
    # Prepare batch for LLM
    batch_items = [
        {"name": c["name"], "sku": c["sku"], "brand": str(c.get("brand", ""))} 
        for c in candidates
    ]
    
    # We use the existing category validation function but we pass the Item Name as the "Category"
    # This works because the prompt says "A customer is buying from: '{source_category}'"
    # If we pass "Streamlight Fire Vulcan LED Lantern", the LLM understands it's a specific product.
    
    results = get_batch_llm_validation(
        source_item["name"], # Pass item name as context
        batch_items,
        provider=provider,
        max_items=settings.MAX_BATCH_SIZE
    )
    
    # Merge results
    validated = []
    for i, res in enumerate(results):
        candidate = candidates[i] if i < len(candidates) else {}
        validated.append({
            **candidate,
            "llm_valid": res.get("valid"),
            "llm_confidence": res.get("confidence"),
            "llm_reason": res.get("reason")
        })
        
    return validated

def main():
    parser = argparse.ArgumentParser(description="Find upsells for a specific SKU")
    parser.add_argument("--sku", required=True, help="Source Product SKU")
    parser.add_argument("--limit", type=int, default=20, help="Number of candidates to evaluate")
    parser.add_argument("--provider", default=settings.DEFAULT_PROVIDER, help="LLM Provider")
    args = parser.parse_args()
    
    try:
        client = BigCommerceClient.from_env()
    except Exception as e:
        console.print(f"[red]Connection Error: {e}[/red]")
        return
        
    # 1. Fetch Source Product
    console.print(f"Fetching SKU: [bold]{args.sku}[/bold]...")
    product = client.get_product_by_sku(args.sku)
    
    if not product:
        console.print(f"[red]SKU {args.sku} not found![/red]")
        return
        
    console.print(f"Found: [green]{product['name']}[/green] (${product['price']})")
    
    # 2. Get Candidates
    console.print(f"Finding candidates (limit {args.limit})...")
    candidates = get_candidates(client, product, limit=args.limit)
    console.print(f"Found {len(candidates)} candidates.")
    
    # 3. Validate
    console.print(f"Validating with {args.provider}...")
    results = validate_item_upsells(product, candidates, args.provider)
    
    # 4. Display Results
    table = Table(title=f"Recommendations for {product['name']}")
    table.add_column("Candidate SKU")
    table.add_column("Name")
    table.add_column("Price")
    table.add_column("Valid")
    table.add_column("Reason")
    
    for r in results:
        valid_mark = "✅" if r.get("llm_valid") else "❌"
        if r.get("llm_valid"):
            table.add_row(
                r["sku"],
                r["name"][:40],
                f"${r['price']}",
                valid_mark,
                r.get("llm_reason", "")[:50]
            )
            
    console.print(table)

if __name__ == "__main__":
    main()
