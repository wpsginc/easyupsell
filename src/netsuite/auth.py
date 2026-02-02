"""
NetSuite OAuth 1.0a TBA Authentication

Implements Token-Based Authentication with HMAC-SHA256 signatures.
Ported from pim-sync for EasyUpsell integration.
"""

import base64
import hashlib
import hmac
import os
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class NetSuiteCredentials:
    account_id: str
    consumer_key: str
    consumer_secret: str
    token_id: str
    token_secret: str

    @property
    def realm(self) -> str:
        """OAuth realm - uppercase with underscore."""
        return self.account_id.upper().replace("-", "_")

    @property
    def base_url(self) -> str:
        """REST API base URL."""
        account = self.account_id.lower().replace("_", "-")
        return f"https://{account}.suitetalk.api.netsuite.com/services/rest"

    @classmethod
    def from_env(cls) -> "NetSuiteCredentials":
        """Load credentials from environment variables."""
        load_dotenv()
        return cls(
            account_id=os.environ["NETSUITE_ACCOUNT_ID"],
            consumer_key=os.environ["NETSUITE_CONSUMER_KEY"],
            consumer_secret=os.environ["NETSUITE_CONSUMER_SECRET"],
            token_id=os.environ["NETSUITE_TOKEN_ID"],
            token_secret=os.environ["NETSUITE_TOKEN_SECRET"],
        )


def percent_encode(s: str) -> str:
    """RFC 3986 percent-encoding."""
    return urllib.parse.quote(s, safe="")


def generate_nonce() -> str:
    """Generate unique nonce for each request."""
    return uuid.uuid4().hex


def generate_timestamp() -> str:
    """Unix timestamp as string."""
    return str(int(time.time()))


def create_signature_base_string(
    method: str,
    url: str,
    oauth_params: dict,
    query_params: Optional[dict] = None,
) -> str:
    """
    Create the signature base string per OAuth 1.0a spec.

    Parameters must be sorted alphabetically and percent-encoded.
    """
    # Combine OAuth params and query params
    all_params = dict(oauth_params)
    if query_params:
        all_params.update(query_params)

    # Sort and encode
    sorted_params = sorted(all_params.items())
    param_string = "&".join(
        f"{percent_encode(k)}={percent_encode(v)}" for k, v in sorted_params
    )

    # Create base string
    base_string = "&".join(
        [
            method.upper(),
            percent_encode(url),
            percent_encode(param_string),
        ]
    )

    return base_string


def sign_request(
    base_string: str,
    consumer_secret: str,
    token_secret: str,
) -> str:
    """
    Create HMAC-SHA256 signature.

    Signing key = consumer_secret&token_secret (both percent-encoded)
    """
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"

    signature = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return base64.b64encode(signature).decode("utf-8")


def build_auth_header(
    creds: NetSuiteCredentials,
    method: str,
    url: str,
    query_params: Optional[dict] = None,
) -> str:
    """
    Build the OAuth Authorization header for a request.
    """
    # OAuth parameters (without signature)
    oauth_params = {
        "oauth_consumer_key": creds.consumer_key,
        "oauth_token": creds.token_id,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": generate_timestamp(),
        "oauth_nonce": generate_nonce(),
        "oauth_version": "1.0",
    }

    # Create signature
    base_string = create_signature_base_string(method, url, oauth_params, query_params)
    signature = sign_request(base_string, creds.consumer_secret, creds.token_secret)
    oauth_params["oauth_signature"] = signature

    # Build header
    header_params = ", ".join(
        f'{k}="{percent_encode(v)}"' for k, v in sorted(oauth_params.items())
    )

    return f'OAuth realm="{creds.realm}", {header_params}'


if __name__ == "__main__":
    # Quick test - print auth header
    creds = NetSuiteCredentials.from_env()
    print(f"Account: {creds.account_id}")
    print(f"Realm: {creds.realm}")
    print(f"Base URL: {creds.base_url}")
    print()

    test_url = f"{creds.base_url}/query/v1/suiteql"
    header = build_auth_header(creds, "POST", test_url)
    print(f"Auth Header:\n{header[:100]}...")
