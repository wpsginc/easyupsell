"""
BigCommerce V3 API Client

Provides access to products, variants, and related upsell functionality.
Ported from pim-sync for EasyUpsell integration.
"""

import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv


class BigCommerceClient:
    """Client for BigCommerce V3 REST API."""

    def __init__(
        self,
        store_hash: str,
        access_token: str,
        timeout: int = 60,
    ):
        self.store_hash = store_hash
        self.access_token = access_token
        self.timeout = timeout
        self.base_url = f"https://api.bigcommerce.com/stores/{store_hash}/v3"

        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    @classmethod
    def from_env(cls, store_prefix: str = "BC") -> "BigCommerceClient":
        """
        Create client from environment variables.

        Args:
            store_prefix: Prefix for env vars (e.g., "BC" for BC_STORE_HASH)
        """
        load_dotenv()

        store_hash = os.environ.get(f"{store_prefix}_STORE_HASH", "")
        access_token = os.environ.get(f"{store_prefix}_ACCESS_TOKEN", "")

        if not store_hash or not access_token:
            raise ValueError(
                f"Missing environment variables: {store_prefix}_STORE_HASH and "
                f"{store_prefix}_ACCESS_TOKEN required"
            )

        return cls(store_hash=store_hash, access_token=access_token)

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}/{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request to API."""
        url = f"{self.base_url}/{endpoint}"
        response = self.session.post(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make PUT request to API."""
        url = f"{self.base_url}/{endpoint}"
        response = self.session.put(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get_paginated(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """Get all pages of a paginated endpoint."""
        all_items = []
        page = 1
        params = params or {}
        params["limit"] = limit

        while True:
            params["page"] = page
            response = self._get(endpoint, params)
            data = response.get("data", [])

            if not data:
                break

            all_items.extend(data)

            # Check if there are more pages
            meta = response.get("meta", {}).get("pagination", {})
            total_pages = meta.get("total_pages", 1)

            if page >= total_pages:
                break

            page += 1

        return all_items

    # -------------------------------------------------------------------------
    # Products
    # -------------------------------------------------------------------------

    def get_product(self, product_id: int) -> dict[str, Any]:
        """Get a single product by ID."""
        response = self._get(f"catalog/products/{product_id}")
        return response.get("data", {})

    def get_products(
        self,
        limit: int = 250,
        sku: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get products with optional filtering."""
        params = {}
        if sku:
            params["sku"] = sku
        if name:
            params["name"] = name

        return self._get_paginated("catalog/products", params, limit)

    def get_product_by_sku(self, sku: str) -> Optional[dict[str, Any]]:
        """Get a product by SKU."""
        products = self.get_products(sku=sku, limit=1)
        return products[0] if products else None

    # -------------------------------------------------------------------------
    # Categories
    # -------------------------------------------------------------------------

    def get_category_tree(self) -> list[dict[str, Any]]:
        """Get the full category tree."""
        response = self._get("catalog/trees/categories")
        return response.get("data", [])

    def get_categories(self, limit: int = 250) -> list[dict[str, Any]]:
        """Get all categories (flat list)."""
        return self._get_paginated("catalog/categories", limit=limit)

    # -------------------------------------------------------------------------
    # Variants
    # -------------------------------------------------------------------------

    def get_product_variants(self, product_id: int) -> list[dict[str, Any]]:
        """Get all variants for a product."""
        return self._get_paginated(f"catalog/products/{product_id}/variants")

    # -------------------------------------------------------------------------
    # Related Products (for upsells)
    # -------------------------------------------------------------------------

    def get_related_products(self, product_id: int) -> list[int]:
        """Get related product IDs for a product."""
        product = self.get_product(product_id)
        return product.get("related_products", [])

    def set_related_products(
        self, product_id: int, related_ids: list[int]
    ) -> dict[str, Any]:
        """Set related products for upsell functionality."""
        return self._put(
            f"catalog/products/{product_id}",
            {"related_products": related_ids}
        )

    # -------------------------------------------------------------------------
    # Orders (for co-purchase analysis)
    # -------------------------------------------------------------------------

    def get_orders(
        self,
        min_date: Optional[str] = None,
        status_id: Optional[int] = None,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """
        Get orders with optional date/status filtering.
        
        Args:
            min_date: Minimum date in RFC 2822 format (e.g., "Mon, 01 Jan 2024 00:00:00 +0000")
            status_id: Filter by status (11=Completed, 10=Shipped)
        """
        # Orders are V2 API
        url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v2/orders"
        params = {"limit": limit}
        
        if min_date:
            params["min_date_created"] = min_date
        if status_id:
            params["status_id"] = status_id
        
        all_orders = []
        page = 1
        
        while True:
            params["page"] = page
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 204:  # No content
                break
                
            response.raise_for_status()
            orders = response.json()
            
            if not orders:
                break
            
            all_orders.extend(orders)
            page += 1
            
            if len(orders) < limit:
                break
        
        return all_orders

    def get_order_products(self, order_id: int) -> list[dict[str, Any]]:
        """Get products for a specific order."""
        url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v2/orders/{order_id}/products"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Connection Test
    # -------------------------------------------------------------------------

    def test_connection(self) -> dict[str, Any]:
        """Test the connection and return store info."""
        try:
            url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v2/store"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            store = response.json()

            return {
                "success": True,
                "store_name": store.get("name"),
                "domain": store.get("domain"),
                "secure_url": store.get("secure_url"),
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
            }


if __name__ == "__main__":
    # Quick test
    print("BigCommerce Connection Test")
    print("=" * 50)

    try:
        client = BigCommerceClient.from_env()
        result = client.test_connection()

        if result["success"]:
            print(f"✅ Connected to: {result['store_name']}")
            print(f"   Domain: {result['domain']}")
        else:
            print(f"❌ Connection failed: {result['error']}")
    except ValueError as e:
        print(f"⚠️  {e}")
        print("\nCopy .env.template to .env and fill in credentials.")
