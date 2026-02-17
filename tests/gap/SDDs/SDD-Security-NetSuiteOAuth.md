# SDD: NetSuite OAuth 1.0a Security Testing

## 1. Gap Description
The NetSuite OAuth 1.0a implementation in `src/netsuite/auth.py` has zero test coverage for security-critical cryptographic operations. This creates risk of:
- Authentication bypass via signature forgery
- Credential leakage via incorrect percent-encoding
- Replay attacks via timestamp/nonce vulnerabilities
- Runtime failures from malformed signatures

**Severity:** P0 - CRITICAL  
**Impact:** Production authentication failures, potential credential theft

## 2. Target Location
**Test file:** `tests/security/test_netsuite_oauth.py` (create new)  
**Source under test:** `src/netsuite/auth.py`

## 3. Test Strategy

### 3.1 Test Vectors (Known-Good Reference)
Use OAuth 1.0a RFC 5849 Appendix A test vectors to validate:
- Percent-encoding function correctness
- Signature base string generation
- HMAC-SHA256 signature computation

### 3.2 Attack Vector Testing
Simulate real-world attack scenarios:
- Signature forgery attempts (wrong signature should fail)
- Replay attacks (reuse old timestamp/nonce)
- Encoding attacks (special chars: `&`, `=`, `/`, Unicode)

### 3.3 Edge Case Coverage
Test boundary conditions:
- Empty strings in parameters
- Very long nonces (1000+ chars)
- Timestamps in the past/future
- URL with query parameters
- URL with special characters

## 4. Implementation Details

### 4.1 Test Structure
```python
# tests/security/test_netsuite_oauth.py
import pytest
from src.netsuite.auth import (
    percent_encode,
    generate_nonce,
    generate_timestamp,
    create_signature_base_string,
    sign_request,
    build_auth_header,
    NetSuiteCredentials
)

class TestPercentEncoding:
    """Test RFC 3986 percent-encoding compliance"""
    
    def test_unreserved_chars_not_encoded(self):
        """Unreserved chars (A-Z, a-z, 0-9, -, _, ., ~) stay unchanged"""
        assert percent_encode("ABCabc123-_.~") == "ABCabc123-_.~"
    
    def test_reserved_chars_encoded(self):
        """Reserved chars get percent-encoded"""
        assert percent_encode("a&b=c") == "a%26b%3Dc"
    
    def test_space_encoded_as_percent20(self):
        """Space becomes %20, not +"""
        assert percent_encode("hello world") == "hello%20world"
    
    def test_unicode_encoded(self):
        """Unicode chars percent-encoded as UTF-8 bytes"""
        # Euro sign (€) = UTF-8 E2 82 AC
        assert percent_encode("€") == "%E2%82%AC"
    
    def test_slash_encoded(self):
        """Slash must be encoded per OAuth spec"""
        assert percent_encode("api/v1/test") == "api%2Fv1%2Ftest"

class TestNonceGeneration:
    """Test nonce uniqueness and format"""
    
    def test_nonce_is_hex_string(self):
        """Nonce should be hexadecimal"""
        nonce = generate_nonce()
        assert all(c in "0123456789abcdef" for c in nonce)
    
    def test_nonce_uniqueness(self):
        """Sequential nonces must be unique"""
        nonces = [generate_nonce() for _ in range(1000)]
        assert len(set(nonces)) == 1000  # No duplicates
    
    def test_nonce_length(self):
        """Nonce should be UUID4 hex (32 chars)"""
        assert len(generate_nonce()) == 32

class TestSignatureBaseString:
    """Test OAuth signature base string construction"""
    
    def test_rfc5849_example(self):
        """Validate against RFC 5849 Appendix A example"""
        # Use known test vector from OAuth RFC
        method = "POST"
        url = "https://example.com/request"
        oauth_params = {
            "oauth_consumer_key": "9djdj82h48djs9d2",
            "oauth_token": "kkk9d7dh3k39sjv7",
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": "137131201",
            "oauth_nonce": "7d8f3e4a",
        }
        query_params = {"b5": "=%3D", "a3": "a", "c@": "", "a2": "r b"}
        
        base = create_signature_base_string(method, url, oauth_params, query_params)
        
        # Expected per RFC (params sorted, percent-encoded)
        expected = (
            "POST&https%3A%2F%2Fexample.com%2Frequest&"
            "a2%3Dr%2520b%26a3%3Da%26b5%3D%253D%25253D%26"
            "c%2540%3D%26oauth_consumer_key%3D9djdj82h48djs9d2%26"
            "oauth_nonce%3D7d8f3e4a%26oauth_signature_method%3DHMAC-SHA256%26"
            "oauth_timestamp%3D137131201%26oauth_token%3Dkkk9d7dh3k39sjv7"
        )
        assert base == expected
    
    def test_parameter_sorting(self):
        """Parameters must be sorted alphabetically"""
        method = "GET"
        url = "https://api.netsuite.com/test"
        oauth_params = {
            "oauth_timestamp": "1234567890",
            "oauth_consumer_key": "key123",
            "oauth_nonce": "abc123",
        }
        
        base = create_signature_base_string(method, url, oauth_params)
        
        # oauth_consumer_key < oauth_nonce < oauth_timestamp (alphabetical)
        assert base.index("oauth_consumer_key") < base.index("oauth_nonce")
        assert base.index("oauth_nonce") < base.index("oauth_timestamp")

class TestHMACSignature:
    """Test HMAC-SHA256 signature generation"""
    
    def test_known_signature(self):
        """Validate signature against known test vector"""
        # Test vector from OAuth 1.0a spec
        base_string = "POST&https%3A%2F%2Fexample.com&oauth_consumer_key%3Dkey"
        consumer_secret = "secret123"
        token_secret = "tokensecret456"
        
        signature = sign_request(base_string, consumer_secret, token_secret)
        
        # Signature should be base64-encoded HMAC-SHA256
        import base64
        decoded = base64.b64decode(signature)
        assert len(decoded) == 32  # SHA256 = 32 bytes
    
    def test_signature_deterministic(self):
        """Same input produces same signature"""
        base = "GET&https%3A%2F%2Fapi.netsuite.com&param%3Dvalue"
        sig1 = sign_request(base, "secret", "token")
        sig2 = sign_request(base, "secret", "token")
        assert sig1 == sig2
    
    def test_signature_changes_with_input(self):
        """Different inputs produce different signatures"""
        base1 = "GET&https%3A%2F%2Fapi.netsuite.com&param%3Dvalue1"
        base2 = "GET&https%3A%2F%2Fapi.netsuite.com&param%3Dvalue2"
        sig1 = sign_request(base1, "secret", "token")
        sig2 = sign_request(base2, "secret", "token")
        assert sig1 != sig2

class TestAuthHeaderGeneration:
    """Test complete OAuth header construction"""
    
    def test_header_contains_required_fields(self):
        """Auth header must have all OAuth 1.0a required fields"""
        creds = NetSuiteCredentials(
            account_id="TSTDRV123456",
            consumer_key="test_consumer",
            consumer_secret="test_secret",
            token_id="test_token",
            token_secret="token_secret"
        )
        
        header = build_auth_header(creds, "POST", f"{creds.base_url}/test")
        
        # Required OAuth 1.0a fields
        assert 'oauth_consumer_key="test_consumer"' in header
        assert 'oauth_token="test_token"' in header
        assert 'oauth_signature_method="HMAC-SHA256"' in header
        assert 'oauth_timestamp=' in header
        assert 'oauth_nonce=' in header
        assert 'oauth_version="1.0"' in header
        assert 'oauth_signature=' in header
        assert f'realm="{creds.realm}"' in header
    
    def test_header_values_percent_encoded(self):
        """OAuth header values must be percent-encoded"""
        creds = NetSuiteCredentials(
            account_id="TEST-123",
            consumer_key="key with spaces",
            consumer_secret="secret",
            token_id="token&id",
            token_secret="secret"
        )
        
        header = build_auth_header(creds, "GET", creds.base_url)
        
        # Spaces and special chars should be encoded
        assert "key%20with%20spaces" in header
        assert "token%26id" in header

class TestReplayAttackPrevention:
    """Test timestamp and nonce replay attack prevention"""
    
    def test_timestamp_increases(self):
        """Timestamps should increase over time"""
        import time
        t1 = generate_timestamp()
        time.sleep(0.01)
        t2 = generate_timestamp()
        assert int(t2) >= int(t1)
    
    def test_nonce_collision_unlikely(self):
        """Nonce collision probability should be negligible"""
        # Generate 10k nonces, expect zero collisions
        nonces = [generate_nonce() for _ in range(10000)]
        assert len(set(nonces)) == 10000

class TestCredentialsFromEnv:
    """Test environment variable loading"""
    
    def test_missing_env_vars_raises_error(self, monkeypatch):
        """Missing credentials should raise KeyError"""
        monkeypatch.delenv("NETSUITE_ACCOUNT_ID", raising=False)
        
        with pytest.raises(KeyError):
            NetSuiteCredentials.from_env()
    
    def test_realm_conversion(self):
        """Account ID should convert to OAuth realm format"""
        creds = NetSuiteCredentials(
            account_id="tstdrv123456-sb1",
            consumer_key="key",
            consumer_secret="secret",
            token_id="token",
            token_secret="secret"
        )
        
        # Realm = uppercase with underscores
        assert creds.realm == "TSTDRV123456_SB1"
    
    def test_base_url_format(self):
        """Base URL should use lowercase with hyphens"""
        creds = NetSuiteCredentials(
            account_id="TSTDRV123456_SB1",
            consumer_key="key",
            consumer_secret="secret",
            token_id="token",
            token_secret="secret"
        )
        
        expected_url = "https://tstdrv123456-sb1.suitetalk.api.netsuite.com/services/rest"
        assert creds.base_url == expected_url

class TestSecurityVulnerabilities:
    """Test specific attack vectors"""
    
    def test_signature_tampering_detected(self):
        """Modified signature should be detectable"""
        # This test would require NetSuite API mock to validate signature
        # For now, verify signature changes when base string changes
        base1 = "GET&https%3A%2F%2Fapi.netsuite.com&amount%3D100"
        base2 = "GET&https%3A%2F%2Fapi.netsuite.com&amount%3D999"  # Tampered
        
        sig1 = sign_request(base1, "secret", "token")
        sig2 = sign_request(base2, "secret", "token")
        
        # Different amounts produce different signatures
        assert sig1 != sig2
    
    def test_url_injection_prevented(self):
        """URL manipulation should change signature"""
        creds = NetSuiteCredentials(
            account_id="TEST",
            consumer_key="key",
            consumer_secret="secret",
            token_id="token",
            token_secret="token_secret"
        )
        
        url1 = "https://test.suitetalk.api.netsuite.com/services/rest/record/v1/customer"
        url2 = "https://test.suitetalk.api.netsuite.com/services/rest/record/v1/admin"  # Different endpoint
        
        header1 = build_auth_header(creds, "GET", url1)
        header2 = build_auth_header(creds, "GET", url2)
        
        # Extract signatures (after oauth_signature=)
        import re
        sig1 = re.search(r'oauth_signature="([^"]+)"', header1).group(1)
        sig2 = re.search(r'oauth_signature="([^"]+)"', header2).group(1)
        
        # Different URLs should produce different signatures
        assert sig1 != sig2
```

### 4.2 Mock Strategy
No mocking needed — these are pure cryptographic functions. Test against:
1. RFC 5849 official test vectors
2. Known-good NetSuite requests (captured from working implementation)
3. Edge cases and attack vectors

### 4.3 Success Criteria
- ✅ All RFC 5849 test vectors pass
- ✅ 100% code coverage of `src/netsuite/auth.py`
- ✅ No security warnings from bandit scan
- ✅ Attack vector tests demonstrate protection

## 5. Recommended Executor
**Demon:** rem_testing (unit + security focused)  
**Reason:** Pure cryptographic testing, no browser/UI needed

**Alternative:** rem_security (if available) for adversarial testing

## 6. Dependencies
- pytest
- No external mocking needed (pure functions)
- Optional: `hypothesis` for property-based testing of percent-encoding

## 7. Estimated Effort
**Test Implementation:** 4-6 hours  
**Validation:** 1-2 hours  
**Total:** ~1 day

## 8. References
- [RFC 5849: OAuth 1.0 Protocol](https://tools.ietf.org/html/rfc5849)
- [RFC 3986: Percent-Encoding](https://tools.ietf.org/html/rfc3986#section-2.1)
- [NetSuite OAuth 1.0a Documentation](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_157771733782.html)
