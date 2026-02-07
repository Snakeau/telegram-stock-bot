"""HTTP client with semaphore control and retry logic."""

import asyncio
import logging
import random
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Global HTTP semaphore (limits concurrent requests)
HTTP_SEMAPHORE = asyncio.Semaphore(10)

# Global HTTP client (for connection pooling)
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create global HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30)
    return _http_client


async def close_http_client() -> None:
    """Close global HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def http_get(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 30,
    retries: int = 3,
) -> httpx.Response:
    """
    GET request with semaphore + exponential backoff retry.
    
    Args:
        url: URL to fetch
        params: Query parameters
        headers: Custom headers
        timeout: Request timeout in seconds
        retries: Number of retries on failure
        
    Returns:
        httpx.Response object
        
    Raises:
        httpx.HTTPError on persistent failure
    """
    client = get_http_client()
    last_exception = None
    
    async with HTTP_SEMAPHORE:
        for attempt in range(retries):
            try:
                logger.debug(
                    "HTTP GET attempt %d/%d: %s",
                    attempt + 1,
                    retries,
                    url
                )
                
                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "1")
                    wait_time = float(retry_after)
                    if attempt < retries - 1:
                        logger.warning(
                            "Rate limited (429). Retrying after %.1f seconds...",
                            wait_time
                        )
                        await asyncio.sleep(wait_time)
                        continue
                
                # Handle server errors (5xx)
                if response.status_code >= 500:
                    if attempt < retries - 1:
                        backoff = 0.5 * (2 ** attempt) + random.uniform(0, 0.2)
                        logger.warning(
                            "Server error (%d). Retrying in %.2f seconds...",
                            response.status_code,
                            backoff
                        )
                        await asyncio.sleep(backoff)
                        continue
                
                # Success or client error
                response.raise_for_status()
                logger.debug("HTTP GET success: %s", url)
                return response
                
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                if attempt < retries - 1:
                    backoff = 0.5 * (2 ** attempt) + random.uniform(0, 0.2)
                    logger.warning(
                        "HTTP error on attempt %d: %s. Retrying in %.2f seconds...",
                        attempt + 1,
                        exc,
                        backoff
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error("HTTP GET failed after %d retries: %s", retries, exc)
                    
            except httpx.HTTPError as exc:
                logger.error("HTTP error: %s", exc)
                raise
    
    # All retries exhausted
    if last_exception:
        raise last_exception
    
    raise httpx.NetworkError("HTTP GET failed: max retries exceeded")


async def http_post(
    url: str,
    json: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 30,
    retries: int = 3,
) -> httpx.Response:
    """
    POST request with semaphore + exponential backoff retry.
    
    Similar to http_get but for POST requests.
    """
    client = get_http_client()
    last_exception = None
    
    async with HTTP_SEMAPHORE:
        for attempt in range(retries):
            try:
                logger.debug(
                    "HTTP POST attempt %d/%d: %s",
                    attempt + 1,
                    retries,
                    url
                )
                
                response = await client.post(
                    url,
                    json=json,
                    headers=headers,
                    timeout=timeout,
                )
                
                # Handle rate limit
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "1")
                    wait_time = float(retry_after)
                    if attempt < retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                
                # Handle server errors
                if response.status_code >= 500:
                    if attempt < retries - 1:
                        backoff = 0.5 * (2 ** attempt) + random.uniform(0, 0.2)
                        await asyncio.sleep(backoff)
                        continue
                
                response.raise_for_status()
                logger.debug("HTTP POST success: %s", url)
                return response
                
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exception = exc
                if attempt < retries - 1:
                    backoff = 0.5 * (2 ** attempt) + random.uniform(0, 0.2)
                    logger.warning(
                        "HTTP POST error on attempt %d: %s. Retrying...",
                        attempt + 1,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error("HTTP POST failed after %d retries: %s", retries, exc)
                    
            except httpx.HTTPError as exc:
                logger.error("HTTP POST error: %s", exc)
                raise
    
    if last_exception:
        raise last_exception
    
    raise httpx.NetworkError("HTTP POST failed: max retries exceeded")
