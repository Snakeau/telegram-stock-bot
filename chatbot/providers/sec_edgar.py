"""SEC EDGAR API provider for fundamental data."""

import asyncio
import json
import logging
from typing import Dict, List, Optional

import httpx

from ..cache import CacheInterface
from ..config import Config, SEC_COMPANY_TICKERS_URL
from ..db import PortfolioDB

logger = logging.getLogger(__name__)


class SECEdgarProvider:
    """
    SEC EDGAR API client for retrieving fundamental company data.
    
    Features:
    - Caches company_tickers.json for 24h (in-memory + database)
    - Proper User-Agent headers
    - Retry logic with exponential backoff
    - Handles rate limits gracefully
    """
    
    def __init__(
        self,
        config: Config,
        cache: CacheInterface,
        http_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        db: Optional[PortfolioDB] = None,
    ):
        self.config = config
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
        self.db = db
        self.user_agent = "InvestCheck/1.0 (contact@example.com)"
    
    async def get_cik_from_ticker(self, ticker: str) -> Optional[str]:
        """
        Get CIK (Central Index Key) from ticker symbol.
        
        Uses 24h cache for company_tickers.json and 30-day negative cache
        for missing CIKs to avoid repeated lookups.
        
        Args:
            ticker: Stock ticker symbol
        
        Returns:
            CIK string or None if not found
        """
        ticker_upper = ticker.upper()
        
        # Check negative cache first (30 days TTL)
        neg_cache_key = f"sec:no_cik:{ticker_upper}"
        if self.cache.get(neg_cache_key, ttl_seconds=2592000):  # 30 days
            logger.debug("Negative cache hit for %s (no CIK)", ticker_upper)
            return None
        
        cache_key = "sec:company_tickers"
        
        # Check in-memory cache first
        cached_data = self.cache.get(
            cache_key,
            ttl_seconds=self.config.sec_company_tickers_cache_ttl
        )
        
        if cached_data is None and self.db:
            # Check database cache (24h TTL)
            cached_json = self.db.get_sec_cache(cache_key, ttl_hours=24)
            if cached_json:
                try:
                    cached_data = json.loads(cached_json)
                    self.cache.set(cache_key, cached_data)
                    logger.info("Restored company_tickers from database cache")
                except json.JSONDecodeError as exc:
                    logger.warning("Failed to decode cached company_tickers: %s", exc)
        
        if cached_data is None:
            # Fetch from SEC
            try:
                async with self.semaphore:
                    response = await self.http_client.get(
                        SEC_COMPANY_TICKERS_URL,
                        headers={"User-Agent": self.user_agent},
                        timeout=self.config.http_timeout
                    )
                    response.raise_for_status()
                    cached_data = response.json()
                    self.cache.set(cache_key, cached_data)
                    
                    # Also store in database cache
                    if self.db:
                        self.db.set_sec_cache(cache_key, json.dumps(cached_data))
                    
                    logger.info("Fetched and cached company_tickers.json from SEC")
            except Exception as exc:
                logger.warning("Failed to fetch company_tickers.json: %s", exc)
                return None
        
        # Search for ticker in data
        for entry in cached_data.values():
            if entry.get('ticker', '').upper() == ticker_upper:
                cik = str(entry.get('cik_str'))
                logger.info("Found CIK %s for ticker %s", cik, ticker)
                return cik
        
        # Not found - set negative cache
        logger.debug("No CIK found for %s, setting negative cache", ticker_upper)
        self.cache.set(neg_cache_key, True)
        return None
        
        logger.warning("No CIK found for ticker %s in SEC database", ticker)
        return None
    
    async def get_company_facts(self, cik: str) -> Optional[Dict]:
        """
        Get company fundamental facts from SEC EDGAR.
        
        Args:
            cik: Company CIK
        
        Returns:
            Dictionary with company facts or None if not available
        """
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
        
        # Retry logic for SEC API
        for attempt in range(self.config.max_retries):
            try:
                async with self.semaphore:
                    response = await self.http_client.get(
                        url,
                        headers={"User-Agent": self.user_agent},
                        timeout=self.config.http_timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                    logger.info("Successfully fetched company facts for CIK %s", cik)
                    return data
            
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.warning("No company facts found for CIK %s (404)", cik)
                    return None
                elif attempt < self.config.max_retries - 1:
                    backoff = self.config.retry_backoff_factor * (2 ** attempt)
                    logger.warning(
                        "HTTP error on attempt %d for CIK %s: %s, retrying in %.1fs...",
                        attempt + 1, cik, exc, backoff
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.warning("HTTP error on final attempt for CIK %s: %s", cik, exc)
                    return None
            
            except Exception as exc:
                if attempt < self.config.max_retries - 1:
                    backoff = self.config.retry_backoff_factor * (2 ** attempt)
                    logger.warning(
                        "Error on attempt %d for CIK %s: %s, retrying in %.1fs...",
                        attempt + 1, cik, exc, backoff
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.warning("Failed to get company facts for CIK %s: %s", cik, exc)
                    return None
        
        return None
    
    def extract_fundamentals(self, facts: Dict) -> Dict[str, List[Dict]]:
        """
        Extract fundamental metrics from SEC EDGAR facts data.
        
        Args:
            facts: Raw company facts data from SEC API
        
        Returns:
            Dictionary with extracted metrics:
            - revenue: List of annual revenue data
            - operating_cash_flow: List of operating cash flow data
            - capex: List of capital expenditure data
            - cash: List of cash and equivalents data
            - debt: List of debt data
            - shares_outstanding: List of shares outstanding data
        
        Each metric is a list of dicts with: {year, value, filed}
        """
        fundamentals = {}
        
        if not facts or 'facts' not in facts:
            logger.warning("No facts data in response")
            return fundamentals
        
        us_gaap = facts['facts'].get('us-gaap', {})
        
        if not us_gaap:
            logger.warning("No us-gaap data found in facts")
            return fundamentals
        
        # Define tags to extract (with expanded list of alternatives)
        tags_map = {
            'revenue': [
                'Revenues',
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'SalesRevenueNet',
                'RevenueFromContractWithCustomerIncludingAssessedTax'
            ],
            'operating_cash_flow': [
                'NetCashProvidedByUsedInOperatingActivities',
                'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
            ],
            'capex': [
                'PaymentsToAcquirePropertyPlantAndEquipment',
                'PaymentsForCapitalImprovements',
                'PaymentsToAcquireProductiveAssets'
            ],
            'cash': [
                'CashAndCashEquivalentsAtCarryingValue',
                'Cash',
                'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
            ],
            'debt': [
                'LongTermDebt',
                'DebtCurrent',
                'LongTermDebtAndCapitalLeaseObligations'
            ],
            'shares_outstanding': [
                'CommonStockSharesOutstanding',
                'WeightedAverageNumberOfSharesOutstandingBasic',
                'CommonStockSharesIssued'
            ]
        }
        
        for metric, possible_tags in tags_map.items():
            for tag in possible_tags:
                if tag not in us_gaap:
                    continue
                
                # Extract data for 10-K (annual reports only)
                units = us_gaap[tag].get('units', {})
                
                # For revenue, capex, operating_cash_flow use USD
                # For shares use shares
                unit_key = 'shares' if metric == 'shares_outstanding' else 'USD'
                
                if unit_key not in units:
                    logger.debug("No %s units found for %s using tag %s", unit_key, metric, tag)
                    continue
                
                # Filter only 10-K forms
                annual_data = [
                    item for item in units[unit_key]
                    if item.get('form') in ['10-K', '10-K/A'] and item.get('fy')
                ]
                
                if not annual_data:
                    logger.debug("No 10-K data found for %s using tag %s", metric, tag)
                    continue
                
                # Sort by fiscal year (newest first)
                annual_data.sort(key=lambda x: (x.get('fy', 0), x.get('filed', '')), reverse=True)
                
                # Remove duplicates by fiscal year (keep most recent filing)
                seen_years = set()
                unique_data = []
                for item in annual_data:
                    fy = item.get('fy')
                    if fy and fy not in seen_years:
                        seen_years.add(fy)
                        unique_data.append({
                            'year': fy,
                            'value': item.get('val'),
                            'filed': item.get('filed')
                        })
                
                if unique_data:
                    fundamentals[metric] = unique_data
                    logger.info(
                        "Extracted %s: %d years of data using tag %s",
                        metric, len(unique_data), tag
                    )
                    break  # Found data for this metric, move to next
        
        return fundamentals
