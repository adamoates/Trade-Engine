"""
Data types for market microstructure data.

This module defines types for advanced market data including:
- Options market data (Put-Call Ratio, Open Interest, Implied Volatility)
- Level 2 order book data (Depth of Market, bid/ask walls, liquidity)

These data types enable sophisticated signal confirmation and risk assessment
beyond basic price/volume analysis.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OptionType(str, Enum):
    """Option contract type."""
    CALL = "call"
    PUT = "put"


@dataclass
class OptionsSnapshot:
    """
    Snapshot of options market data for a symbol.

    Used for sentiment analysis and volatility forecasting.
    """
    symbol: str
    timestamp: datetime

    # Put-Call Ratio metrics
    put_volume: float  # Total put option volume
    call_volume: float  # Total call option volume
    put_call_ratio: float  # put_volume / call_volume

    # Open Interest metrics
    put_open_interest: float  # Total open put contracts
    call_open_interest: float  # Total open call contracts
    total_open_interest: float  # Total open contracts

    # Volatility metrics
    implied_volatility: Optional[float] = None  # Average IV across strikes
    iv_rank: Optional[float] = None  # IV percentile over lookback period (0-100)

    # Additional metrics
    max_pain: Optional[float] = None  # Price where option sellers lose least
    gamma_exposure: Optional[float] = None  # Market-wide gamma positioning

    def get_sentiment_signal(self) -> str:
        """
        Get sentiment interpretation from Put-Call Ratio.

        Returns:
            "BULLISH", "BEARISH", or "NEUTRAL"
        """
        # Crypto market typically has long bias, so adjust thresholds
        if self.put_call_ratio < 0.7:
            return "BULLISH"
        elif self.put_call_ratio > 1.2:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def is_contrarian_signal(self) -> Optional[str]:
        """
        Check for extreme sentiment that might signal reversal.

        Returns:
            "BUY" for extreme fear, "SELL" for extreme greed, None otherwise
        """
        if self.put_call_ratio > 1.5:  # Extreme fear
            return "BUY"
        elif self.put_call_ratio < 0.4:  # Extreme greed
            return "SELL"
        return None


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""
    price: float
    quantity: float  # Total quantity at this price
    order_count: int  # Number of orders at this price


@dataclass
class Level2Snapshot:
    """
    Level 2 order book snapshot (Depth of Market).

    Provides real-time view of liquidity and order flow dynamics.
    """
    symbol: str
    timestamp: datetime

    # Order book depth
    bids: List[OrderBookLevel]  # Sorted by price descending (best bid first)
    asks: List[OrderBookLevel]  # Sorted by price ascending (best ask first)

    def get_best_bid(self) -> Optional[float]:
        """Get best (highest) bid price."""
        return self.bids[0].price if self.bids else None

    def get_best_ask(self) -> Optional[float]:
        """Get best (lowest) ask price."""
        return self.asks[0].price if self.asks else None

    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid is not None and best_ask is not None:
            return best_ask - best_bid
        return None

    def get_spread_percentage(self) -> Optional[float]:
        """Get bid-ask spread as percentage of mid-price."""
        spread = self.get_spread()
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if spread is not None and best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
            return (spread / mid_price) * 100 if mid_price > 0 else None
        return None

    def get_total_bid_volume(self, depth: int = 10) -> float:
        """
        Get total volume on bid side.

        Args:
            depth: Number of levels to include (default: 10)
        """
        return sum(level.quantity for level in self.bids[:depth])

    def get_total_ask_volume(self, depth: int = 10) -> float:
        """
        Get total volume on ask side.

        Args:
            depth: Number of levels to include (default: 10)
        """
        return sum(level.quantity for level in self.asks[:depth])

    def get_order_book_imbalance(self, depth: int = 10) -> float:
        """
        Calculate order book imbalance.

        Positive values indicate buying pressure (more bids than asks).
        Negative values indicate selling pressure (more asks than bids).

        Args:
            depth: Number of levels to include

        Returns:
            Imbalance ratio: (bid_volume - ask_volume) / (bid_volume + ask_volume)
            Range: -1.0 (all asks) to +1.0 (all bids)
        """
        bid_vol = self.get_total_bid_volume(depth)
        ask_vol = self.get_total_ask_volume(depth)
        total_vol = bid_vol + ask_vol

        if total_vol > 0:
            return (bid_vol - ask_vol) / total_vol
        return 0.0

    def detect_walls(
        self,
        threshold_multiplier: float = 3.0,
        max_depth: int = 20
    ) -> Dict[str, List[OrderBookLevel]]:
        """
        Detect "walls" (abnormally large orders) in the order book.

        Args:
            threshold_multiplier: Wall is defined as order >= avg_size * multiplier
            max_depth: How many levels to scan

        Returns:
            Dict with 'buy_walls' and 'sell_walls' lists
        """
        # Calculate average order size for normalization
        all_levels = self.bids[:max_depth] + self.asks[:max_depth]
        if not all_levels:
            return {"buy_walls": [], "sell_walls": []}

        avg_size = sum(level.quantity for level in all_levels) / len(all_levels)
        threshold = avg_size * threshold_multiplier

        buy_walls = [level for level in self.bids[:max_depth] if level.quantity >= threshold]
        sell_walls = [level for level in self.asks[:max_depth] if level.quantity >= threshold]

        return {
            "buy_walls": buy_walls,
            "sell_walls": sell_walls
        }

    def get_liquidity_score(self, depth: int = 10) -> float:
        """
        Calculate liquidity score (0-100).

        Higher scores indicate better liquidity (tighter spreads, more depth).

        Args:
            depth: Number of levels to include
        """
        # Component 1: Spread (lower is better)
        spread_pct = self.get_spread_percentage()
        if spread_pct is None:
            return 0.0

        # Normalize spread: 0.01% = 100 points, 1% = 0 points (linear)
        spread_score = max(0, min(100, (1.0 - spread_pct) * 100))

        # Component 2: Depth (higher is better)
        total_volume = self.get_total_bid_volume(depth) + self.get_total_ask_volume(depth)
        # Normalize: assume 1000 units is "good" liquidity
        depth_score = min(100, (total_volume / 1000) * 100)

        # Component 3: Balance (closer to 0 imbalance is better)
        imbalance = abs(self.get_order_book_imbalance(depth))
        balance_score = (1 - imbalance) * 100

        # Weighted average: spread most important, then depth, then balance
        return (spread_score * 0.5 + depth_score * 0.3 + balance_score * 0.2)


@dataclass
class MarketMicrostructure:
    """
    Combined microstructure data for a symbol.

    Aggregates options data and Level 2 data for holistic market analysis.
    """
    symbol: str
    timestamp: datetime
    options_data: Optional[OptionsSnapshot] = None
    l2_data: Optional[Level2Snapshot] = None

    def get_confirmation_signal(self) -> Dict[str, any]:
        """
        Generate confirmation signal from microstructure data.

        Returns:
            Dict with confirmation status and supporting metrics
        """
        result = {
            "has_confirmation": False,
            "sentiment": "NEUTRAL",
            "liquidity_adequate": False,
            "signals": []
        }

        # Options-based confirmation
        if self.options_data:
            sentiment = self.options_data.get_sentiment_signal()
            contrarian = self.options_data.is_contrarian_signal()

            result["sentiment"] = sentiment
            result["signals"].append(f"PCR: {self.options_data.put_call_ratio:.2f} ({sentiment})")

            if contrarian:
                result["signals"].append(f"Contrarian signal: {contrarian}")

            # High OI growth confirms trend strength
            if self.options_data.total_open_interest > 0:
                result["signals"].append(f"OI: {self.options_data.total_open_interest:.0f}")

        # L2-based confirmation
        if self.l2_data:
            imbalance = self.l2_data.get_order_book_imbalance()
            liquidity = self.l2_data.get_liquidity_score()

            result["liquidity_adequate"] = liquidity > 50.0
            result["signals"].append(f"OB Imbalance: {imbalance:+.2f}")
            result["signals"].append(f"Liquidity: {liquidity:.1f}/100")

            # Detect walls
            walls = self.l2_data.detect_walls()
            if walls["buy_walls"]:
                result["signals"].append(f"Buy walls: {len(walls['buy_walls'])}")
            if walls["sell_walls"]:
                result["signals"].append(f"Sell walls: {len(walls['sell_walls'])}")

        # Overall confirmation requires alignment
        if self.options_data and self.l2_data:
            # Bullish confirmation: bullish sentiment + buying pressure + liquidity
            imbalance = self.l2_data.get_order_book_imbalance()
            liquidity = self.l2_data.get_liquidity_score()

            if (self.options_data.get_sentiment_signal() == "BULLISH" and
                imbalance > 0.2 and
                liquidity > 50):
                result["has_confirmation"] = True
                result["signals"].append("✓ Bullish confirmation")

            # Bearish confirmation: bearish sentiment + selling pressure + liquidity
            elif (self.options_data.get_sentiment_signal() == "BEARISH" and
                  imbalance < -0.2 and
                  liquidity > 50):
                result["has_confirmation"] = True
                result["signals"].append("✓ Bearish confirmation")

        return result
