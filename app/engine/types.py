"""
Core interfaces for live trading engine.

Defines abstract base classes for DataFeed, Broker, and Strategy.
These interfaces allow for easy testing (mock implementations) and
swapping between paper/live brokers.

CRITICAL: All financial values (prices, quantities, P&L) use Decimal
to avoid float rounding errors. This is NON-NEGOTIABLE per CLAUDE.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Dict, Any
from datetime import datetime
from decimal import Decimal


@dataclass
class Bar:
    """Single OHLCV bar with validation metadata."""
    timestamp: int       # UTC timestamp (milliseconds)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    gap_flag: bool = False       # True if bar was filled/imputed
    zero_vol_flag: bool = False  # True if zero volume (should skip)

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime (UTC)."""
        return datetime.utcfromtimestamp(self.timestamp / 1000)

    def __repr__(self):
        return (f"Bar(ts={self.datetime.isoformat()}, "
                f"O={self.open:.2f}, H={self.high:.2f}, "
                f"L={self.low:.2f}, C={self.close:.2f}, V={self.volume:.2f})")


@dataclass
class Signal:
    """Trading signal from strategy."""
    symbol: str
    side: str           # "buy" | "sell" | "close"
    qty: Decimal        # Base currency quantity (e.g., 0.01 BTC)
    price: Decimal      # Signal generation price (for logging)
    sl: Decimal | None = None    # Stop loss price
    tp: Decimal | None = None    # Take profit price
    reason: str = ""           # Why signal generated (for audit log)

    def __repr__(self):
        sl_str = f"{self.sl:.2f}" if self.sl is not None else "None"
        tp_str = f"{self.tp:.2f}" if self.tp is not None else "None"
        return (f"Signal({self.side.upper()} {self.qty} {self.symbol} @ {self.price:.2f}, "
                f"SL={sl_str}, TP={tp_str})")


@dataclass
class Position:
    """Current position state."""
    symbol: str
    side: str           # "long" | "short"
    qty: Decimal        # Position size (base currency)
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal        # Unrealized P&L (USD)
    pnl_pct: Decimal    # Unrealized P&L (%)

    @property
    def notional(self) -> Decimal:
        """Position notional value (USD)."""
        return self.qty * self.current_price

    def __repr__(self):
        return (f"Position({self.side.upper()} {self.qty} {self.symbol} @ {self.entry_price:.2f}, "
                f"PnL=${self.pnl:.2f} ({self.pnl_pct:+.2f}%))")


class DataFeed(ABC):
    """
    Abstract data feed interface.

    Implementations:
    - BinanceFuturesDataFeed (live REST polling)
    - BinanceFuturesWSFeed (websocket - future)
    - BacktestDataFeed (historical CSV - for validation)
    """

    @abstractmethod
    def candles(self) -> Iterator[Bar]:
        """
        Yield validated bars (bar-close only).

        Should:
        - Only yield completed bars (not partial)
        - Validate bar quality (no gaps, no zero volume)
        - Set gap_flag, zero_vol_flag appropriately
        - Sleep until next bar close
        """
        pass


class Broker(ABC):
    """
    Abstract broker interface.

    Implementations:
    - BinanceFuturesBroker (live)
    - BinanceFuturesPaperBroker (testnet)
    - MockBroker (unit tests)
    """

    @abstractmethod
    def buy(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """
        Place buy order (long entry or short exit).

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            qty: Quantity in base currency (e.g., 0.01 BTC)
            sl: Stop loss price (optional)
            tp: Take profit price (optional)

        Returns:
            order_id: Exchange order ID

        Raises:
            BrokerError: On exchange errors, insufficient balance, etc.
        """
        pass

    @abstractmethod
    def sell(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """
        Place sell order (short entry or long exit).

        Args/Returns: Same as buy()
        """
        pass

    @abstractmethod
    def close_all(self, symbol: str):
        """
        Flatten position (market order, both sides if hedging).

        Args:
            symbol: Trading pair to close
        """
        pass

    @abstractmethod
    def positions(self) -> Dict[str, Position]:
        """
        Get current positions.

        Returns:
            Dict mapping symbol → Position
            Empty dict if no positions
        """
        pass

    @abstractmethod
    def balance(self) -> Decimal:
        """
        Get available balance (USD or USDT).

        Returns:
            Available balance for trading
        """
        pass


class Strategy(ABC):
    """
    Abstract strategy interface.

    Implementations wrap existing strategies (trending_v3, etc.)
    """

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[Signal]:
        """
        Process new bar, return signals.

        Args:
            bar: Completed, validated bar

        Returns:
            List of signals (empty list if no action)

        Note:
            - Should update internal state (indicators, regime, etc.)
            - Should respect cooldown periods
            - Should NOT execute trades (that's the runner's job)
        """
        pass

    @abstractmethod
    def reset(self):
        """
        Reset strategy state (for new session or error recovery).
        """
        pass
