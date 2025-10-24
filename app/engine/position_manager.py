"""
Position manager with P&L tracking for live trading.

Tracks open positions, calculates unrealized/realized P&L,
and manages position lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class Position:
    """Open trading position."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.side == "LONG":
            return (current_price - self.entry_price) * self.quantity
        else:  # SHORT
            return (self.entry_price - current_price) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        """Calculate unrealized P&L as percentage."""
        pnl = self.unrealized_pnl(current_price)
        notional = self.entry_price * self.quantity
        return (pnl / notional) * 100 if notional > 0 else 0.0


@dataclass
class ClosedTrade:
    """Completed trade record."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    duration_seconds: float
    exit_reason: str  # "TP", "SL", "SIGNAL", "MANUAL"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'exit_reason': self.exit_reason
        }


class PositionManager:
    """
    Manages trading positions and calculates P&L.

    Tracks:
    - Open positions (unrealized P&L)
    - Closed trades (realized P&L)
    - Total equity and performance metrics
    """

    def __init__(self, initial_capital: float):
        """
        Initialize position manager.

        Args:
            initial_capital: Starting capital in USD
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital  # Available cash
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.closed_trades: List[ClosedTrade] = []

        logger.info(f"PositionManager initialized | Capital: ${initial_capital:,.2f}")

    @property
    def total_unrealized_pnl(self) -> float:
        """Total unrealized P&L from all open positions."""
        # Note: Requires current prices - will be passed in
        return 0.0  # Placeholder - calculated in get_equity()

    @property
    def total_realized_pnl(self) -> float:
        """Total realized P&L from closed trades."""
        return sum(trade.pnl for trade in self.closed_trades)

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate current total equity.

        Args:
            current_prices: Dict of symbol -> current price

        Returns:
            Total equity (cash + unrealized P&L)
        """
        unrealized = sum(
            pos.unrealized_pnl(current_prices.get(pos.symbol, pos.entry_price))
            for pos in self.positions.values()
        )
        return self.cash + unrealized

    def can_open_position(
        self,
        symbol: str,
        size_usd: float,
        current_prices: Dict[str, float]
    ) -> bool:
        """
        Check if we have enough capital to open position.

        Args:
            symbol: Trading symbol
            size_usd: Position size in USD
            current_prices: Current market prices

        Returns:
            True if position can be opened
        """
        # Check if already have position in this symbol
        if symbol in self.positions:
            logger.warning(f"Already have open position in {symbol}")
            return False

        # Check if we have enough cash
        equity = self.get_equity(current_prices)

        if size_usd > self.cash:
            logger.warning(
                f"Insufficient cash | Need: ${size_usd:.2f}, Have: ${self.cash:.2f}"
            )
            return False

        return True

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Position:
        """
        Open a new position.

        Args:
            symbol: Trading symbol
            side: "LONG" or "SHORT"
            entry_price: Entry price
            quantity: Position size in base currency
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price

        Returns:
            Position object
        """
        notional = entry_price * quantity

        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(timezone.utc),
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.positions[symbol] = position
        self.cash -= notional  # Lock up cash

        logger.info(
            f"📈 Opened {side} position | "
            f"{symbol} @ ${entry_price:.2f} | "
            f"Qty: {quantity:.6f} | "
            f"Notional: ${notional:.2f}"
        )

        if stop_loss:
            logger.info(f"  SL: ${stop_loss:.2f}")
        if take_profit:
            logger.info(f"  TP: ${take_profit:.2f}")

        return position

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str = "MANUAL"
    ) -> Optional[ClosedTrade]:
        """
        Close an open position.

        Args:
            symbol: Symbol to close
            exit_price: Exit price
            exit_reason: Reason for exit ("TP", "SL", "SIGNAL", "MANUAL")

        Returns:
            ClosedTrade object if position was closed, None if no position
        """
        if symbol not in self.positions:
            logger.warning(f"No open position in {symbol}")
            return None

        pos = self.positions.pop(symbol)
        exit_time = datetime.now(timezone.utc)

        # Calculate P&L
        pnl = pos.unrealized_pnl(exit_price)
        pnl_pct = pos.unrealized_pnl_pct(exit_price)

        # Return cash
        exit_notional = exit_price * pos.quantity
        self.cash += exit_notional

        # Create trade record
        trade = ClosedTrade(
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            duration_seconds=(exit_time - pos.entry_time).total_seconds(),
            exit_reason=exit_reason
        )

        self.closed_trades.append(trade)

        logger.info(
            f"📉 Closed {pos.side} position | "
            f"{symbol} @ ${exit_price:.2f} | "
            f"P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%) | "
            f"Reason: {exit_reason}"
        )

        return trade

    def check_stops(self, current_prices: Dict[str, float]) -> List[ClosedTrade]:
        """
        Check all positions for stop loss / take profit hits.

        Args:
            current_prices: Current market prices

        Returns:
            List of trades that were closed
        """
        closed = []

        for symbol, pos in list(self.positions.items()):
            current_price = current_prices.get(symbol)
            if not current_price:
                continue

            # Check stop loss
            if pos.stop_loss:
                if (pos.side == "LONG" and current_price <= pos.stop_loss) or \
                   (pos.side == "SHORT" and current_price >= pos.stop_loss):
                    logger.warning(f"🛑 Stop loss hit: {symbol} @ ${current_price:.2f}")
                    trade = self.close_position(symbol, current_price, "SL")
                    if trade:
                        closed.append(trade)
                    continue

            # Check take profit
            if pos.take_profit:
                if (pos.side == "LONG" and current_price >= pos.take_profit) or \
                   (pos.side == "SHORT" and current_price <= pos.take_profit):
                    logger.success(f"🎯 Take profit hit: {symbol} @ ${current_price:.2f}")
                    trade = self.close_position(symbol, current_price, "TP")
                    if trade:
                        closed.append(trade)

        return closed

    def get_stats(self, current_prices: Dict[str, float]) -> Dict:
        """
        Get performance statistics.

        Args:
            current_prices: Current market prices

        Returns:
            Dictionary of stats
        """
        equity = self.get_equity(current_prices)
        total_pnl = equity - self.initial_capital
        return_pct = (total_pnl / self.initial_capital) * 100

        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl < 0]

        return {
            'initial_capital': self.initial_capital,
            'equity': equity,
            'cash': self.cash,
            'total_pnl': total_pnl,
            'return_pct': return_pct,
            'realized_pnl': self.total_realized_pnl,
            'open_positions': len(self.positions),
            'total_trades': len(self.closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.closed_trades) if self.closed_trades else 0.0
        }
