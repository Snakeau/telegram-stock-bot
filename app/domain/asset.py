"""Asset domain model - explicit representation of financial instruments."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set


class AssetType(str, Enum):
    """Type of financial asset."""
    STOCK = "stock"      # US equity
    ETF = "etf"          # Exchange-Traded Fund


class Exchange(str, Enum):
    """Supported exchanges."""
    LSE = "LSE"          # London Stock Exchange (UCITS)
    NASDAQ = "NASDAQ"    # US stocks
    NYSE = "NYSE"        # US stocks
    XETRA = "XETRA"      # Germany (for future)
    EUREX = "EUREX"      # Europe (for future)


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"


@dataclass(frozen=True)
class Asset:
    """
    Explicit, resolved representation of a financial asset.
    
    Immutable by design - forces correct flow:
    1. User sends ticker
    2. Resolver creates Asset with explicit exchange/currency/yahoo_symbol
    3. Providers always receive Asset, never raw ticker
    4. UI displays resolve asset with full context
    
    Attributes:
        symbol: User-facing ticker (e.g., "VWRA", "AAPL")
        exchange: Primary exchange (LSE, NASDAQ, NYSE)
        currency: Base currency (USD, GBP, EUR)
        yahoo_symbol: Yahoo Finance symbol for OHLCV (e.g., "VWRA.L", "AAPL")
        asset_type: Type of asset (STOCK or ETF)
        region: Geographic region (e.g., "UK", "US", optional)
        underlying: For complex instruments, the underlying asset name (optional)
    """
    symbol: str
    exchange: Exchange
    currency: Currency
    yahoo_symbol: str
    asset_type: AssetType
    region: Optional[str] = None
    underlying: Optional[str] = None

    def __post_init__(self):
        """Validate asset after initialization."""
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if not self.yahoo_symbol:
            raise ValueError("yahoo_symbol cannot be empty")
        if "." not in self.yahoo_symbol and self.exchange != Exchange.NASDAQ and self.exchange != Exchange.NYSE:
            raise ValueError(
                f"yahoo_symbol '{self.yahoo_symbol}' must include exchange suffix for {self.exchange}"
            )

    @property
    def display_name(self) -> str:
        """Display name for UI (e.g., 'VWRA (LSE, USD)')."""
        return f"{self.symbol} ({self.exchange.value}, {self.currency.value})"

    @property
    def short_display(self) -> str:
        """Short display name for headers (e.g., 'VWRA')."""
        return self.symbol

    def __str__(self) -> str:
        """String representation."""
        return self.display_name

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"Asset(symbol={self.symbol!r}, exchange={self.exchange.value}, "
            f"currency={self.currency.value}, yahoo_symbol={self.yahoo_symbol!r}, "
            f"type={self.asset_type.value})"
        )

    @staticmethod
    def create_stock(
        symbol: str,
        exchange: Exchange = Exchange.NASDAQ,
        currency: Currency = Currency.USD,
    ) -> "Asset":
        """Factory for US stocks (fallback path)."""
        # For US stocks, yahoo_symbol is usually just the symbol (no suffix needed)
        yahoo_symbol = symbol
        return Asset(
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            yahoo_symbol=yahoo_symbol,
            asset_type=AssetType.STOCK,
            region="US",
        )

    @staticmethod
    def create_ucits_etf(
        symbol: str,
        lse_symbol: str,
        currency: Currency = Currency.USD,
    ) -> "Asset":
        """Factory for LSE UCITS ETFs."""
        return Asset(
            symbol=symbol,
            exchange=Exchange.LSE,
            currency=currency,
            yahoo_symbol=lse_symbol,
            asset_type=AssetType.ETF,
            region="UK",
        )


# Type alias for clarity in function signatures
AssetRef = Asset
