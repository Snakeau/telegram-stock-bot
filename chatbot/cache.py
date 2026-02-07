"""Cache abstraction with TTL support."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CacheInterface(ABC):
    """Abstract cache interface."""
    
    @abstractmethod
    def get(self, key: str, ttl_seconds: int) -> Optional[Any]:
        """Get cached value if exists and not expired."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache."""
        pass
    
    @abstractmethod
    def cleanup(self, ttl_seconds: int) -> int:
        """Remove expired items, return count of removed items."""
        pass


class InMemoryCache(CacheInterface):
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = 600):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str, ttl_seconds: int = 600) -> Optional[Any]:
        """Get cached value if it exists and is not expired."""
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if time.time() - timestamp > ttl_seconds:
            del self._cache[key]
            logger.debug("Cache miss (expired): %s", key)
            return None
        
        logger.debug("Cache hit: %s", key)
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp."""
        self._cache[key] = (value, time.time())
        logger.debug("Cache set: %s", key)
    
    def clear(self) -> None:
        """Clear all cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared: %d items removed", count)
    
    def cleanup(self, ttl_seconds: int = 600) -> int:
        """Remove expired items, return count of removed items."""
        now = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if now - timestamp > ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info("Cache cleanup: %d items removed", len(expired_keys))
        
        return len(expired_keys)
    
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {"size": len(self._cache)}
