"""
NetSuite REST API Client

Provides high-level methods for querying and updating NetSuite records.
"""

from typing import Any, Optional

import requests

from .auth import NetSuiteCredentials, build_auth_header


class NetSuiteClient:
    """NetSuite REST API Client with automatic OAuth 1.0a TBA authentication."""

    def __init__(self, creds: NetSuiteCredentials, timeout: int = 60):
        self.creds = creds
        self.timeout = timeout
        self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "NetSuiteClient":
        """Create client from environment variables."""
        return cls(NetSuiteCredentials.from_env())

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> requests.Response:
        """Make authenticated request to NetSuite."""
        auth_header = build_auth_header(self.creds, method, url, params)

        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "transient",
        }

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=headers,
            timeout=self.timeout,
        )

        return response

    def suiteql(self, query: str, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        """
        Execute a SuiteQL query.

        Args:
            query: The SuiteQL query string
            limit: Max records to return (default 1000)
            offset: Record offset for pagination

        Returns:
            Query response with items and pagination info
        """
        url = f"{self.creds.base_url}/query/v1/suiteql"
        params = {"limit": str(limit), "offset": str(offset)}

        response = self._request("POST", url, params=params, json={"q": query})
        response.raise_for_status()

        return response.json()

    def get_record(self, record_type: str, record_id: str) -> dict[str, Any]:
        """
        Get a single record by type and ID.

        Args:
            record_type: NetSuite record type (e.g., 'inventoryitem', 'customer')
            record_id: Internal ID of the record

        Returns:
            Record data
        """
        url = f"{self.creds.base_url}/record/v1/{record_type}/{record_id}"
        response = self._request("GET", url)
        response.raise_for_status()
        return response.json()

    def test_connection(self) -> dict[str, Any]:
        """Test connection and return account info."""
        try:
            # Simple query to verify credentials
            result = self.suiteql("SELECT 1 as test", limit=1)
            return {
                "success": True,
                "account_id": self.creds.account_id,
                "realm": self.creds.realm,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
            }


if __name__ == "__main__":
    # Quick test
    print("NetSuite Connection Test")
    print("=" * 50)

    try:
        client = NetSuiteClient.from_env()
        result = client.test_connection()

        if result["success"]:
            print(f"✅ Connected to account: {result['account_id']}")
        else:
            print(f"❌ Connection failed: {result['error']}")
    except KeyError as e:
        print(f"⚠️  Missing environment variable: {e}")
        print("\nCopy .env.template to .env and fill in credentials.")
