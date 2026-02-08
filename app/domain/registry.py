"""UCITS ETF registry - static mapping of known exchange-traded funds on LSE."""

from typing import Dict, Optional
from .asset import Asset, AssetType, Currency, Exchange


class UCITSRegistry:
    """
    Static registry of UCITS ETFs available on LSE.
    
    MUST be the FIRST resolution step when analyzing ETFs.
    Rules:
    - Only LSE-listed UCITS ETFs
    - Always use .L suffix for Yahoo Finance
    - Explicit currency per ETF (not inferred)
    - Region explicitly set to "UK"
    
    Future: can be extended to XETRA, EUREX, etc.
    """
    
    # Static mapping: ticker → Asset
    _REGISTRY: Dict[str, Asset] = {
        # Vanguard FTSE All-World UCITS (accumulating)
        "VWRA": Asset.create_ucits_etf(
            symbol="VWRA",
            lse_symbol="VWRA.L",
            currency=Currency.USD,
        ),
        
        # iShares Physical Gold - LSE (accumulating)
        "SGLN": Asset.create_ucits_etf(
            symbol="SGLN",
            lse_symbol="SGLN.L",
            currency=Currency.GBP,
        ),
        
        # iShares Core Global Aggregate Bond - LSE (accumulating)
        "AGGU": Asset.create_ucits_etf(
            symbol="AGGU",
            lse_symbol="AGGU.L",
            currency=Currency.GBP,
        ),
        
        # iShares Physical Silver - LSE (accumulating)
        "SSLN": Asset.create_ucits_etf(
            symbol="SSLN",
            lse_symbol="SSLN.L",
            currency=Currency.GBP,
        ),
    }

    @classmethod
    def resolve(cls, ticker: str) -> Optional[Asset]:
        """
        Resolve ticker to registered UCITS ETF.
        
        Returns:
            Asset if ticker found in registry, None otherwise
        """
        normalized_ticker = ticker.upper().strip()
        return cls._REGISTRY.get(normalized_ticker)

    @classmethod
    def is_registered(cls, ticker: str) -> bool:
        """Check if ticker is in UCITS registry."""
        return cls.resolve(ticker) is not None

    @classmethod
    def registered_tickers(cls) -> list[str]:
        """Return list of all registered tickers."""
        return list(cls._REGISTRY.keys())

    @classmethod
    def register(cls, asset: Asset) -> None:
        """
        Register a new UCITS ETF (for testing or dynamic registration).
        
        Args:
            asset: Asset to register (must be UCITS ETF)
        """
        if asset.asset_type != AssetType.ETF:
            raise ValueError(f"Can only register ETFs, got {asset.asset_type}")
        if asset.exchange != Exchange.LSE:
            raise ValueError(f"Can only register LSE assets, got {asset.exchange}")
        cls._REGISTRY[asset.symbol] = asset

    @classmethod
    def get_all(cls) -> Dict[str, Asset]:
        """Return copy of entire registry (read-only view)."""
        return dict(cls._REGISTRY)
