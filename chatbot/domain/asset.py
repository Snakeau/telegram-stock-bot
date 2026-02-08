"""
Asset Domain Model - Type-safe representation of financial assets.

Ensures that every ticker is explicitly resolved to an Asset with:
- Exchange (LSE, NASDAQ, NYSE, XETRA, EUREX)
- Currency (USD, GBP, EUR)
- Yahoo Finance symbol (for data fetching)

This prevents silent fallback to wrong exchanges (e.g., SGLN → Singapore instead of LSE).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Exchange(str, Enum):
    """Supported exchanges."""
    LSE = "LSE"          # London Stock Exchange
    NASDAQ = "NASDAQ"    # NASDAQ (US)
    NYSE = "NYSE"        # New York Stock Exchange (US)
    XETRA = "XETRA"      # Deutsche Börse (Germany)
    EUREX = "EUREX"      # European exchange


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"          # US Dollar
    GBP = "GBP"          # British Pound
    EUR = "EUR"          # Euro


class AssetType(str, Enum):
    """Asset type classification."""
    STOCK = "stock"      # Regular stock
    ETF = "etf"          # Exchange-traded fund


@dataclass(frozen=True)
class Asset:
    """
    Immutable Asset representation with strict validation.
    
    Ensures that an Asset cannot be mutated after creation, preventing
    accidental exchange/currency changes during processing.
    
    Attributes:
        symbol: Ticker symbol (e.g., "SGLN", "ADBE")
        exchange: Exchange enum (LSE, NASDAQ, NYSE, etc.)
        currency: Currency enum (USD, GBP, EUR)
        yahoo_symbol: Symbol for Yahoo Finance (e.g., "SGLN.L", "ADBE")
        asset_type: Asset type (stock or etf)
    """
    
    symbol: str
    exchange: Exchange
    currency: Currency
    yahoo_symbol: str
    asset_type: AssetType = AssetType.STOCK
    
    def __post_init__(self):
        """Validate asset after initialization."""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not self.yahoo_symbol or not self.yahoo_symbol.strip():
            raise ValueError("yahoo_symbol cannot be empty")
        
        # LSE symbols MUST have .L suffix in yahoo_symbol
        if self.exchange == Exchange.LSE and not self.yahoo_symbol.endswith('.L'):
            raise ValueError(f"LSE symbol must end with .L: {self.yahoo_symbol}")
    
    @property
    def display_name(self) -> str:
        """
        Human-readable display name.
        
        Returns:
            Format: "SYMBOL (EXCHANGE, CURRENCY)"
            Example: "SGLN (LSE, GBP)"
        """
        return f"{self.symbol} ({self.exchange.value}, {self.currency.value})"
    
    @classmethod
    def create_ucits_etf(
        cls,
        symbol: str,
        exchange: Exchange,
        currency: Currency,
        yahoo_symbol: str,
    ) -> "Asset":
        """
        Create a UCITS ETF asset (European exchange-traded fund).
        
        Args:
            symbol: Ticker symbol
            exchange: Exchange enum
            currency: Currency enum
            yahoo_symbol: Yahoo Finance symbol
            
        Returns:
            Asset with asset_type=ETF
            
        Example:
            sgln = Asset.create_ucits_etf("SGLN", Exchange.LSE, Currency.GBP, "SGLN.L")
        """
        return cls(
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            yahoo_symbol=yahoo_symbol,
            asset_type=AssetType.ETF,
        )
    
    @classmethod
    def create_stock(
        cls,
        symbol: str,
        exchange: Exchange,
        currency: Currency,
        yahoo_symbol: Optional[str] = None,
    ) -> "Asset":
        """
        Create a stock asset.
        
        If yahoo_symbol is not provided, defaults to symbol.
        
        Args:
            symbol: Ticker symbol
            exchange: Exchange enum
            currency: Currency enum
            yahoo_symbol: Yahoo Finance symbol (defaults to symbol)
            
        Returns:
            Asset with asset_type=STOCK
            
        Example:
            adbe = Asset.create_stock("ADBE", Exchange.NASDAQ, Currency.USD)
        """
        return cls(
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            yahoo_symbol=yahoo_symbol or symbol,
            asset_type=AssetType.STOCK,
        )
