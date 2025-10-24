"""
Asset Class Adapter for Strategy Parameter Tuning.

This module adapts trading strategy parameters based on asset class characteristics.
Different asset classes (crypto, stocks, forex) have unique market dynamics that
require different approaches:

Cryptocurrency Markets:
- 24/7 trading (no market close arbitrage)
- Extreme volatility (wider stops, smaller positions)
- Sentiment-driven (higher weight on options/social data)
- Lower liquidity (stricter liquidity requirements)
- Scarcity dynamics (supply metrics matter)

Stock Markets:
- Fixed hours (overnight gap risk)
- Lower volatility (tighter stops, larger positions)
- Fundamentals-driven (earnings, guidance)
- Higher liquidity (easier execution)
- Dividend income (time-based strategies)

This adapter automatically tunes alpha model parameters, risk limits, and
confirmation thresholds based on the asset class being traded.
"""

from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass


class AssetClass(str, Enum):
    """Supported asset classes."""
    CRYPTO = "crypto"
    STOCK = "stock"
    FOREX = "forex"
    COMMODITY = "commodity"


@dataclass
class MarketCharacteristics:
    """
    Characteristics that define an asset class's market dynamics.

    These metrics inform how strategies should be adapted.
    """
    # Trading characteristics
    is_24_7: bool  # Does market trade 24/7?
    typical_daily_volatility: float  # Typical daily price change (%)
    average_spread_bps: float  # Average bid-ask spread in basis points

    # Liquidity characteristics
    min_liquidity_score: float  # Minimum acceptable liquidity (0-100)
    slippage_tolerance: float  # Expected slippage (%)

    # Market structure
    has_circuit_breakers: bool  # Does exchange halt trading on big moves?
    has_overnight_risk: bool  # Is there gap risk when market closed?
    has_options_market: bool  # Are options available?

    # Price drivers
    sentiment_weight: float  # How much sentiment drives price (0-1)
    fundamental_weight: float  # How much fundamentals drive price (0-1)
    technical_weight: float  # How much technicals drive price (0-1)


# Predefined characteristics for major asset classes
ASSET_CLASS_CHARACTERISTICS: Dict[AssetClass, MarketCharacteristics] = {
    AssetClass.CRYPTO: MarketCharacteristics(
        is_24_7=True,
        typical_daily_volatility=5.0,  # 5% daily moves common
        average_spread_bps=10.0,  # 0.1% spread
        min_liquidity_score=60.0,  # Higher threshold due to lower liquidity
        slippage_tolerance=0.5,  # 0.5% expected slippage
        has_circuit_breakers=False,
        has_overnight_risk=False,  # Always trading
        has_options_market=True,  # Major coins have options
        sentiment_weight=0.5,  # Very sentiment-driven
        fundamental_weight=0.2,  # Less fundamental analysis
        technical_weight=0.3  # Technical patterns matter
    ),

    AssetClass.STOCK: MarketCharacteristics(
        is_24_7=False,
        typical_daily_volatility=1.5,  # 1.5% daily moves
        average_spread_bps=2.0,  # 0.02% spread for liquid stocks
        min_liquidity_score=40.0,  # Lower threshold, stocks more liquid
        slippage_tolerance=0.1,  # 0.1% expected slippage
        has_circuit_breakers=True,
        has_overnight_risk=True,  # Gap risk
        has_options_market=True,
        sentiment_weight=0.25,  # Some sentiment impact
        fundamental_weight=0.5,  # Fundamentals very important
        technical_weight=0.25  # Technicals matter
    ),

    AssetClass.FOREX: MarketCharacteristics(
        is_24_7=True,
        typical_daily_volatility=0.7,  # 0.7% daily moves
        average_spread_bps=1.0,  # 0.01% spread (very tight)
        min_liquidity_score=30.0,  # Very liquid
        slippage_tolerance=0.05,  # Minimal slippage
        has_circuit_breakers=False,
        has_overnight_risk=False,
        has_options_market=True,
        sentiment_weight=0.3,
        fundamental_weight=0.4,  # Macro fundamentals
        technical_weight=0.3
    ),
}


class AssetClassAdapter:
    """
    Adapts strategy parameters based on asset class characteristics.

    This class implements the "market chameleon" concept from the research:
    strategies must adapt to different market conditions and asset classes.
    """

    def __init__(self, asset_class: AssetClass):
        """
        Initialize adapter for specific asset class.

        Args:
            asset_class: The asset class to adapt for
        """
        self.asset_class = asset_class
        self.characteristics = ASSET_CLASS_CHARACTERISTICS[asset_class]

    def adapt_alpha_parameters(
        self,
        base_params: Dict[str, Any],
        alpha_type: str
    ) -> Dict[str, Any]:
        """
        Adapt alpha model parameters for asset class.

        Args:
            base_params: Base/default parameters
            alpha_type: Type of alpha model (e.g., "MACD", "RSI", "BB")

        Returns:
            Adapted parameters dictionary
        """
        adapted = base_params.copy()

        # Adjust for volatility
        volatility_multiplier = (
            self.characteristics.typical_daily_volatility / 1.5  # Normalize to stocks
        )

        if alpha_type == "MACD":
            # Crypto: Use shorter periods due to faster moves
            # Stocks: Use standard periods
            if self.asset_class == AssetClass.CRYPTO:
                adapted["fast_period"] = max(6, int(base_params.get("fast_period", 12) * 0.7))
                adapted["slow_period"] = max(12, int(base_params.get("slow_period", 26) * 0.7))

        elif alpha_type == "RSI":
            # Crypto: Adjust overbought/oversold thresholds
            # Higher volatility = more extreme thresholds
            if self.asset_class == AssetClass.CRYPTO:
                adapted["overbought_threshold"] = min(85, base_params.get("overbought_threshold", 70) + 10)
                adapted["oversold_threshold"] = max(15, base_params.get("oversold_threshold", 30) - 10)

        elif alpha_type == "BOLLINGER":
            # Adjust standard deviation multiplier for volatility
            base_std_dev = base_params.get("num_std_dev", 2.0)
            adapted["num_std_dev"] = base_std_dev * (1.0 + (volatility_multiplier - 1.0) * 0.3)

        # Adjust confidence based on market characteristics
        base_confidence = base_params.get("confidence", 0.7)

        # Lower confidence in sentiment-driven markets (harder to predict)
        sentiment_penalty = 1.0 - (self.characteristics.sentiment_weight * 0.15)
        adapted["confidence"] = base_confidence * sentiment_penalty

        return adapted

    def adapt_confirmation_parameters(
        self,
        base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adapt signal confirmation parameters for asset class.

        Args:
            base_params: Base confirmation filter parameters

        Returns:
            Adapted parameters dictionary
        """
        adapted = base_params.copy()

        # Liquidity requirements
        adapted["min_liquidity_score"] = self.characteristics.min_liquidity_score

        # Options confirmation
        if self.characteristics.has_options_market:
            # Crypto: Options data more valuable (sentiment-driven)
            # Stocks: Less critical (fundamentals matter more)
            if self.asset_class == AssetClass.CRYPTO:
                adapted["require_options_confirmation"] = False  # Optional but valuable
                adapted["confidence_boost_factor"] = 1.3  # Higher boost
            else:
                adapted["require_options_confirmation"] = False
                adapted["confidence_boost_factor"] = 1.15  # Lower boost
        else:
            adapted["require_options_confirmation"] = False

        # Order book imbalance thresholds
        # Higher volatility = need stronger imbalance signal
        volatility_factor = self.characteristics.typical_daily_volatility / 1.5
        base_threshold = base_params.get("ob_imbalance_threshold", 0.2)
        adapted["ob_imbalance_threshold"] = base_threshold * volatility_factor

        return adapted

    def adapt_risk_parameters(
        self,
        base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adapt risk management parameters for asset class.

        Args:
            base_params: Base risk parameters

        Returns:
            Adapted parameters dictionary
        """
        adapted = base_params.copy()

        # Position sizing based on volatility
        base_max_position = base_params.get("max_position_size", 0.1)  # 10% of portfolio

        # Reduce position size in volatile markets
        volatility_factor = 1.5 / self.characteristics.typical_daily_volatility
        adapted["max_position_size"] = base_max_position * min(1.0, volatility_factor)

        # Stop loss based on typical volatility
        # Need wider stops in crypto to avoid being stopped out by noise
        base_stop_loss = base_params.get("stop_loss_pct", 2.0)  # 2%
        adapted["stop_loss_pct"] = base_stop_loss * (
            self.characteristics.typical_daily_volatility / 1.5
        )

        # Overnight risk adjustment
        if self.characteristics.has_overnight_risk:
            # Stocks: Reduce position before close to manage gap risk
            adapted["reduce_before_close"] = True
            adapted["close_reduction_factor"] = 0.5  # 50% reduction
        else:
            adapted["reduce_before_close"] = False

        # Slippage budget
        adapted["max_slippage_pct"] = self.characteristics.slippage_tolerance

        return adapted

    def get_trading_hours_config(self) -> Dict[str, Any]:
        """
        Get trading hours configuration for asset class.

        Returns:
            Trading hours configuration
        """
        if self.characteristics.is_24_7:
            return {
                "trading_enabled": True,
                "hours": "24/7",
                "timezone": "UTC",
                "market_open": None,
                "market_close": None,
                "allow_overnight": True
            }
        else:
            # Stock market hours (US)
            return {
                "trading_enabled": True,
                "hours": "09:30-16:00",
                "timezone": "America/New_York",
                "market_open": "09:30",
                "market_close": "16:00",
                "allow_overnight": False,  # Close positions before market close
                "pre_market": "04:00-09:30",  # Optional pre-market trading
                "after_hours": "16:00-20:00"  # Optional after-hours trading
            }

    def should_trade_now(self, current_time: str) -> bool:
        """
        Determine if trading should be active at current time.

        Args:
            current_time: Current time (ISO format or HH:MM)

        Returns:
            True if trading should be active
        """
        if self.characteristics.is_24_7:
            return True

        # For stock markets, check if within trading hours
        # This would need proper datetime parsing in production
        # Simplified for now
        return True  # Placeholder

    def get_recommended_indicators(self) -> Dict[str, float]:
        """
        Get recommended indicator weights for asset class.

        Returns:
            Dict mapping indicator category to weight
        """
        return {
            "sentiment": self.characteristics.sentiment_weight,
            "fundamental": self.characteristics.fundamental_weight,
            "technical": self.characteristics.technical_weight
        }

    def get_market_specific_features(self) -> Dict[str, bool]:
        """
        Get market-specific features to enable/disable.

        Returns:
            Feature flags for this asset class
        """
        return {
            "use_options_data": self.characteristics.has_options_market,
            "use_circuit_breaker_detection": self.characteristics.has_circuit_breakers,
            "manage_overnight_risk": self.characteristics.has_overnight_risk,
            "continuous_trading": self.characteristics.is_24_7,
            "scarcity_metrics": self.asset_class == AssetClass.CRYPTO,  # Supply analysis
            "dividend_capture": self.asset_class == AssetClass.STOCK,
            "macro_economic_data": self.asset_class in [AssetClass.STOCK, AssetClass.FOREX]
        }
