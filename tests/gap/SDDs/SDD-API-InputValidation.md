# SDD: API Input Validation

## 1. Gap Description
The FastAPI endpoints accept path parameters (`category_name`, `sku`, `netsuite_id`) and query parameters (`min_score`, `limit`) with minimal validation.
- `category_name` and `sku` have no length limits or character restrictions.
- `netsuite_id` is not validated (e.g., should be numeric or specific format?).

**Risks:**
- **DoS**: Sending 1MB string as `sku` could impact DB performance or logging.
- **Data Integrity**: Weird characters might confuse downstream systems or logs.

## 2. Target Location
`tests/gap/test_api_validation.py`

## 3. Test Strategy
1.  **Length Limit**: Send a request with a 10k character `sku`. Expect 422 or 400.
2.  **Special Characters**: Send URL-encoded null bytes or control characters.
3.  **NetSuite ID Format**: Send non-numeric ID (if strict numeric is required) or extremely long ID.

## 4. Implementation Details
- Use `fastapi.testclient.TestClient`.
- Define reasonable limits (e.g., SKU max 255 chars, Category max 255 chars).
- The test should assert that the API rejects invalid inputs *before* hitting the DB layer (or DB layer handles it gracefully without 500).
