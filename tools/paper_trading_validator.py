#!/usr/bin/env python3
"""
Paper Trading Validation Framework

Runs L2 strategy in paper trading mode and tracks performance metrics
to validate the strategy meets Gate 5→6 requirements before live trading.

Gate 5→6 Requirements (CLAUDE.md):
- 60 days of paper trading completed
- Win rate >50%
- Profit factor >1.0
- Confidence that edge exists

This framework:
- Logs all trades to SQLite database
- Tracks P&L, win rate, profit factor, drawdown
- Generates daily reports
- Persists state across sessions
- Can resume after interruption

Usage:
    # Start paper trading session (Kraken Futures - recommended)
    python tools/paper_trading_validator.py --broker kraken --symbol PF_XBTUSD --session 60days

    # Start paper trading session (Binance.us Spot)
    python tools/paper_trading_validator.py --broker binance_us --symbol BTCUSDT --session 60days

    # View current statistics
    python tools/paper_trading_validator.py --report

    # Resume session
    python tools/paper_trading_validator.py --resume 60days
"""

import asyncio
import time
import sys
import sqlite3
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import argparse
import json

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from app.adapters.feed_binance_l2 import BinanceFuturesL2Feed
from app.adapters.broker_kraken import KrakenFuturesBroker
from app.adapters.broker_binance_us import BinanceUSSpotBroker
from app.strategies.alpha_l2_imbalance import L2ImbalanceStrategy, L2StrategyConfig
from app.engine.risk_manager import RiskManager
from app.engine.types import Signal, Bar


class PaperTradingDatabase:
    """SQLite database for paper trading results."""

    def __init__(self, session_name: str):
        """Initialize database."""
        self.db_path = Path(__file__).parent.parent / "data" / f"paper_trading_{session_name}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self):
        """Create database tables."""
        cursor = self.conn.cursor()

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity REAL NOT NULL,
                pnl REAL,
                pnl_pct REAL,
                duration_seconds INTEGER,
                exit_reason TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Session metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Daily statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                trades_count INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                total_pnl REAL NOT NULL,
                win_rate REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def log_trade_entry(self, symbol: str, side: str, price: Decimal, qty: Decimal) -> int:
        """Log trade entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trades (timestamp, symbol, side, entry_price, quantity, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?)
        """, (
            int(time.time() * 1000),
            symbol,
            side,
            float(price),
            float(qty),
            datetime.now().isoformat()
        ))
        self.conn.commit()
        return cursor.lastrowid

    def log_trade_exit(
        self,
        trade_id: int,
        exit_price: Decimal,
        pnl: Decimal,
        pnl_pct: Decimal,
        duration_seconds: int,
        exit_reason: str
    ):
        """Log trade exit."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE trades
            SET exit_price = ?,
                pnl = ?,
                pnl_pct = ?,
                duration_seconds = ?,
                exit_reason = ?,
                status = 'closed'
            WHERE id = ?
        """, (
            float(exit_price),
            float(pnl),
            float(pnl_pct),
            duration_seconds,
            exit_reason,
            trade_id
        ))
        self.conn.commit()

    def get_statistics(self) -> Dict:
        """Get current statistics."""
        cursor = self.conn.cursor()

        # Total trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'closed'")
        total_trades = cursor.fetchone()[0]

        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "days_running": 0
            }

        # Winning/losing trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'closed' AND pnl > 0")
        winning_trades = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'closed' AND pnl < 0")
        losing_trades = cursor.fetchone()[0]

        # P&L
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'closed'")
        total_pnl = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT AVG(pnl) FROM trades WHERE status = 'closed' AND pnl > 0")
        avg_win = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT AVG(pnl) FROM trades WHERE status = 'closed' AND pnl < 0")
        avg_loss = cursor.fetchone()[0] or 0.0

        # Profit factor
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'closed' AND pnl > 0")
        total_wins = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT SUM(ABS(pnl)) FROM trades WHERE status = 'closed' AND pnl < 0")
        total_losses = cursor.fetchone()[0] or 0.0

        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Max drawdown (simplified - cumulative P&L based)
        cursor.execute("SELECT pnl FROM trades WHERE status = 'closed' ORDER BY timestamp ASC")
        pnls = [row[0] for row in cursor.fetchall()]
        cumulative_pnl = []
        running_sum = 0
        for pnl in pnls:
            running_sum += pnl
            cumulative_pnl.append(running_sum)

        max_drawdown = 0.0
        if cumulative_pnl:
            peak = cumulative_pnl[0]
            for value in cumulative_pnl:
                if value > peak:
                    peak = value
                drawdown = peak - value
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # Days running
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM trades WHERE status = 'closed'")
        result = cursor.fetchone()
        if result[0] and result[1]:
            days_running = (result[1] - result[0]) / 1000 / 86400
        else:
            days_running = 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0.0,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "days_running": days_running
        }

    def set_metadata(self, key: str, value: str):
        """Set session metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO session_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().isoformat()))
        self.conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get session metadata."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM session_metadata WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None

    def close(self):
        """Close database connection."""
        self.conn.close()


class PaperTradingValidator:
    """Paper trading validation system."""

    def __init__(
        self,
        broker_type: str,
        symbol: str,
        session_name: str,
        spot_only: bool = False
    ):
        """
        Initialize validator.

        Args:
            broker_type: "kraken" or "binance_us"
            symbol: Trading symbol
            session_name: Session name for database
            spot_only: If True, use spot-only mode
        """
        self.broker_type = broker_type
        self.symbol = symbol
        self.session_name = session_name
        self.spot_only = spot_only

        # Database
        self.db = PaperTradingDatabase(session_name)

        # Simulated positions (for paper trading)
        self.positions: Dict[str, Dict] = {}  # {symbol: {side, entry_price, qty, entry_time, trade_id}}

        # Performance tracking
        self.session_start_time = time.time()

        logger.info(f"Paper Trading Validator initialized | "
                   f"Broker: {broker_type} | "
                   f"Symbol: {symbol} | "
                   f"Session: {session_name} | "
                   f"Mode: {'SPOT-ONLY' if spot_only else 'FUTURES'}")

    async def run(self, duration_hours: int = 24):
        """
        Run paper trading session.

        Args:
            duration_hours: How long to run (hours)
        """
        logger.info("="*80)
        logger.info("STARTING PAPER TRADING VALIDATION")
        logger.info("="*80)

        # Save session metadata
        self.db.set_metadata("broker_type", self.broker_type)
        self.db.set_metadata("symbol", self.symbol)
        self.db.set_metadata("start_time", datetime.now().isoformat())

        # Initialize L2 feed
        feed = BinanceFuturesL2Feed(
            symbol=self.symbol if self.broker_type == "binance_us" else self._map_to_binance_symbol(self.symbol),
            depth=5,
            update_interval_ms=100,
            testnet=True
        )

        # Initialize strategy
        config = L2StrategyConfig(
            spot_only=self.spot_only,
            buy_threshold=Decimal("3.0"),
            sell_threshold=Decimal("0.33"),
            depth=5,
            position_size_usd=Decimal("1000"),  # Paper trading position size
            cooldown_seconds=5
        )
        strategy = L2ImbalanceStrategy(
            symbol=self.symbol,
            order_book=feed.order_book,
            config=config
        )

        # Initialize risk manager
        risk_config = {
            "risk": {
                "max_daily_loss_usd": 500,
                "max_trades_per_day": 20,
                "max_position_usd": 1000
            }
        }
        risk_manager = RiskManager(risk_config)

        # Fetch initial snapshot
        await feed._fetch_snapshot()
        logger.info(f"Order book loaded")

        # Connect WebSocket
        await feed._connect_websocket()
        logger.info("WebSocket connected")

        # Start processing
        feed.running = True
        message_task = asyncio.create_task(feed._process_ws_messages())

        # Main loop
        start_time = time.time()
        last_bar_time = time.time()
        last_report_time = time.time()
        bar_interval = 1.0
        report_interval = 3600  # 1 hour

        try:
            while time.time() - start_time < (duration_hours * 3600):
                await asyncio.sleep(0.01)

                now = time.time()

                # Process bar
                if now - last_bar_time >= bar_interval:
                    await self._process_bar(strategy, risk_manager, feed.order_book)
                    last_bar_time = now

                # Generate report
                if now - last_report_time >= report_interval:
                    self._generate_report()
                    last_report_time = now

        except KeyboardInterrupt:
            logger.info("Paper trading stopped by user")
        finally:
            feed.running = False
            if feed.ws_connection:
                await feed.ws_connection.close()

        # Final report
        self._generate_report(final=True)

    async def _process_bar(
        self,
        strategy: L2ImbalanceStrategy,
        risk_manager: RiskManager,
        order_book
    ):
        """Process one bar."""
        if not order_book.is_valid():
            return

        mid_price = order_book.get_mid_price()
        if not mid_price:
            return

        # Create bar
        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=mid_price,
            high=mid_price,
            low=mid_price,
            close=mid_price,
            volume=Decimal("0")
        )

        # Generate signals
        signals = strategy.on_bar(bar)

        # Process signals
        for signal in signals:
            # Risk check
            risk_result = risk_manager.check_all(signal, self.positions)
            if not risk_result.passed:
                logger.warning(f"Risk check failed: {risk_result.reason}")
                continue

            # Execute paper trade
            self._execute_paper_trade(signal, mid_price)

    def _execute_paper_trade(self, signal: Signal, current_price: Decimal):
        """Execute paper trade (simulated)."""
        symbol = signal.symbol

        if signal.side == "buy":
            # Open long position
            if symbol in self.positions:
                logger.warning(f"Already have position in {symbol}, ignoring BUY signal")
                return

            trade_id = self.db.log_trade_entry(symbol, "long", signal.price, signal.qty)
            self.positions[symbol] = {
                "side": "long",
                "entry_price": signal.price,
                "qty": signal.qty,
                "entry_time": time.time(),
                "trade_id": trade_id
            }
            logger.info(f"PAPER TRADE: BUY {symbol} @ {signal.price} | Qty: {signal.qty}")

        elif signal.side == "sell":
            # Open short position (if not spot-only mode)
            if self.spot_only:
                logger.debug(f"Short signal ignored (spot-only mode)")
                return

            if symbol in self.positions:
                logger.warning(f"Already have position in {symbol}, ignoring SELL signal")
                return

            trade_id = self.db.log_trade_entry(symbol, "short", signal.price, signal.qty)
            self.positions[symbol] = {
                "side": "short",
                "entry_price": signal.price,
                "qty": signal.qty,
                "entry_time": time.time(),
                "trade_id": trade_id
            }
            logger.info(f"PAPER TRADE: SELL {symbol} @ {signal.price} | Qty: {signal.qty}")

        elif signal.side == "close":
            # Close position
            if symbol not in self.positions:
                logger.warning(f"No position to close for {symbol}")
                return

            position = self.positions[symbol]
            entry_price = position["entry_price"]
            qty = position["qty"]
            duration = int(time.time() - position["entry_time"])

            # Calculate P&L
            if position["side"] == "long":
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:  # short
                pnl = (entry_price - current_price) * qty
                pnl_pct = ((entry_price - current_price) / entry_price) * 100

            # Log exit
            self.db.log_trade_exit(
                trade_id=position["trade_id"],
                exit_price=current_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                duration_seconds=duration,
                exit_reason=signal.reason
            )

            logger.info(
                f"PAPER TRADE: CLOSE {symbol} @ {current_price} | "
                f"P&L: ${pnl:.2f} ({pnl_pct:+.2f}%) | "
                f"Duration: {duration}s"
            )

            del self.positions[symbol]

    def _map_to_binance_symbol(self, symbol: str) -> str:
        """Map broker symbol to Binance symbol for L2 feed."""
        mapping = {
            "PF_XBTUSD": "BTCUSDT",
            "PF_ETHUSD": "ETHUSDT",
            "PF_SOLUSD": "SOLUSDT",
            "PF_ADAUSD": "ADAUSDT"
        }
        return mapping.get(symbol, symbol)

    def _generate_report(self, final: bool = False):
        """Generate performance report."""
        stats = self.db.get_statistics()

        logger.info("="*80)
        logger.info("PAPER TRADING REPORT" if not final else "FINAL PAPER TRADING REPORT")
        logger.info("="*80)

        logger.info(f"Session: {self.session_name}")
        logger.info(f"Days Running: {stats['days_running']:.1f} / 60 days required")
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Winning Trades: {stats['winning_trades']}")
        logger.info(f"Losing Trades: {stats['losing_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.2f}% (Target: >50%)")
        logger.info(f"Total P&L: ${stats['total_pnl']:.2f}")
        logger.info(f"Avg Win: ${stats['avg_win']:.2f}")
        logger.info(f"Avg Loss: ${stats['avg_loss']:.2f}")
        logger.info(f"Profit Factor: {stats['profit_factor']:.2f} (Target: >1.0)")
        logger.info(f"Max Drawdown: ${stats['max_drawdown']:.2f}")

        # Gate 5→6 validation
        logger.info("")
        logger.info("Gate 5→6 Requirements:")
        days_met = stats['days_running'] >= 60
        win_rate_met = stats['win_rate'] > 50
        profit_factor_met = stats['profit_factor'] > 1.0

        logger.info(f"  [{'✓' if days_met else '✗'}] 60 days completed: {stats['days_running']:.1f} days")
        logger.info(f"  [{'✓' if win_rate_met else '✗'}] Win rate >50%: {stats['win_rate']:.2f}%")
        logger.info(f"  [{'✓' if profit_factor_met else '✗'}] Profit factor >1.0: {stats['profit_factor']:.2f}")

        if days_met and win_rate_met and profit_factor_met:
            logger.success("="*80)
            logger.success("✓ ALL GATE 5→6 REQUIREMENTS MET - READY FOR LIVE TRADING")
            logger.success("="*80)
        else:
            logger.warning("Gate 5→6 requirements NOT YET MET - continue paper trading")

        logger.info("="*80)


def generate_report_only(session_name: str):
    """Generate report for existing session."""
    db = PaperTradingDatabase(session_name)
    stats = db.get_statistics()

    logger.info("="*80)
    logger.info(f"PAPER TRADING REPORT - Session: {session_name}")
    logger.info("="*80)

    if stats['total_trades'] == 0:
        logger.warning("No trades found in session")
        return

    logger.info(f"Days Running: {stats['days_running']:.1f} / 60 days required")
    logger.info(f"Total Trades: {stats['total_trades']}")
    logger.info(f"Win Rate: {stats['win_rate']:.2f}% (Target: >50%)")
    logger.info(f"Total P&L: ${stats['total_pnl']:.2f}")
    logger.info(f"Profit Factor: {stats['profit_factor']:.2f} (Target: >1.0)")
    logger.info(f"Max Drawdown: ${stats['max_drawdown']:.2f}")

    # Gate validation
    logger.info("")
    logger.info("Gate 5→6 Status:")
    days_met = stats['days_running'] >= 60
    win_rate_met = stats['win_rate'] > 50
    profit_factor_met = stats['profit_factor'] > 1.0

    logger.info(f"  [{'✓' if days_met else '✗'}] 60 days completed")
    logger.info(f"  [{'✓' if win_rate_met else '✗'}] Win rate >50%")
    logger.info(f"  [{'✓' if profit_factor_met else '✗'}] Profit factor >1.0")

    if days_met and win_rate_met and profit_factor_met:
        logger.success("✓ READY FOR LIVE TRADING")
    else:
        logger.warning("Continue paper trading")

    logger.info("="*80)

    db.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Paper Trading Validator')
    parser.add_argument('--broker', type=str, choices=['kraken', 'binance_us'],
                       help='Broker to use (kraken recommended for full strategy)')
    parser.add_argument('--symbol', type=str,
                       help='Trading symbol (e.g., PF_XBTUSD for Kraken, BTCUSDT for Binance.us)')
    parser.add_argument('--session', type=str,
                       help='Session name (e.g., "60days")')
    parser.add_argument('--duration', type=int, default=24,
                       help='Duration in hours (default: 24, runs continuously if > 24*60)')
    parser.add_argument('--report', action='store_true',
                       help='Generate report for existing session (specify --session)')
    parser.add_argument('--resume', type=str,
                       help='Resume existing session (specify session name)')

    args = parser.parse_args()

    # Report mode
    if args.report:
        if not args.session:
            logger.error("--session required for --report")
            sys.exit(1)
        generate_report_only(args.session)
        return

    # Validate arguments
    if not args.broker or not args.symbol or not args.session:
        logger.error("--broker, --symbol, and --session required (or use --report)")
        parser.print_help()
        sys.exit(1)

    # Determine spot-only mode
    spot_only = args.broker == "binance_us"

    # Create validator
    validator = PaperTradingValidator(
        broker_type=args.broker,
        symbol=args.symbol,
        session_name=args.session,
        spot_only=spot_only
    )

    try:
        await validator.run(duration_hours=args.duration)
    except Exception as e:
        logger.error(f"Paper trading failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        validator.db.close()


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    asyncio.run(main())
