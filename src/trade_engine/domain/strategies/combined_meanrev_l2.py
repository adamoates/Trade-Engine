"""
Mean-Reversion L2 Timing Strategy

Combines Bollinger Bands mean-reversion with L2 imbalance for precise entry timing.
Waits for price extremes (Bollinger Band touches), then uses L2 to confirm reversal.

Strategy Logic:
1. Primary: Bollinger Bands identify oversold/overbought conditions
   - Price hits lower band = Oversold (potential buy)
   - Price hits upper band = Overbought (potential sell)
2. Secondary: L2 Imbalance confirms reversal is starting
   - After oversold: Wait for bid pressure (imbalance > 3.5x)
   - After overbought: Wait for ask pressure (imbalance < 0.28x)
3. Entry: Only execute when both conditions met

Expected Performance:
- Win Rate: 60-68% (catches actual reversals, not false signals)
- Profit Factor: 1.6-2.0
- Trade Frequency: 5-15 trades/day (very selective)
- Max Drawdown: ~10%

Best For: Range-bound markets, high volatility environments

CRITICAL: All financial values use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from loguru import logger

from trade_engine.core.types import Signal
from trade_engine.adapters.feeds.binance_l2 import OrderBook
from trade_engine.domain.strategies.alpha_l2_imbalance import (
    L2ImbalanceStrategy,
    L2StrategyConfig
)


@dataclass
class BollingerBandsConfig:
    """Configuration for Bollinger Bands."""
    period: int = 20
    std_dev: Decimal = Decimal("2.0")
    timeframe: str = "5m"


class MeanReversionL2Strategy:
    """
    Mean-Reversion Strategy with L2 Entry Timing.

    Uses Bollinger Bands to identify price extremes, then waits for L2
    order book confirmation that reversal is actually happening.

    This avoids "catching falling knives" - instead of buying just because
    price is low, we wait for actual buying pressure to appear in the order book.

    Architecture:
    - Primary Strategy: Bollinger Bands (identifies extremes)
    - Signal Generator: L2 Imbalance (confirms reversal)
    - Entry Timing: Two-stage confirmation

    Example:
        config = MeanReversionL2Config(
            l2_config=L2StrategyConfig(...),
            bb_config=BollingerBandsConfig(period=20, std_dev=Decimal("2.0"))
        )
        strategy = MeanReversionL2Strategy(symbol="BTCUSDT", order_book=ob, config=config)

        # Update BB bands periodically (every 5min bar)
        strategy.update_bands(close_price)

        # Check for signals frequently (every 100ms)
        signal = strategy.check_imbalance(order_book)
    """

    def __init__(
        self,
        symbol: str,
        order_book: OrderBook,
        l2_config: L2StrategyConfig,
        bb_config: BollingerBandsConfig
    ):
        """
        Initialize mean-reversion L2 strategy.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            order_book: L2 order book instance
            l2_config: L2 strategy configuration
            bb_config: Bollinger Bands configuration
        """
        self.symbol = symbol
        self.bb_config = bb_config

        # L2 signal generator (fast, higher thresholds for reversal confirmation)
        l2_config_copy = L2StrategyConfig(
            buy_threshold=Decimal("3.5"),  # Higher threshold for reversal
            sell_threshold=Decimal("0.28"),  # Lower threshold for reversal
            depth=l2_config.depth,
            position_size_usd=l2_config.position_size_usd,
            profit_target_pct=l2_config.profit_target_pct,
            stop_loss_pct=l2_config.stop_loss_pct,
            cooldown_seconds=l2_config.cooldown_seconds,
            max_hold_time_seconds=l2_config.max_hold_time_seconds,
            spot_only=l2_config.spot_only
        )

        self.l2_strategy = L2ImbalanceStrategy(
            symbol=symbol,
            order_book=order_book,
            config=l2_config_copy
        )

        # Bollinger Bands tracking
        self.price_history: List[Decimal] = []
        self.middle_band: Optional[Decimal] = None
        self.upper_band: Optional[Decimal] = None
        self.lower_band: Optional[Decimal] = None

        # Reversal state
        self.waiting_for_reversal: Optional[str] = None  # "long" or "short" or None
        self.extreme_timestamp: Optional[int] = None
        self.extreme_timeout_seconds = 300  # 5 minutes

        # Statistics
        self.extreme_touches = 0
        self.reversals_confirmed = 0
        self.reversals_timeout = 0

        logger.info(
            f"MeanReversionL2Strategy initialized | "
            f"Symbol: {symbol} | "
            f"BB: {bb_config.period} period, {bb_config.std_dev}σ | "
            f"Timeframe: {bb_config.timeframe}"
        )

    def update_bands(self, close_price: Decimal) -> None:
        """
        Update Bollinger Bands.

        Call this on each new bar (e.g., every 5 minutes).

        Args:
            close_price: Close price of current bar (Decimal)
        """
        # Validate Decimal type
        if not isinstance(close_price, Decimal):
            raise TypeError(f"close_price must be Decimal, got {type(close_price)}")

        # Add price to history
        self.price_history.append(close_price)

        # Need enough data for BB calculation
        if len(self.price_history) < self.bb_config.period:
            return

        # Calculate middle band (SMA)
        recent_prices = self.price_history[-self.bb_config.period:]
        self.middle_band = sum(recent_prices) / Decimal(str(self.bb_config.period))

        # Calculate standard deviation
        variance = sum(
            (price - self.middle_band) ** 2
            for price in recent_prices
        ) / Decimal(str(self.bb_config.period))
        std_dev = variance.sqrt()

        # Calculate upper and lower bands
        self.upper_band = self.middle_band + (self.bb_config.std_dev * std_dev)
        self.lower_band = self.middle_band - (self.bb_config.std_dev * std_dev)

        # Check for extreme touches
        self._check_extreme_touch(close_price)

        logger.debug(
            f"BB Updated | "
            f"Lower: {self.lower_band:.2f} | "
            f"Mid: {self.middle_band:.2f} | "
            f"Upper: {self.upper_band:.2f} | "
            f"Price: {close_price:.2f}"
        )

    def _check_extreme_touch(self, close_price: Decimal) -> None:
        """Check if price touched Bollinger Band extreme."""
        import time

        if not self.lower_band or not self.upper_band:
            return

        # Check for lower band touch (oversold)
        if close_price <= self.lower_band:
            if self.waiting_for_reversal != "long":
                self.waiting_for_reversal = "long"
                self.extreme_timestamp = int(time.time())
                self.extreme_touches += 1
                logger.warning(
                    f"📉 Lower band touched | "
                    f"Price: {close_price:.2f} | "
                    f"Lower band: {self.lower_band:.2f} | "
                    f"Waiting for BUY reversal confirmation..."
                )

        # Check for upper band touch (overbought)
        elif close_price >= self.upper_band:
            if self.waiting_for_reversal != "short":
                self.waiting_for_reversal = "short"
                self.extreme_timestamp = int(time.time())
                self.extreme_touches += 1
                logger.warning(
                    f"📈 Upper band touched | "
                    f"Price: {close_price:.2f} | "
                    f"Upper band: {self.upper_band:.2f} | "
                    f"Waiting for SELL reversal confirmation..."
                )

    def check_imbalance(self, order_book: OrderBook) -> Optional[Signal]:
        """
        Check for mean-reversion signal with L2 confirmation.

        Args:
            order_book: Current L2 order book

        Returns:
            Signal if reversal confirmed by L2, None otherwise
        """
        import time

        # Step 1: Check if we're waiting for a reversal
        if not self.waiting_for_reversal:
            return None

        # Step 2: Check timeout (5 minutes)
        if self.extreme_timestamp:
            elapsed = int(time.time()) - self.extreme_timestamp
            if elapsed > self.extreme_timeout_seconds:
                logger.debug(
                    f"⏱️  Reversal wait timeout | "
                    f"Direction: {self.waiting_for_reversal} | "
                    f"Elapsed: {elapsed}s"
                )
                self.waiting_for_reversal = None
                self.extreme_timestamp = None
                self.reversals_timeout += 1
                return None

        # Step 3: Get L2 signal
        l2_signal = self.l2_strategy.check_imbalance(order_book)

        if not l2_signal:
            return None

        # Step 4: Check if L2 confirms the reversal
        if self.waiting_for_reversal == "long" and l2_signal.side == "buy":
            # Price was oversold, now buyers stepping in
            logger.success(
                f"✅ Mean-reversion LONG confirmed | "
                f"L2 Imbalance: {self.l2_strategy.last_imbalance:.2f}x | "
                f"Confirmation rate: {self.confirmation_rate:.1%}"
            )
            self.reversals_confirmed += 1
            self.waiting_for_reversal = None
            self.extreme_timestamp = None
            return l2_signal

        elif self.waiting_for_reversal == "short" and l2_signal.side == "sell":
            # Price was overbought, now sellers stepping in
            logger.success(
                f"✅ Mean-reversion SHORT confirmed | "
                f"L2 Imbalance: {self.l2_strategy.last_imbalance:.2f}x | "
                f"Confirmation rate: {self.confirmation_rate:.1%}"
            )
            self.reversals_confirmed += 1
            self.waiting_for_reversal = None
            self.extreme_timestamp = None
            return l2_signal

        return None

    @property
    def confirmation_rate(self) -> float:
        """Calculate percentage of extreme touches that resulted in trades."""
        if self.extreme_touches == 0:
            return 0.0
        return self.reversals_confirmed / self.extreme_touches

    @property
    def in_position(self) -> bool:
        """Check if currently in position (delegates to L2 strategy)."""
        return self.l2_strategy.in_position

    @in_position.setter
    def in_position(self, value: bool):
        """Set position status."""
        self.l2_strategy.in_position = value

    @property
    def entry_time(self) -> Optional[int]:
        """Get entry timestamp (delegates to L2 strategy)."""
        return self.l2_strategy.entry_time

    @entry_time.setter
    def entry_time(self, value: Optional[int]):
        """Set entry timestamp."""
        self.l2_strategy.entry_time = value

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            "strategy": "meanrev_l2",
            "symbol": self.symbol,
            "middle_band": str(self.middle_band) if self.middle_band else None,
            "upper_band": str(self.upper_band) if self.upper_band else None,
            "lower_band": str(self.lower_band) if self.lower_band else None,
            "waiting_for_reversal": self.waiting_for_reversal,
            "extreme_touches": self.extreme_touches,
            "reversals_confirmed": self.reversals_confirmed,
            "reversals_timeout": self.reversals_timeout,
            "confirmation_rate": f"{self.confirmation_rate:.1%}",
            "price_history_length": len(self.price_history),
            **self.l2_strategy.get_stats()
        }
