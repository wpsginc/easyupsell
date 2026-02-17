# SDD: Cache Corruption and Error Handling

## 1. Gap Description
The cache module (`src/cache.py`) has 65 lines of critical infrastructure code with ZERO test coverage. This module handles SQLite database operations that can fail in multiple ways, and failures are currently silent.

**Severity:** P1 - HIGH  
**Impact:** Data loss, application crashes, silent failures

## 2. Target Location
**Test file:** `tests/test_cache.py` (create new)  
**Source under test:** `src/cache.py`

## 3. Test Strategy

### 3.1 Happy Path Testing
Verify cache works correctly under normal conditions:
- Set and get values
- Expiration handling (TTL)
- Clear cache
- Database initialization

### 3.2 Failure Mode Testing
Simulate real-world failure scenarios:
- Corrupted SQLite database file
- Disk full during write
- Invalid JSON in cache
- Concurrent access (race conditions)
- File permissions issues

### 3.3 Edge Case Testing
Test boundary conditions:
- Very large cached values (1MB+)
- Very long cache keys (1000+ chars)
- Expired entries (immediate expiration, far future)
- Empty database (no entries)

## 4. Implementation Details

### 4.1 Test Structure
```python
# tests/test_cache.py
import pytest
import sqlite3
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

from src.cache import Cache

@pytest.fixture
def temp_cache(tmp_path):
    """Create temporary cache for isolated testing"""
    db_path = tmp_path / "test_cache.db"
    cache = Cache(db_path=db_path)
    yield cache
    # Cleanup happens automatically with tmp_path


class TestCacheBasicOperations:
    """Test happy path cache operations"""
    
    def test_cache_init_creates_database(self, tmp_path):
        """Cache initialization creates SQLite database"""
        db_path = tmp_path / "cache.db"
        assert not db_path.exists()
        
        cache = Cache(db_path=db_path)
        
        assert db_path.exists()
        
        # Verify table structure
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cache'"
            )
            assert cursor.fetchone() is not None
    
    def test_set_and_get_value(self, temp_cache):
        """Store and retrieve value from cache"""
        temp_cache.set("test_key", {"data": "value"}, ttl_seconds=3600)
        
        result = temp_cache.get("test_key")
        
        assert result == {"data": "value"}
    
    def test_get_nonexistent_key_returns_none(self, temp_cache):
        """Getting non-existent key returns None"""
        result = temp_cache.get("does_not_exist")
        
        assert result is None
    
    def test_set_overwrites_existing_key(self, temp_cache):
        """Setting same key twice overwrites first value"""
        temp_cache.set("key", "value1")
        temp_cache.set("key", "value2")
        
        result = temp_cache.get("key")
        
        assert result == "value2"
    
    def test_cache_clear_removes_all_entries(self, temp_cache):
        """Clear removes all cached entries"""
        temp_cache.set("key1", "value1")
        temp_cache.set("key2", "value2")
        temp_cache.set("key3", "value3")
        
        temp_cache.clear()
        
        assert temp_cache.get("key1") is None
        assert temp_cache.get("key2") is None
        assert temp_cache.get("key3") is None


class TestCacheExpiration:
    """Test TTL and expiration handling"""
    
    def test_expired_entry_returns_none(self, temp_cache):
        """Expired cache entry returns None"""
        # Set with 1 second TTL
        temp_cache.set("key", "value", ttl_seconds=1)
        
        # Wait for expiration
        time.sleep(1.5)
        
        result = temp_cache.get("key")
        assert result is None
    
    def test_expired_entry_is_deleted(self, temp_cache, tmp_path):
        """Expired entry is removed from database"""
        temp_cache.set("key", "value", ttl_seconds=1)
        time.sleep(1.5)
        
        # Trigger expiration by getting
        temp_cache.get("key")
        
        # Verify deletion in database
        db_path = tmp_path / "test_cache.db"
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache WHERE key = 'key'")
            count = cursor.fetchone()[0]
            assert count == 0
    
    def test_not_expired_entry_returns_value(self, temp_cache):
        """Non-expired entry returns value"""
        # Set with 10 second TTL
        temp_cache.set("key", "value", ttl_seconds=10)
        
        # Immediately get (should not be expired)
        result = temp_cache.get("key")
        
        assert result == "value"
    
    def test_default_ttl_is_24_hours(self, temp_cache):
        """Default TTL is 86400 seconds (24 hours)"""
        temp_cache.set("key", "value")  # No TTL specified
        
        # Check database for expires_at timestamp
        db_path = temp_cache.db_path
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT expires_at FROM cache WHERE key = 'key'")
            expires_at = cursor.fetchone()[0]
        
        # Should expire ~24 hours from now
        expected_expiry = time.time() + 86400
        assert abs(expires_at - expected_expiry) < 10  # Allow 10s tolerance


class TestCacheDataTypes:
    """Test caching different data types"""
    
    def test_cache_dict(self, temp_cache):
        """Cache stores and retrieves dict"""
        data = {"name": "test", "count": 42, "active": True}
        temp_cache.set("dict_key", data)
        
        result = temp_cache.get("dict_key")
        assert result == data
    
    def test_cache_list(self, temp_cache):
        """Cache stores and retrieves list"""
        data = [1, 2, 3, "four", {"five": 5}]
        temp_cache.set("list_key", data)
        
        result = temp_cache.get("list_key")
        assert result == data
    
    def test_cache_string(self, temp_cache):
        """Cache stores and retrieves string"""
        temp_cache.set("str_key", "hello world")
        
        result = temp_cache.get("str_key")
        assert result == "hello world"
    
    def test_cache_number(self, temp_cache):
        """Cache stores and retrieves number"""
        temp_cache.set("int_key", 12345)
        temp_cache.set("float_key", 3.14159)
        
        assert temp_cache.get("int_key") == 12345
        assert temp_cache.get("float_key") == 3.14159
    
    def test_cache_none_value(self, temp_cache):
        """Cache can store None value (different from missing key)"""
        temp_cache.set("none_key", None)
        
        result = temp_cache.get("none_key")
        assert result is None
        
        # But we can't distinguish from missing key!
        # This might be a bug in the implementation


class TestCacheErrorHandling:
    """Test error handling and recovery"""
    
    def test_corrupted_json_returns_none(self, temp_cache, tmp_path):
        """Corrupted JSON in cache returns None instead of crashing"""
        # Manually insert invalid JSON into database
        db_path = tmp_path / "test_cache.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                ("bad_key", "{invalid json!!!", time.time() + 3600)
            )
        
        # Should return None, not raise exception
        result = temp_cache.get("bad_key")
        assert result is None
    
    def test_database_file_deleted_recreates(self, tmp_path):
        """If database file is deleted, cache recreates it"""
        db_path = tmp_path / "cache.db"
        cache = Cache(db_path=db_path)
        
        # Add some data
        cache.set("key", "value")
        assert cache.get("key") == "value"
        
        # Delete database file
        db_path.unlink()
        
        # Try to use cache again - should recreate DB
        cache2 = Cache(db_path=db_path)
        cache2.set("new_key", "new_value")
        assert cache2.get("new_key") == "new_value"
    
    def test_read_only_database_fails_gracefully(self, tmp_path):
        """Read-only database fails with clear error"""
        db_path = tmp_path / "readonly_cache.db"
        cache = Cache(db_path=db_path)
        
        # Make database read-only
        os.chmod(db_path, 0o444)
        
        # Try to write - should raise PermissionError or similar
        with pytest.raises(Exception) as exc_info:
            cache.set("key", "value")
        
        # Error should be clear (not silent failure)
        assert "permission" in str(exc_info.value).lower() or \
               "readonly" in str(exc_info.value).lower()
    
    def test_disk_full_during_write(self, temp_cache, monkeypatch):
        """Disk full error during cache write is handled"""
        # Mock sqlite3.connect to simulate disk full
        original_connect = sqlite3.connect
        
        def mock_connect_disk_full(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            original_execute = conn.execute
            
            def mock_execute(sql, *args):
                if "INSERT OR REPLACE" in sql:
                    raise sqlite3.OperationalError("database or disk is full")
                return original_execute(sql, *args)
            
            conn.execute = mock_execute
            return conn
        
        monkeypatch.setattr("sqlite3.connect", mock_connect_disk_full)
        
        # Should raise clear error
        with pytest.raises(sqlite3.OperationalError) as exc_info:
            temp_cache.set("key", "value")
        
        assert "disk is full" in str(exc_info.value)
    
    def test_concurrent_access_no_corruption(self, tmp_path):
        """Concurrent cache access doesn't corrupt database"""
        import threading
        
        db_path = tmp_path / "concurrent_cache.db"
        cache = Cache(db_path=db_path)
        
        errors = []
        
        def writer(key_prefix):
            try:
                for i in range(100):
                    cache.set(f"{key_prefix}_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)
        
        # Spawn 5 threads writing concurrently
        threads = [
            threading.Thread(target=writer, args=(f"thread_{i}",))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Check for errors
        assert len(errors) == 0, f"Concurrent access caused errors: {errors}"
        
        # Verify all writes succeeded
        # (500 total writes: 5 threads × 100 writes each)
        # Note: Some might be overwritten, but no corruption
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]
            # Should have ~500 entries (might be less if keys collide)
            assert count >= 400


class TestCacheLargeData:
    """Test cache with large data"""
    
    def test_cache_large_value(self, temp_cache):
        """Cache handles large values (1MB+)"""
        # Create 1MB string
        large_value = "x" * (1024 * 1024)
        
        temp_cache.set("large_key", large_value)
        result = temp_cache.get("large_key")
        
        assert result == large_value
    
    def test_cache_many_entries(self, temp_cache):
        """Cache handles many entries (10k+)"""
        # Store 10,000 entries
        for i in range(10000):
            temp_cache.set(f"key_{i}", {"index": i, "data": f"value_{i}"})
        
        # Verify random samples
        assert temp_cache.get("key_0")["index"] == 0
        assert temp_cache.get("key_5000")["index"] == 5000
        assert temp_cache.get("key_9999")["index"] == 9999
    
    def test_cache_complex_nested_data(self, temp_cache):
        """Cache handles deeply nested data structures"""
        complex_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "data": [1, 2, 3, {"nested": "value"}]
                            }
                        }
                    }
                }
            }
        }
        
        temp_cache.set("complex_key", complex_data)
        result = temp_cache.get("complex_key")
        
        assert result == complex_data


class TestCacheEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_key_string(self, temp_cache):
        """Empty string as key is allowed"""
        temp_cache.set("", "value for empty key")
        
        result = temp_cache.get("")
        assert result == "value for empty key"
    
    def test_very_long_key(self, temp_cache):
        """Very long key (1000+ chars) works"""
        long_key = "k" * 1000
        temp_cache.set(long_key, "value")
        
        result = temp_cache.get(long_key)
        assert result == "value"
    
    def test_special_characters_in_key(self, temp_cache):
        """Special characters in key are handled"""
        special_keys = [
            "key with spaces",
            "key/with/slashes",
            "key?with=params&more=stuff",
            "key\nwith\nnewlines",
            "key\twith\ttabs",
            "key'with\"quotes",
        ]
        
        for key in special_keys:
            temp_cache.set(key, f"value for {key}")
        
        for key in special_keys:
            result = temp_cache.get(key)
            assert result == f"value for {key}"
    
    def test_zero_ttl(self, temp_cache):
        """TTL of 0 means immediate expiration"""
        temp_cache.set("key", "value", ttl_seconds=0)
        
        # Should be immediately expired
        result = temp_cache.get("key")
        assert result is None
    
    def test_negative_ttl(self, temp_cache):
        """Negative TTL means already expired"""
        temp_cache.set("key", "value", ttl_seconds=-100)
        
        result = temp_cache.get("key")
        assert result is None
    
    def test_very_large_ttl(self, temp_cache):
        """Very large TTL (100 years) works"""
        # 100 years in seconds
        temp_cache.set("key", "value", ttl_seconds=100 * 365 * 24 * 3600)
        
        result = temp_cache.get("key")
        assert result == "value"


class TestCacheIntegration:
    """Test cache integration with BigCommerceClient"""
    
    def test_bigcommerce_client_uses_cache(self, tmp_path, monkeypatch):
        """BigCommerceClient actually uses cache"""
        # This would test that src/bigcommerce/client.py uses cache
        # Requires mocking BC API and verifying cache hits
        
        # For now, just verify cache is instantiated
        from src.bigcommerce.client import BigCommerceClient
        
        client = BigCommerceClient(
            store_hash="test_hash",
            access_token="test_token"
        )
        
        assert hasattr(client, "cache")
        assert isinstance(client.cache, Cache)
```

### 4.2 Observability Improvements
Add to `src/cache.py`:
```python
class Cache:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.DATA_DIR / "cache.db")
        self._hits = 0
        self._misses = 0
        self._init_db()
    
    def get(self, key: str) -> Optional[Any]:
        result = self._get_internal(key)
        if result is None:
            self._misses += 1
        else:
            self._hits += 1
        return result
    
    def stats(self) -> dict:
        """Return cache statistics"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }
```

Add test for stats:
```python
def test_cache_stats_tracking(temp_cache):
    """Cache tracks hit/miss statistics"""
    temp_cache.set("key1", "value1")
    
    # 1 hit
    temp_cache.get("key1")
    # 1 miss
    temp_cache.get("key2")
    # 1 hit
    temp_cache.get("key1")
    
    stats = temp_cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 2/3
```

## 5. Recommended Executor
**Demon:** rem_testing  
**Reason:** Pure unit testing of infrastructure code, no external dependencies

## 6. Dependencies
- pytest
- No external libraries needed (pure Python + SQLite)

## 7. Estimated Effort
**Test Implementation:** 6-8 hours  
**Bug fixes discovered:** 2-4 hours  
**Total:** ~1-2 days

## 8. Success Criteria
- ✅ 100% code coverage of `src/cache.py`
- ✅ All happy path tests pass
- ✅ All error scenarios handled gracefully (no silent failures)
- ✅ Concurrent access doesn't corrupt database
- ✅ Performance acceptable (1000 writes/sec minimum)

## 9. Known Issues in Current Implementation

Based on code review of `src/cache.py`, these bugs exist:

1. **Silent JSON failures:** Line 46-48 catches JSONDecodeError but returns None (indistinguishable from cache miss)
2. **No logging:** Errors are swallowed without logging
3. **No metrics:** Can't measure cache effectiveness
4. **Race conditions:** No locking for concurrent access
5. **No cleanup:** Expired entries accumulate in database (no periodic cleanup)

## 10. Follow-up SDDs
After implementing this SDD:
- **SDD-Performance-CacheMetrics** — Add observability (hit rate, size, cleanup)
- **SDD-Performance-CacheCleanup** — Implement periodic expired entry cleanup
- **SDD-ErrorHandling-CacheLogging** — Add structured logging for cache operations
