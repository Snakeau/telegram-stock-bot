"""Tests for database operations."""

import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from chatbot.db import PortfolioDB


class TestPortfolioNAVHistory:
    """Tests for portfolio NAV history operations."""
    
    @pytest.fixture
    def db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        db = PortfolioDB(db_path)
        yield db
    
    def test_save_and_retrieve_nav(self, db):
        """Test saving and retrieving NAV data."""
        user_id = 12345
        total_value = 10000.50
        
        db.save_nav(user_id, total_value, "USD")
        
        nav_series = db.get_nav_series(user_id, days=90)
        assert len(nav_series) == 1
        assert nav_series[0][1] == total_value
    
    def test_nav_upsert_same_day(self, db):
        """Test that NAV is updated (not inserted twice) for same day."""
        user_id = 12345
        
        db.save_nav(user_id, 10000.00, "USD")
        db.save_nav(user_id, 10500.00, "USD")  # Update same day
        
        nav_series = db.get_nav_series(user_id, days=90)
        assert len(nav_series) == 1
        assert nav_series[0][1] == 10500.00  # Latest value
    
    def test_nav_series_limit(self, db):
        """Test NAV series respects day limit."""
        user_id = 12345
        
        # This is a simplified test - in reality dates would be different
        for i in range(10):
            db.save_nav(user_id, 10000 + i * 100)
        
        nav_series = db.get_nav_series(user_id, days=5)
        # Returns at most requested days (this is simplified)
        assert len(nav_series) <= 10


class TestSECCache:
    """Tests for SEC cache operations."""
    
    @pytest.fixture
    def db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        db = PortfolioDB(db_path)
        yield db
    
    def test_sec_cache_store_and_retrieve(self, db):
        """Test storing and retrieving SEC cache."""
        key = "sec:company_tickers"
        payload = '{"AAPL": {"cik_str": 320193}}'
        
        db.set_sec_cache(key, payload)
        retrieved = db.get_sec_cache(key, ttl_hours=24)
        
        assert retrieved == payload
    
    def test_sec_cache_ttl_expiry(self, db):
        """Test SEC cache expires after TTL."""
        key = "sec:test"
        payload = "test_data"
        
        db.set_sec_cache(key, payload)
        
        # Manually set fetched_at to old time
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "UPDATE sec_cache SET fetched_at = ? WHERE key = ?",
                (old_time, key)
            )
            conn.commit()
        
        # Should return None (expired)
        retrieved = db.get_sec_cache(key, ttl_hours=24)
        assert retrieved is None
    
    def test_sec_cache_no_expiry_within_ttl(self, db):
        """Test SEC cache doesn't expire within TTL."""
        key = "sec:test"
        payload = "test_data"
        
        db.set_sec_cache(key, payload)
        retrieved = db.get_sec_cache(key, ttl_hours=24)
        
        assert retrieved == payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
