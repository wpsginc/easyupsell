#!/usr/bin/env python3
"""
Test NetSuite API connectivity.

Usage:
    python scripts/test_ns_auth.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from netsuite import NetSuiteClient


def main():
    print("NetSuite API Test")
    print("=" * 50)

    try:
        client = NetSuiteClient.from_env()
        print(f"Account: {client.creds.account_id}")
        print(f"Realm: {client.creds.realm}")
        print()
    except KeyError as e:
        print(f"❌ Missing environment variable: {e}")
        print("\nCopy .env.template to .env and fill in credentials.")
        return 1

    # Test connection
    print("Testing connection...")
    result = client.test_connection()

    if not result["success"]:
        print(f"❌ Connection failed: {result.get('error')}")
        return 1

    print(f"✅ Connected to account: {result.get('account_id')}")
    print()

    # Run a simple query
    print("Running test query...")
    try:
        result = client.suiteql("SELECT id, itemid FROM item LIMIT 5")
        items = result.get("items", [])
        print(f"Found {len(items)} items:")
        for item in items:
            print(f"  - {item.get('itemid')} (ID: {item.get('id')})")
    except Exception as e:
        print(f"Query failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
