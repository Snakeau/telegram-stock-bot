"""
UCITS ETF Registry - Static mapping of European UCITS ETFs to LSE.

Ensures that ETFs like SGLN, VWRA, AGGU, SSLN always resolve to LSE
and never to Singapore, US, or other exchanges where they might trade.
"""

from typing import Dict, Optional
from .asset import Asset, Exchange, Currency, AssetType


class UCITSRegistry:
    """
    Static registry for UCITS ETFs trading on LSE.
    
    UCITS (Undertakings for Collective Investment in Transferable Securities)
    are regulated investment funds primarily listed on LSE. This registry
    ensures they always resolve to LSE, never to fallback exchanges.
    """
    
    # Static registry of UCITS ETFs - maps ticker to Asset
    _REGISTRY: Dict[str, Asset] = {
        "VWRA": Asset.create_ucits_etf("VWRA", Exchange.LSE, Currency.USD, "VWRA.L"),
        "SGLN": Asset.create_ucits_etf("SGLN", Exchange.LSE, Currency.GBP, "SGLN.L"),
        "AGGU": Asset.create_ucits_etf("AGGU", Exchange.LSE, Currency.GBP, "AGGU.L"),
        "SSLN": Asset.create_ucits_etf("SSLN", Exchange.LSE, Currency.GBP, "SSLN.L"),
    }
    
    @staticmethod
    def resolve(ticker: str) -> Optional[Asset]:
        """
        Resolve a ticker to a registered UCITS Asset.
        
        Case-insensitive lookup.
        
        Args:
            ticker: Ticker symbol (e.g., "SGLN", "vwra")
            
        Returns:
            Asset if registered, None otherwise
            
        Example:
            sgln = UCITSRegistry.resolve("SGLN")
            # Returns Asset(symbol="SGLN", exchange=LSE, currency=GBP, yahoo_symbol="SGLN.L")
        """
        normalized = ticker.upper().strip()
        return UCITSRegistry._REGISTRY.get(normalized)
    
    @staticmethod
    def is_registered(ticker: str) -> bool:
        """
        Check if a ticker is a registered UCITS ETF.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            True if registered
        """
        return UCITSRegistry.resolve(ticker) is not None
    
    @staticmethod
    def register(asset: Asset) -> None:
        """
        Register a new UCITS ETF.
        
        Allows dynamic registration if needed in future.
        
        Args:
            asset: Asset to register (must be LSE type etf)
            
        Raises:
            ValueError: If not LSE asset or not ETF type
        """
        if asset.exchange != Exchange.LSE:
            raise ValueError(f"UCITS registry only accepts LSE assets, got {asset.exchange}")
        if asset.asset_type != AssetType.ETF:
            raise ValueError(f"UCITS registry only accepts ETF assets, got {asset.asset_type}")
        
        UCITSRegistry._REGISTRY[asset.symbol.upper()] = asset
    
    @staticmethod
    def get_all() -> Dict[str, Asset]:
        """
        Get all registered UCITS ETFs.
        
        Returns:
            Dict mapping ticker → Asset
        """
        return dict(UCITSRegistry._REGISTRY)
    
    @staticmethod
    def clear() -> None:
        """
        Clear all registrations (for testing only).
        
        Resets to default UCITS ETFs after clearing.
        """
        UCITSRegistry._REGISTRY.clear()
        # Restore defaults
        UCITSRegistry._REGISTRY.update({
            "VWRA": Asset.create_ucits_etf("VWRA", Exchange.LSE, Currency.USD, "VWRA.L"),
            "SGLN": Asset.create_ucits_etf("SGLN", Exchange.LSE, Currency.GBP, "SGLN.L"),
            "AGGU": Asset.create_ucits_etf("AGGU", Exchange.LSE, Currency.GBP, "AGGU.L"),
            "SSLN": Asset.create_ucits_etf("SSLN", Exchange.LSE, Currency.GBP, "SSLN.L"),
        })
