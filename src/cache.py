import sqlite3
import json
import time
from pathlib import Path
from typing import Any, Optional

from config import settings

class Cache:
    """Simple SQLite Cache for API responses."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.DATA_DIR / "cache.db")
        self._init_db()
        
    def _init_db(self):
        """Initialize cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at REAL
                )
            """)
            
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if valid."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
                
            value_json, expires_at = row
            
            if time.time() > expires_at:
                # Expired
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
                
            try:
                return json.loads(value_json)
            except json.JSONDecodeError:
                return None
                
    def set(self, key: str, value: Any, ttl_seconds: int = 86400):
        """Set value in cache (default 24h)."""
        expires_at = time.time() + ttl_seconds
        value_json = json.dumps(value)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, value_json, expires_at)
            )

    def clear(self):
        """Clear all cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
