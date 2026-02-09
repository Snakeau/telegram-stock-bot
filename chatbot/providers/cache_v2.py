"""Enhanced caching layer for market data with SQLite persistence and TTL."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """
    Two-tier caching: RAM (fast) + SQLite (persistent).
    
    - RAM cache: In-memory with TTL, fast lookups
    - SQLite cache: Persistent storage, auto-expiry checking
    - Supports: JSON serialization, DataFrame pickling, string storage
    """
    
    def __init__(self, db_path: str = "market_cache.db"):
        """Initialize cache with SQLite backend."""
        self.db_path = db_path if db_path != ":memory:" else ":memory:"
        self.mem_cache: Dict[str, tuple[Any, datetime]] = {}
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if tables exist, create if not
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv_cache'")
                if not cursor.fetchone():
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS ohlcv_cache (
                            key TEXT PRIMARY KEY,
                            payload_parquet BLOB,
                            payload_json TEXT,
                            fetched_at TEXT NOT NULL,
                            ttl_seconds INTEGER NOT NULL
                        )
                    """)
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_meta_cache'")
                if not cursor.fetchone():
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS ticker_meta_cache (
                            key TEXT PRIMARY KEY,
                            payload_json TEXT NOT NULL,
                            fetched_at TEXT NOT NULL,
                            ttl_seconds INTEGER NOT NULL
                        )
                    """)
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='etf_facts_cache'")
                if not cursor.fetchone():
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS etf_facts_cache (
                            key TEXT PRIMARY KEY,
                            payload_json TEXT NOT NULL,
                            fetched_at TEXT NOT NULL,
                            ttl_seconds INTEGER NOT NULL
                        )
                    """)
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def get_ohlcv(self, key: str, ttl_seconds: int = 3600) -> Optional[pd.DataFrame]:
        """
        Retrieve OHLCV data (DataFrame) from cache.
        
        Priority: RAM → SQLite (if not expired)
        """
        # Check RAM cache
        if key in self.mem_cache:
            data, expiry = self.mem_cache[key]
            if datetime.now() < expiry:
                logger.debug(f"RAM cache hit: {key}")
                return data
            else:
                del self.mem_cache[key]
        
        # Check SQLite cache
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_parquet, payload_json, fetched_at, ttl_seconds FROM ohlcv_cache WHERE key = ?",
                (key,)
            ).fetchone()
        
        if row is None:
            return None
        
        payload_parquet, payload_json, fetched_at, db_ttl = row
        fetched_dt = datetime.fromisoformat(fetched_at)
        
        now = datetime.now()
        age_seconds = (now - fetched_dt).total_seconds()
        remaining_ttl = max(0, int(db_ttl - age_seconds))

        # Check expiry
        if remaining_ttl <= 0:
            self._delete_ohlcv(key)
            return None
        
        logger.debug(f"SQLite cache hit: {key}")
        
        # Reconstruct DataFrame from parquet/JSON
        try:
            if payload_parquet:
                import io
                df = pd.read_parquet(io.BytesIO(payload_parquet))
            elif payload_json:
                df = pd.read_json(StringIO(payload_json))
            else:
                return None
            
            # Preserve effective TTL from persistent layer when promoting to RAM.
            self.mem_cache[key] = (df, now + timedelta(seconds=remaining_ttl))
            return df
        except Exception as e:
            logger.error(f"Failed to deserialize OHLCV {key}: {e}")
            return None
    
    def set_ohlcv(self, key: str, df: pd.DataFrame, ttl_seconds: int = 3600):
        """Store OHLCV data with TTL."""
        # Store in RAM cache
        self.mem_cache[key] = (df, datetime.now() + timedelta(seconds=ttl_seconds))
        
        # Store in SQLite (parquet for efficiency)
        try:
            import io
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer)
            payload_parquet = parquet_buffer.getvalue()
            payload_json = None
        except Exception as e:
            logger.warning(f"Failed to parquet {key}, using JSON: {e}")
            payload_parquet = None
            payload_json = df.to_json()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ohlcv_cache 
                (key, payload_parquet, payload_json, fetched_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (key, payload_parquet, payload_json, datetime.now().isoformat(), ttl_seconds))
            conn.commit()
        
        logger.debug(f"Cached OHLCV: {key} (TTL: {ttl_seconds}s)")
    
    def get_meta(self, key: str, ttl_seconds: int = 3600) -> Optional[Dict[str, Any]]:
        """Retrieve ticker metadata from cache."""
        # Check RAM cache
        if key in self.mem_cache:
            data, expiry = self.mem_cache[key]
            if datetime.now() < expiry:
                logger.debug(f"RAM cache hit: {key}")
                return data
            else:
                del self.mem_cache[key]
        
        # Check SQLite cache
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at, ttl_seconds FROM ticker_meta_cache WHERE key = ?",
                (key,)
            ).fetchone()
        
        if row is None:
            return None
        
        payload_json, fetched_at, db_ttl = row
        fetched_dt = datetime.fromisoformat(fetched_at)
        
        now = datetime.now()
        age_seconds = (now - fetched_dt).total_seconds()
        remaining_ttl = max(0, int(db_ttl - age_seconds))

        # Check expiry
        if remaining_ttl <= 0:
            self._delete_meta(key)
            return None
        
        try:
            data = json.loads(payload_json)
            self.mem_cache[key] = (data, now + timedelta(seconds=remaining_ttl))
            return data
        except Exception as e:
            logger.error(f"Failed to deserialize meta {key}: {e}")
            return None
    
    def set_meta(self, key: str, data: Dict[str, Any], ttl_seconds: int = 3600):
        """Store ticker metadata with TTL."""
        # Store in RAM cache
        self.mem_cache[key] = (data, datetime.now() + timedelta(seconds=ttl_seconds))
        
        # Store in SQLite
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ticker_meta_cache 
                (key, payload_json, fetched_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
            """, (key, json.dumps(data), datetime.now().isoformat(), ttl_seconds))
            conn.commit()
        
        logger.debug(f"Cached meta: {key} (TTL: {ttl_seconds}s)")
    
    def get_etf_facts(self, key: str, ttl_seconds: int = 2592000) -> Optional[Dict[str, Any]]:  # 30 days default
        """Retrieve ETF facts from cache."""
        # Ensure database is initialized
        self._init_db()
        
        # Check RAM cache
        if key in self.mem_cache:
            data, expiry = self.mem_cache[key]
            if datetime.now() < expiry:
                logger.debug(f"RAM cache hit: {key}")
                return data
            else:
                del self.mem_cache[key]
        
        # Check SQLite cache
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at, ttl_seconds FROM etf_facts_cache WHERE key = ?",
                (key,)
            ).fetchone()
        
        if row is None:
            return None
        
        payload_json, fetched_at, db_ttl = row
        fetched_dt = datetime.fromisoformat(fetched_at)
        
        now = datetime.now()
        age_seconds = (now - fetched_dt).total_seconds()
        remaining_ttl = max(0, int(db_ttl - age_seconds))

        # Check expiry
        if remaining_ttl <= 0:
            self._delete_etf_facts(key)
            return None
        
        try:
            data = json.loads(payload_json)
            self.mem_cache[key] = (data, now + timedelta(seconds=remaining_ttl))
            return data
        except Exception as e:
            logger.error(f"Failed to deserialize ETF facts {key}: {e}")
            return None
    
    def set_etf_facts(self, key: str, data: Dict[str, Any], ttl_seconds: int = 2592000):  # 30 days
        """Store ETF facts with TTL."""
        # Store in RAM cache
        self.mem_cache[key] = (data, datetime.now() + timedelta(seconds=ttl_seconds))
        
        # Store in SQLite
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO etf_facts_cache 
                (key, payload_json, fetched_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
            """, (key, json.dumps(data), datetime.now().isoformat(), ttl_seconds))
            conn.commit()
        
        logger.debug(f"Cached ETF facts: {key} (TTL: {ttl_seconds}s)")
    
    def _delete_ohlcv(self, key: str):
        """Remove expired OHLCV from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM ohlcv_cache WHERE key = ?", (key,))
            conn.commit()
    
    def _delete_meta(self, key: str):
        """Remove expired meta from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM ticker_meta_cache WHERE key = ?", (key,))
            conn.commit()
    
    def _delete_etf_facts(self, key: str):
        """Remove expired ETF facts from cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM etf_facts_cache WHERE key = ?", (key,))
            conn.commit()
    
    def clear_all(self):
        """Clear all caches (use cautiously)."""
        self.mem_cache.clear()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM ohlcv_cache")
            conn.execute("DELETE FROM ticker_meta_cache")
            conn.execute("DELETE FROM etf_facts_cache")
            conn.commit()
        logger.info("All caches cleared")
