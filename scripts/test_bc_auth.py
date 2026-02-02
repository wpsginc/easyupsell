#!/usr/bin/env python3
"""
Test BigCommerce API connectivity.

Usage:
    python scripts/test_bc_auth.py
    python scripts/test_bc_auth.py --product-id 5890
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient


def main():
    parser = argparse.ArgumentParser(description="Test BigCommerce API")
    parser.add_argument("--store", default="BC", help="Store prefix (BC, BC_TFS, etc)")
    parser.add_argument("--product-id", type=int, help="Fetch specific product by ID")
    parser.add_argument("--sku", help="Fetch product by SKU")
    args = parser.parse_args()

    print("BigCommerce API Test")
    print("=" * 50)

    try:
        client = BigCommerceClient.from_env(store_prefix=args.store)
        print(f"Store hash: {client.store_hash}")
        print()
    except ValueError as e:
        print(f"❌ {e}")
        print("\nAdd to .env:")
        print(f"  {args.store}_STORE_HASH=your_store_hash")
        print(f"  {args.store}_ACCESS_TOKEN=your_access_token")
        return 1

    # Test connection
    print("Testing connection...")
    result = client.test_connection()

    if not result["success"]:
        print(f"❌ Connection failed: {result.get('error')}")
        return 1

    print(f"✅ Connected to: {result.get('store_name')}")
    print(f"   Domain: {result.get('domain')}")
    print()

    # Fetch specific product
    if args.product_id:
        print(f"Fetching product {args.product_id}...")
        product = client.get_product(args.product_id)
        print(json.dumps(product, indent=2))

        print(f"\nRelated products: {client.get_related_products(args.product_id)}")

    # Fetch by SKU
    if args.sku:
        print(f"Fetching product with SKU: {args.sku}...")
        product = client.get_product_by_sku(args.sku)
        if product:
            print(f"Found: {product.get('name')} (ID: {product.get('id')})")
        else:
            print("Not found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
