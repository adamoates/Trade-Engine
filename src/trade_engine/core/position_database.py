"""
Position Database - Persistent storage for entry prices and P&L tracking.

Fixes critical gaps in P&L calculation:
1. Stores entry prices for Binance.us Spot (which doesn't track them natively)
2. Provides position persistence across reconnections
3. Tracks realized P&L for all brokers
4. Enables accurate cost basis calculation for spot holdings

Usage:
    db = PositionDatabase(db_path="data/positions_live.db")

    # Record entry
    db.open_position(
        symbol="BTCUSDT",
        side="long",
        entry_price=Decimal("50000.00"),
        qty=Decimal("0.01"),
        broker="binance_us"
    )

    # Record exit and calculate P&L
    db.close_position(
        symbol="BTCUSDT",
        exit_price=Decimal("50100.00"),
        exit_reason="take_profit"
    )

    # Retrieve open positions
    positions = db.get_open_positions()
"""

import sqlite3
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger


class PositionDatabaseError(Exception):
    """Position database errors."""
    pass


class PositionDatabase:
    """
    Persistent position tracking database.

    Stores entry prices and calculates P&L for:
    - Spot trading (Binance.us, Coinbase, etc.)
    - Futures trading (backup to exchange data)
    - Position recovery after reconnection

    Uses SQLite for:
    - Reliability (ACID compliance)
    - Simplicity (no external database)
    - Performance (local file access)
    """

    def __init__(self, db_path: str = "data/positions_live.db"):
        """
        Initialize position database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Create data directory if needed
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"PositionDatabase initialized | DB: {db_path}")

    def _init_database(self):
        """Create database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Positions table - tracks OPEN positions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                qty REAL NOT NULL,
                broker TEXT NOT NULL,
                entry_time INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(symbol, broker)
            )
        """)

        # Trades table - tracks CLOSED positions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                qty REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                duration_seconds INTEGER NOT NULL,
                exit_reason TEXT NOT NULL,
                broker TEXT NOT NULL,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Daily statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                broker TEXT NOT NULL,
                trades_count INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                total_pnl REAL NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Session metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

        logger.debug("Database schema initialized")

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        qty: Decimal,
        broker: str = "unknown"
    ) -> int:
        """
        Record position entry.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "long" or "short"
            entry_price: Entry price (MUST be Decimal)
            qty: Position size in base currency (MUST be Decimal)
            broker: Broker name for multi-broker support

        Returns:
            Position ID

        Raises:
            PositionDatabaseError: If position already exists or invalid data
        """
        if not isinstance(entry_price, Decimal):
            raise PositionDatabaseError(
                f"entry_price must be Decimal, got {type(entry_price)}"
            )

        if not isinstance(qty, Decimal):
            raise PositionDatabaseError(
                f"qty must be Decimal, got {type(qty)}"
            )

        if side not in ("long", "short"):
            raise PositionDatabaseError(
                f"side must be 'long' or 'short', got '{side}'"
            )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO positions (
                    symbol, side, entry_price, qty, broker, entry_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                side,
                float(entry_price),
                float(qty),
                broker,
                int(time.time()),
                datetime.now().isoformat()
            ))

            position_id = cursor.lastrowid
            conn.commit()

            logger.info(
                f"Position opened | ID: {position_id} | "
                f"{symbol} {side} @ {entry_price} | "
                f"Qty: {qty} | Broker: {broker}"
            )

            return position_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Position already exists: {symbol} on {broker}")
            raise PositionDatabaseError(
                f"Position already open for {symbol} on {broker}"
            ) from e
        finally:
            conn.close()

    def close_position(
        self,
        symbol: str,
        exit_price: Decimal,
        exit_reason: str,
        broker: str = "unknown"
    ) -> Dict:
        """
        Record position exit and calculate P&L.

        Args:
            symbol: Trading pair
            exit_price: Exit price (MUST be Decimal)
            exit_reason: Reason for exit (e.g., "take_profit", "stop_loss")
            broker: Broker name

        Returns:
            Trade details with P&L

        Raises:
            PositionDatabaseError: If position not found or invalid data
        """
        if not isinstance(exit_price, Decimal):
            raise PositionDatabaseError(
                f"exit_price must be Decimal, got {type(exit_price)}"
            )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get position details
            cursor.execute("""
                SELECT id, side, entry_price, qty, entry_time
                FROM positions
                WHERE symbol = ? AND broker = ?
            """, (symbol, broker))

            row = cursor.fetchone()
            if not row:
                raise PositionDatabaseError(
                    f"No open position found for {symbol} on {broker}"
                )

            position_id, side, entry_price_float, qty_float, entry_time = row

            # Convert to Decimal for accurate calculations
            entry_price = Decimal(str(entry_price_float))
            qty = Decimal(str(qty_float))

            # Calculate P&L
            if side == "long":
                pnl = (exit_price - entry_price) * qty
                pnl_pct = ((exit_price - entry_price) / entry_price) * Decimal("100")
            else:  # short
                pnl = (entry_price - exit_price) * qty
                pnl_pct = ((entry_price - exit_price) / entry_price) * Decimal("100")

            exit_time = int(time.time())
            duration_seconds = exit_time - entry_time

            # Record trade
            cursor.execute("""
                INSERT INTO trades (
                    symbol, side, entry_price, exit_price, qty,
                    pnl, pnl_pct, duration_seconds, exit_reason,
                    broker, entry_time, exit_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                side,
                float(entry_price),
                float(exit_price),
                float(qty),
                float(pnl),
                float(pnl_pct),
                duration_seconds,
                exit_reason,
                broker,
                entry_time,
                exit_time,
                datetime.now().isoformat()
            ))

            # Delete from positions
            cursor.execute("""
                DELETE FROM positions WHERE id = ?
            """, (position_id,))

            conn.commit()

            logger.info(
                f"Position closed | {symbol} {side} | "
                f"Entry: {entry_price} → Exit: {exit_price} | "
                f"P&L: {pnl:.2f} ({pnl_pct:.2f}%) | "
                f"Reason: {exit_reason} | Duration: {duration_seconds}s"
            )

            return {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "qty": qty,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "duration_seconds": duration_seconds,
                "exit_reason": exit_reason,
                "broker": broker
            }

        finally:
            conn.close()

    def get_open_positions(self, broker: Optional[str] = None) -> Dict[str, Dict]:
        """
        Retrieve all open positions.

        Args:
            broker: Filter by broker (None = all brokers)

        Returns:
            Dict of {symbol: position_data}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if broker:
                cursor.execute("""
                    SELECT symbol, side, entry_price, qty, broker, entry_time
                    FROM positions
                    WHERE broker = ?
                """, (broker,))
            else:
                cursor.execute("""
                    SELECT symbol, side, entry_price, qty, broker, entry_time
                    FROM positions
                """)

            positions = {}
            for row in cursor.fetchall():
                symbol, side, entry_price, qty, broker_name, entry_time = row
                positions[symbol] = {
                    "side": side,
                    "entry_price": Decimal(str(entry_price)),
                    "qty": Decimal(str(qty)),
                    "broker": broker_name,
                    "entry_time": entry_time,
                    "duration_seconds": int(time.time()) - entry_time
                }

            return positions

        finally:
            conn.close()

    def get_position(self, symbol: str, broker: str = "unknown") -> Optional[Dict]:
        """
        Get specific position by symbol.

        Args:
            symbol: Trading pair
            broker: Broker name

        Returns:
            Position dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT side, entry_price, qty, entry_time
                FROM positions
                WHERE symbol = ? AND broker = ?
            """, (symbol, broker))

            row = cursor.fetchone()
            if not row:
                return None

            side, entry_price, qty, entry_time = row
            return {
                "side": side,
                "entry_price": Decimal(str(entry_price)),
                "qty": Decimal(str(qty)),
                "entry_time": entry_time,
                "duration_seconds": int(time.time()) - entry_time
            }

        finally:
            conn.close()

    def calculate_unrealized_pnl(
        self,
        symbol: str,
        current_price: Decimal,
        broker: str = "unknown"
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate unrealized P&L for open position.

        Args:
            symbol: Trading pair
            current_price: Current market price
            broker: Broker name

        Returns:
            Tuple of (pnl, pnl_pct)

        Raises:
            PositionDatabaseError: If position not found
        """
        position = self.get_position(symbol, broker)
        if not position:
            raise PositionDatabaseError(
                f"No open position for {symbol} on {broker}"
            )

        entry_price = position["entry_price"]
        qty = position["qty"]
        side = position["side"]

        if side == "long":
            pnl = (current_price - entry_price) * qty
            pnl_pct = ((current_price - entry_price) / entry_price) * Decimal("100")
        else:  # short
            pnl = (entry_price - current_price) * qty
            pnl_pct = ((entry_price - current_price) / entry_price) * Decimal("100")

        return pnl, pnl_pct

    def get_daily_pnl(self, broker: Optional[str] = None) -> Decimal:
        """
        Get total realized P&L for today.

        Args:
            broker: Filter by broker (None = all brokers)

        Returns:
            Total P&L for today
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp()

            if broker:
                cursor.execute("""
                    SELECT SUM(pnl) FROM trades
                    WHERE exit_time >= ? AND broker = ?
                """, (today_start, broker))
            else:
                cursor.execute("""
                    SELECT SUM(pnl) FROM trades
                    WHERE exit_time >= ?
                """, (today_start,))

            result = cursor.fetchone()[0]
            return Decimal(str(result)) if result else Decimal("0")

        finally:
            conn.close()

    def get_statistics(
        self,
        days: int = 30,
        broker: Optional[str] = None
    ) -> Dict:
        """
        Get trading statistics for last N days.

        Args:
            days: Number of days to analyze
            broker: Filter by broker

        Returns:
            Statistics dict with win rate, profit factor, etc.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp())

            if broker:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_wins,
                        SUM(CASE WHEN pnl <= 0 THEN ABS(pnl) ELSE 0 END) as total_losses
                    FROM trades
                    WHERE exit_time >= ? AND broker = ?
                """, (cutoff_time, broker))
            else:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_wins,
                        SUM(CASE WHEN pnl <= 0 THEN ABS(pnl) ELSE 0 END) as total_losses
                    FROM trades
                    WHERE exit_time >= ?
                """, (cutoff_time,))

            row = cursor.fetchone()

            if not row or row[0] == 0:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl": Decimal("0"),
                    "avg_pnl": Decimal("0"),
                    "profit_factor": 0.0
                }

            total_trades, winning_trades, losing_trades, total_pnl, avg_pnl, total_wins, total_losses = row

            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades or 0,
                "losing_trades": losing_trades or 0,
                "win_rate": round(win_rate, 2),
                "total_pnl": Decimal(str(total_pnl)) if total_pnl else Decimal("0"),
                "avg_pnl": Decimal(str(avg_pnl)) if avg_pnl else Decimal("0"),
                "profit_factor": round(profit_factor, 2)
            }

        finally:
            conn.close()

    def clear_all_positions(self):
        """
        Clear all open positions (emergency use only).

        WARNING: This does not place orders to close positions.
        Only clears the database records.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM positions")
            deleted_count = cursor.rowcount
            conn.commit()

            logger.warning(
                f"Cleared {deleted_count} positions from database | "
                "Manual intervention may be required"
            )

        finally:
            conn.close()
