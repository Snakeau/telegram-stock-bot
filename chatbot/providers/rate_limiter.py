"""Robust rate limiter for Finnhub API (token bucket + per-second safety cap)."""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for Finnhub API.
    
    Enforces:
    1. Per-minute limit (RPM): max requests per minute (free tier: 60)
    2. Per-second limit (RPS): immediate safety cap to avoid bursts (free tier: 5)
    
    Strategy:
    - Refill 1 token per (60/RPM) seconds
    - On each request: check if tokens available, wait if needed
    - Also check per-second cap: max RPS tokens per second
    - Track 429 errors and implement backoff
    
    Attributes:
        rpm: Requests per minute limit
        rps: Requests per second limit
        requests_last_minute: Counter for requests in current minute
        error_429_count: Count of consecutive 429 errors
        last_reset_ts: Timestamp of last minute reset
        last_refill_ts: Timestamp of last token refill
    """
    
    def __init__(self, rpm: int = 60, rps: int = 5):
        """
        Initialize rate limiter.
        
        Args:
            rpm: Requests per minute (default 60 for Finnhub free tier)
            rps: Requests per second (default 5 as safety cap)
        """
        if rpm <= 0 or rps <= 0:
            raise ValueError("rpm and rps must be positive")
        if rps > rpm // 60:
            logger.warning(
                f"RPS ({rps}) is high relative to RPM ({rpm}), "
                f"consider rps <= {rpm // 60}"
            )
        
        self.rpm = rpm
        self.rps = rps
        
        # Token bucket: tokens per minute
        self.tokens_per_minute = float(rpm)
        self.current_tokens = float(rpm)
        
        # Per-second bucket: tokens per second
        self.tokens_per_second = float(rps)
        self.current_tokens_per_second = float(rps)
        
        # Timing
        self.last_refill_ts = time.monotonic()
        self.last_refill_ts_per_second = time.monotonic()
        
        # Counters
        self.requests_last_minute = 0
        self.error_429_count = 0
        self.last_reset_ts = time.monotonic()
        
        # Lock for thread-safe access
        self.lock = asyncio.Lock()

    async def acquire(self, wait: bool = True) -> bool:
        """
        Acquire a token for a request.
        
        Args:
            wait: If True, wait until token available; if False, return immediately
                    
        Returns:
            True if token acquired, False if not available and wait=False
        """
        async with self.lock:
            self._refill_tokens()
            
            # Check if we have tokens available (both per-minute and per-second)
            if self.current_tokens < 1 or self.current_tokens_per_second < 1:
                if not wait:
                    return False
                
                # Calculate wait time
                wait_time = self._calculate_wait_time()
                logger.debug(f"Rate limit reached. Waiting {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                self._refill_tokens()
            
            # Consume tokens
            self.current_tokens -= 1
            self.current_tokens_per_second -= 1
            self.requests_last_minute += 1
            
            logger.debug(
                f"Token acquired. Remaining: {self.current_tokens:.2f}/min, "
                f"{self.current_tokens_per_second:.2f}/sec, "
                f"Requests in window: {self.requests_last_minute}"
            )
            
            return True

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        
        # Refill per-minute tokens
        elapsed_min = (now - self.last_refill_ts) / 60.0
        tokens_to_add_min = elapsed_min * self.tokens_per_minute
        self.current_tokens = min(
            self.tokens_per_minute,
            self.current_tokens + tokens_to_add_min
        )
        self.last_refill_ts = now
        
        # Refill per-second tokens
        elapsed_sec = now - self.last_refill_ts_per_second
        tokens_to_add_sec = elapsed_sec * self.tokens_per_second
        self.current_tokens_per_second = min(
            self.tokens_per_second,
            self.current_tokens_per_second + tokens_to_add_sec
        )
        self.last_refill_ts_per_second = now
        
        # Reset minute counter if 1+ minute has passed
        if now - self.last_reset_ts >= 60:
            logger.info(
                f"Minute window reset. Requests in previous window: {self.requests_last_minute}"
            )
            self.requests_last_minute = 0
            self.last_reset_ts = now

    def _calculate_wait_time(self) -> float:
        """Calculate how long to wait for tokens to refill."""
        now = time.monotonic()
        
        # Time until we refill 1 token per-minute
        min_wait = (60.0 / self.tokens_per_minute) * (1 - self.current_tokens)
        
        # Time until we refill 1 token per-second
        sec_wait = (1 - self.current_tokens_per_second) / self.tokens_per_second
        
        # Return maximum of the two (whichever needs longer)
        return max(min_wait, sec_wait, 0.01)  # Min 10ms to avoid tight loops

    def record_429(self) -> None:
        """Record a 429 (rate limit) error from API."""
        self.error_429_count += 1
        logger.warning(f"API returned 429. Error count: {self.error_429_count}")

    def reset_429_count(self) -> None:
        """Reset 429 error counter on successful request."""
        if self.error_429_count > 0:
            logger.info(f"Cleared 429 error count (was {self.error_429_count})")
        self.error_429_count = 0

    def get_backoff_time(self) -> float:
        """
        Get suggested backoff time based on 429 error count.
        
        Strategy:
        - 1st error: 1 second
        - 2nd error: 2 seconds
        - 3rd+ errors: 5 seconds (then fail)
        
        Returns:
            Seconds to wait before retry, or 0 if should give up
        """
        if self.error_429_count == 0:
            return 0
        if self.error_429_count == 1:
            return 1.0
        if self.error_429_count == 2:
            return 2.0
        # 3+ consecutive errors: give up
        return 0

    async def wait_backoff(self) -> bool:
        """
        Wait for backoff time based on 429 errors.
        
        Returns:
            True if should retry, False if should give up
        """
        backoff = self.get_backoff_time()
        if backoff == 0:
            return False
        
        logger.warning(f"Backing off for {backoff:.1f}s due to rate limit...")
        await asyncio.sleep(backoff)
        return True

    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return {
            "rpm": self.rpm,
            "rps": self.rps,
            "current_tokens_per_minute": round(self.current_tokens, 2),
            "current_tokens_per_second": round(self.current_tokens_per_second, 2),
            "requests_in_current_minute": self.requests_last_minute,
            "consecutive_429_errors": self.error_429_count,
        }


class RateLimitedAsyncCall:
    """Context manager for making rate-limited async calls."""
    
    def __init__(self, limiter: RateLimiter, operation_name: str = "request"):
        self.limiter = limiter
        self.operation_name = operation_name
        self.acquired = False
    
    async def __aenter__(self):
        """Acquire rate limit token on entry."""
        self.acquired = await self.limiter.acquire(wait=True)
        if not self.acquired:
            raise RuntimeError(f"{self.operation_name} could not acquire rate limit token")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Handle exit and error tracking."""
        if exc_type is None:
            # Success: reset 429 count
            self.limiter.reset_429_count()
        return False
