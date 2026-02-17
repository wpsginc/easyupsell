"""
NetSuite REST API Client

Provides high-level methods for querying and updating NetSuite records.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Optional

import requests

from .auth import NetSuiteCredentials, build_auth_header


class NetSuiteError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")


class NetSuiteAuthError(NetSuiteError):
    pass


class NetSuiteValidationError(NetSuiteError):
    pass


class NetSuiteServerError(NetSuiteError):
    pass


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
    ) -> dict[str, Any]:
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

        if 200 <= response.status_code < 300:
            if response.status_code == 204:
                return {"status_code": response.status_code}
            try:
                return response.json()
            except ValueError:
                return {"status_code": response.status_code, "raw": response.text}

        self._raise_for_status(response)
        return {}

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        status = response.status_code
        message = response.text or "NetSuite API error"

        if status == 401:
            raise NetSuiteAuthError(status, message)
        if status in (400, 403, 404, 422):
            raise NetSuiteValidationError(status, message)
        if status in (429, 500, 502, 503, 504):
            raise NetSuiteServerError(status, message)
        raise NetSuiteError(status, message)

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

        return self._request("POST", url, params=params, json={"q": query})

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
        return self._request("GET", url)

    def create_record(self, record_type: str, data: dict) -> dict[str, Any]:
        """POST /record/v1/{record_type}."""
        url = f"{self.creds.base_url}/record/v1/{record_type}"
        return self._request("POST", url, json=data)

    def update_record(self, record_type: str, record_id: str, data: dict) -> dict[str, Any]:
        """PATCH /record/v1/{record_type}/{record_id}."""
        url = f"{self.creds.base_url}/record/v1/{record_type}/{record_id}"
        return self._request("PATCH", url, json=data)

    def upsert_record(self, record_type: str, external_id: str, data: dict) -> dict[str, Any]:
        """PUT /record/v1/{record_type}/eid:{external_id}."""
        encoded_external_id = urllib.parse.quote(external_id, safe="")
        url = f"{self.creds.base_url}/record/v1/{record_type}/eid:{encoded_external_id}"
        return self._request("PUT", url, json=data)

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
        except (requests.RequestException, NetSuiteError) as e:
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
