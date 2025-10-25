"""
L2 Order Book Imbalance Strategy

Core trading strategy based on Level 2 order book bid/ask volume imbalance.
Generates signals when imbalance exceeds thresholds, indicating strong
supply/demand pressure.

Strategy Logic:
- BUY when imbalance > 3.0 (3x more bid volume than ask)
- SELL when imbalance < 0.33 (3x more ask volume than bid)
- Hold for 5-60 seconds
- Target: 0.2% profit (20 bps)
- Stop loss: -0.15% (15 bps)

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

import time
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from loguru import logger

from app.engine.types import Strategy, Bar, Signal
from app.adapters.feed_binance_l2 import BinanceFuturesL2Feed, OrderBook


@dataclass
class L2StrategyConfig:
    """Configuration for L2 Imbalance Strategy."""

    # Imbalance thresholds
    buy_threshold: Decimal = Decimal("3.0")    # Bid/ask ratio for BUY
    sell_threshold: Decimal = Decimal("0.33")  # Bid/ask ratio for SELL (1/3)

    # Order book depth to analyze
    depth: int = 5  # Top 5 levels per side

    # Position sizing
    position_size_usd: Decimal = Decimal("1000")  # $1000 per trade

    # Risk management
    profit_target_pct: Decimal = Decimal("0.2")   # 20 basis points
    stop_loss_pct: Decimal = Decimal("0.15")      # 15 basis points

    # Time management
    min_signal_strength: Decimal = Decimal("0.5")  # Minimum strength to trade (distance from neutral)
    cooldown_seconds: int = 5  # Cooldown between signals
    max_hold_time_seconds: int = 60  # Time stop (exit after 60s)

    # Spread filter
    max_spread_bps: Decimal = Decimal("50")  # Skip if spread >50 bps

    # Minimum price for quantity calculation
    min_price: Decimal = Decimal("1")

    # Trading mode
    spot_only: bool = False  # If True, only long positions (no shorting)


class L2ImbalanceStrategy(Strategy):
    """
    L2 Order Book Imbalance trading strategy.

    Monitors real-time order book imbalance and generates signals
    when strong supply/demand imbalances are detected.

    This is the CORE strategy for the MFT bot as defined in CLAUDE.md.
    """

    def __init__(
        self,
        symbol: str,
        order_book: OrderBook,
        config: Optional[L2StrategyConfig] = None
    ):
        """
        Initialize L2 Imbalance Strategy.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            order_book: Reference to live order book
            config: Strategy configuration (uses defaults if None)
        """
        self.symbol = symbol
        self.order_book = order_book
        self.config = config or L2StrategyConfig()

        # State tracking
        self.in_position = False
        self.position_side: Optional[str] = None  # "long" | "short"
        self.entry_time: Optional[float] = None
        self.entry_price: Optional[Decimal] = None
        self.last_signal_time: float = 0.0

        # Signal history for cooldown
        self.signal_count = 0

        mode_str = "SPOT-ONLY (LONG ONLY)" if self.config.spot_only else "FUTURES (LONG+SHORT)"
        logger.info(
            f"L2ImbalanceStrategy initialized | "
            f"Symbol: {self.symbol} | "
            f"Mode: {mode_str} | "
            f"BuyThreshold: {self.config.buy_threshold} | "
            f"SellThreshold: {self.config.sell_threshold if not self.config.spot_only else 'N/A'} | "
            f"Depth: {self.config.depth}"
        )

    def on_bar(self, bar: Bar) -> list[Signal]:
        """
        Process new bar and generate signals based on L2 imbalance.

        Args:
            bar: Current bar (contains mid-price)

        Returns:
            List of signals (empty if no action)
        """
        signals = []

        # Check if order book is valid
        if not self.order_book.is_valid():
            logger.warning("Order book invalid, skipping signal generation")
            return signals

        # Get current market state
        current_price = bar.close
        imbalance = self.order_book.calculate_imbalance(self.config.depth)
        spread_bps = self.order_book.get_spread_bps()

        # Filter: Skip if spread too wide
        if spread_bps and spread_bps > self.config.max_spread_bps:
            logger.debug(
                f"Spread too wide: {spread_bps:.2f} bps > {self.config.max_spread_bps} bps"
            )
            return signals

        # Check for exit conditions if in position
        if self.in_position:
            exit_signal = self._check_exit_conditions(
                current_price=current_price,
                imbalance=imbalance
            )
            if exit_signal:
                signals.append(exit_signal)
                self._reset_position()
                return signals

        # Check for entry conditions if not in position
        if not self.in_position:
            # Enforce cooldown
            time_since_last_signal = time.time() - self.last_signal_time
            if time_since_last_signal < self.config.cooldown_seconds:
                return signals

            # Check for BUY signal
            if imbalance >= self.config.buy_threshold:
                signal = self._generate_entry_signal(
                    side="buy",
                    current_price=current_price,
                    imbalance=imbalance
                )
                if signal:
                    signals.append(signal)
                    self._enter_position("long", current_price)

            # Check for SELL signal (skip if spot-only mode)
            elif imbalance <= self.config.sell_threshold and not self.config.spot_only:
                signal = self._generate_entry_signal(
                    side="sell",
                    current_price=current_price,
                    imbalance=imbalance
                )
                if signal:
                    signals.append(signal)
                    self._enter_position("short", current_price)
            elif imbalance <= self.config.sell_threshold and self.config.spot_only:
                # In spot-only mode, bearish signals are ignored (can't short)
                logger.debug(f"Bearish signal ignored (spot-only mode): imbalance={imbalance:.2f}")

        return signals

    def _generate_entry_signal(
        self,
        side: str,
        current_price: Decimal,
        imbalance: Decimal
    ) -> Optional[Signal]:
        """
        Generate entry signal with SL/TP.

        Args:
            side: "buy" or "sell"
            current_price: Current market price
            imbalance: Current imbalance ratio

        Returns:
            Signal or None
        """
        # Calculate signal strength (distance from neutral)
        if side == "buy":
            strength = imbalance - Decimal("1.0")  # >0 is bullish
        else:
            strength = Decimal("1.0") - imbalance  # >0 is bearish

        # Filter weak signals
        if strength < self.config.min_signal_strength - Decimal("1.0"):
            logger.debug(f"Signal too weak: strength={strength:.2f}")
            return None

        # Calculate position size (quantity in base currency)
        qty = self.config.position_size_usd / max(current_price, self.config.min_price)

        # Calculate SL/TP prices
        if side == "buy":
            # Long position
            tp_price = current_price * (Decimal("1") + self.config.profit_target_pct / Decimal("100"))
            sl_price = current_price * (Decimal("1") - self.config.stop_loss_pct / Decimal("100"))
        else:
            # Short position
            tp_price = current_price * (Decimal("1") - self.config.profit_target_pct / Decimal("100"))
            sl_price = current_price * (Decimal("1") + self.config.stop_loss_pct / Decimal("100"))

        # Generate signal
        signal = Signal(
            symbol=self.symbol,
            side=side,
            qty=qty,
            price=current_price,
            sl=sl_price,
            tp=tp_price,
            reason=f"L2 imbalance {imbalance:.2f} {'>' if side == 'buy' else '<'} threshold"
        )

        logger.info(
            f"Entry signal generated: {side.upper()} | "
            f"Imbalance: {imbalance:.2f} | "
            f"Strength: {strength:.2f} | "
            f"Price: {current_price} | "
            f"Qty: {qty:.4f}"
        )

        return signal

    def _check_exit_conditions(
        self,
        current_price: Decimal,
        imbalance: Decimal
    ) -> Optional[Signal]:
        """
        Check if position should be exited.

        Exit conditions:
        1. Time stop (held too long)
        2. Take profit hit
        3. Stop loss hit
        4. Imbalance reversal (counter-signal)

        Args:
            current_price: Current market price
            imbalance: Current imbalance ratio

        Returns:
            Close signal or None
        """
        if not self.in_position or not self.entry_price or not self.entry_time:
            return None

        # Calculate P&L
        if self.position_side == "long":
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * Decimal("100")
        else:  # short
            pnl_pct = ((self.entry_price - current_price) / self.entry_price) * Decimal("100")

        # Time stop
        hold_time = time.time() - self.entry_time
        if hold_time > self.config.max_hold_time_seconds:
            logger.info(f"Time stop triggered: {hold_time:.1f}s > {self.config.max_hold_time_seconds}s")
            return self._generate_exit_signal(current_price, "time_stop")

        # Take profit
        if pnl_pct >= self.config.profit_target_pct:
            logger.info(f"Take profit hit: {pnl_pct:.2f}% >= {self.config.profit_target_pct}%")
            return self._generate_exit_signal(current_price, "take_profit")

        # Stop loss
        if pnl_pct <= -self.config.stop_loss_pct:
            logger.warning(f"Stop loss hit: {pnl_pct:.2f}% <= -{self.config.stop_loss_pct}%")
            return self._generate_exit_signal(current_price, "stop_loss")

        # Imbalance reversal
        if self.position_side == "long" and imbalance < Decimal("1.0"):
            logger.info(f"Imbalance reversal (long): {imbalance:.2f} < 1.0")
            return self._generate_exit_signal(current_price, "imbalance_reversal")
        elif self.position_side == "short" and imbalance > Decimal("1.0"):
            logger.info(f"Imbalance reversal (short): {imbalance:.2f} > 1.0")
            return self._generate_exit_signal(current_price, "imbalance_reversal")

        return None

    def _generate_exit_signal(self, current_price: Decimal, reason: str) -> Signal:
        """
        Generate exit signal (close position).

        Args:
            current_price: Current market price
            reason: Exit reason for logging

        Returns:
            Close signal
        """
        # Calculate qty from entry
        qty = self.config.position_size_usd / max(self.entry_price or Decimal("1"), self.config.min_price)

        signal = Signal(
            symbol=self.symbol,
            side="close",
            qty=qty,
            price=current_price,
            sl=None,
            tp=None,
            reason=f"Exit: {reason}"
        )

        return signal

    def _enter_position(self, side: str, entry_price: Decimal):
        """
        Update state when entering position.

        Args:
            side: "long" or "short"
            entry_price: Entry price
        """
        self.in_position = True
        self.position_side = side
        self.entry_time = time.time()
        self.entry_price = entry_price
        self.last_signal_time = time.time()
        self.signal_count += 1

        logger.info(
            f"Entered position: {side.upper()} | "
            f"Entry: {entry_price} | "
            f"Signal #{self.signal_count}"
        )

    def _reset_position(self):
        """Reset position tracking after exit."""
        self.in_position = False
        self.position_side = None
        self.entry_time = None
        self.entry_price = None

        logger.info("Position exited")

    def reset(self):
        """Reset strategy state (for new session or error recovery)."""
        self.in_position = False
        self.position_side = None
        self.entry_time = None
        self.entry_price = None
        self.last_signal_time = 0.0
        self.signal_count = 0

        logger.info(f"L2ImbalanceStrategy reset: {self.symbol}")

    def get_state(self) -> dict:
        """
        Get current strategy state for monitoring.

        Returns:
            Dict with position info, signal count, etc.
        """
        state = {
            "symbol": self.symbol,
            "in_position": self.in_position,
            "position_side": self.position_side,
            "entry_price": str(self.entry_price) if self.entry_price else None,
            "entry_time": self.entry_time,
            "signal_count": self.signal_count,
            "last_signal_time": self.last_signal_time
        }

        # Add current imbalance if order book valid
        if self.order_book.is_valid():
            state["current_imbalance"] = str(
                self.order_book.calculate_imbalance(self.config.depth)
            )
            state["mid_price"] = str(self.order_book.get_mid_price())

        return state
