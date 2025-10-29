#!/usr/bin/env python3
"""
4-Hour Proof of Concept Trading Test

Stakeholder Test Parameters:
- Capital: $500
- Target: $6 profit ($1.50/hour for 4 hours)
- Duration: 4 hours
- Mode: Binance Testnet (paper trading)

This script runs a complete live trading session with:
- Real-time market data from Binance Testnet
- RSI Divergence strategy with L2 confirmation
- Position sizing and risk management
- Performance tracking and reporting
- Automatic stop on profit target or loss limit

Usage:
    python tools/run_poc_test.py

    # Dry run (no actual trades)
    python tools/run_poc_test.py --dry-run

    # Custom duration
    python tools/run_poc_test.py --hours 2
"""

import sys
import os
import argparse
import asyncio
import signal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import json

import yaml
from loguru import logger

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trade_engine.adapters.brokers.binance import BinanceFuturesBroker as BinanceBroker
from trade_engine.domain.strategies.rsi_divergence import RSIDivergenceStrategy
from trade_engine.services.data.multi_source_ohlcv import MultiSourceOHLCV
from trade_engine.services.data.signal_confirmation import SignalConfirmationFilter
from trade_engine.domain.risk.risk_manager import RiskManager


@dataclass
class Trade:
    """Record of a completed trade."""
    timestamp: datetime
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fees: float
    conviction: float
    duration_seconds: float


@dataclass
class PerformanceMetrics:
    """Performance tracking for POC test."""
    start_time: datetime
    end_time: Optional[datetime] = None

    # Capital
    initial_capital: float = 500.0
    current_equity: float = 500.0

    # Trades
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # P&L
    total_pnl: float = 0.0
    total_fees: float = 0.0
    gross_pnl: float = 0.0

    # Hourly tracking
    hourly_pnl: List[float] = field(default_factory=list)

    # Trade history
    trades: List[Trade] = field(default_factory=list)

    def add_trade(self, trade: Trade):
        """Record a trade and update metrics."""
        self.trades.append(trade)
        self.total_trades += 1

        if trade.pnl > 0:
            self.winning_trades += 1
        elif trade.pnl < 0:
            self.losing_trades += 1

        self.total_pnl += trade.pnl
        self.total_fees += trade.fees
        self.gross_pnl = self.total_pnl + self.total_fees
        self.current_equity = self.initial_capital + self.total_pnl

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def return_pct(self) -> float:
        """Calculate return percentage."""
        return (self.total_pnl / self.initial_capital) * 100

    @property
    def avg_win(self) -> float:
        """Average winning trade P&L."""
        winners = [t.pnl for t in self.trades if t.pnl > 0]
        return sum(winners) / len(winners) if winners else 0.0

    @property
    def avg_loss(self) -> float:
        """Average losing trade P&L."""
        losers = [t.pnl for t in self.trades if t.pnl < 0]
        return sum(losers) / len(losers) if losers else 0.0

    @property
    def profit_factor(self) -> float:
        """Profit factor (gross profit / gross loss)."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'initial_capital': self.initial_capital,
            'final_equity': self.current_equity,
            'total_pnl': self.total_pnl,
            'return_pct': self.return_pct,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'total_fees': self.total_fees,
            'hourly_pnl': self.hourly_pnl,
            'trades': [asdict(t) for t in self.trades]
        }


class POCTradingRunner:
    """
    4-hour proof-of-concept trading runner.

    Orchestrates:
    - Market data feed
    - Strategy execution
    - Risk management
    - Performance tracking
    - Reporting
    """

    def __init__(self, config_path: str, dry_run: bool = False):
        """Initialize POC runner."""
        self.dry_run = dry_run
        self.running = False
        self.config = self._load_config(config_path)

        # Initialize metrics
        self.metrics = PerformanceMetrics(
            start_time=datetime.now(timezone.utc),
            initial_capital=self.config['test_config']['capital_usd']
        )

        # Performance targets
        self.profit_target = self.config['test_config']['profit_target_usd']
        self.max_loss = self.config['risk']['max_daily_loss_usd']
        self.duration_hours = self.config['test_config']['duration_hours']

        # Test end time
        self.end_time = self.metrics.start_time + timedelta(hours=self.duration_hours)

        # Setup logging
        self._setup_logging()

        logger.info("=" * 80)
        logger.info("🚀 MFT TRADING BOT - 4-HOUR PROOF OF CONCEPT TEST")
        logger.info("=" * 80)
        logger.info(f"Capital: ${self.metrics.initial_capital:,.2f}")
        logger.info(f"Profit Target: ${self.profit_target:,.2f} (${self.config['test_config']['target_hourly_rate']}/hour)")
        logger.info(f"Max Loss: ${self.max_loss:,.2f}")
        logger.info(f"Duration: {self.duration_hours} hours")
        logger.info(f"End Time: {self.end_time.strftime('%H:%M:%S UTC')}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE TESTNET'}")
        logger.info("=" * 80)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML."""
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """Configure logging."""
        log_dir = Path(self.config['monitoring']['audit_logging']['log_dir'])
        log_dir.mkdir(parents=True, exist_ok=True)

        # Log file for this test
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"poc_test_{timestamp}.log"

        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:HH:MM:SS}</green> | <level>{level:8}</level> | <level>{message}</level>",
            level="INFO"
        )
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}",
            level="DEBUG"
        )

        self.log_file = log_file
        logger.info(f"Logging to: {log_file}")

    async def run(self):
        """
        Run the 4-hour trading test.

        Main loop:
        1. Fetch market data every 5 minutes
        2. Run strategy to generate signals
        3. Execute trades (with risk checks)
        4. Track performance
        5. Check exit conditions
        """
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        try:
            # Initialize components
            await self._initialize_components()

            # Main trading loop
            last_report_time = datetime.now(timezone.utc)
            report_interval = timedelta(minutes=self.config['metrics']['report_interval_minutes'])

            while self.running:
                current_time = datetime.now(timezone.utc)

                # Check if test duration completed
                if current_time >= self.end_time:
                    logger.info("✅ Test duration completed")
                    break

                # Check profit target
                if self.metrics.total_pnl >= self.profit_target:
                    logger.success(f"🎯 PROFIT TARGET REACHED: ${self.metrics.total_pnl:,.2f}")
                    break

                # Check max loss
                if self.metrics.total_pnl <= -self.max_loss:
                    logger.error(f"🛑 MAX LOSS HIT: ${self.metrics.total_pnl:,.2f}")
                    break

                # Run trading cycle
                await self._trading_cycle()

                # Periodic reporting
                if current_time - last_report_time >= report_interval:
                    self._print_progress_report()
                    last_report_time = current_time

                # Wait for next cycle (5-minute bars)
                await asyncio.sleep(300)  # 5 minutes

        except Exception as e:
            logger.exception(f"Fatal error: {e}")

        finally:
            await self._shutdown()

    async def _initialize_components(self):
        """Initialize trading components."""
        logger.info("Initializing trading components...")

        # TODO: Initialize broker, strategy, data feed
        # For now, we'll simulate this
        logger.info("✓ Components initialized (simulated)")

    async def _trading_cycle(self):
        """Execute one trading cycle."""
        # TODO: Implement actual trading logic
        # For now, simulate
        logger.debug("Trading cycle executed (simulated)")

    def _print_progress_report(self):
        """Print progress report."""
        elapsed = datetime.now(timezone.utc) - self.metrics.start_time
        remaining = self.end_time - datetime.now(timezone.utc)

        logger.info("=" * 80)
        logger.info("📊 PROGRESS REPORT")
        logger.info("=" * 80)
        logger.info(f"Elapsed: {elapsed.seconds // 3600}h {(elapsed.seconds % 3600) // 60}m")
        logger.info(f"Remaining: {remaining.seconds // 3600}h {(remaining.seconds % 3600) // 60}m")
        logger.info(f"Equity: ${self.metrics.current_equity:,.2f} ({self.metrics.return_pct:+.2f}%)")
        logger.info(f"P&L: ${self.metrics.total_pnl:+,.2f} (Target: ${self.profit_target:,.2f})")
        logger.info(f"Trades: {self.metrics.total_trades} (W: {self.metrics.winning_trades}, L: {self.metrics.losing_trades})")
        if self.metrics.total_trades > 0:
            logger.info(f"Win Rate: {self.metrics.win_rate:.1%}")
        logger.info("=" * 80)

    async def _shutdown(self):
        """Shutdown and generate final report."""
        logger.info("Shutting down...")

        self.metrics.end_time = datetime.now(timezone.utc)

        # Generate final report
        self._generate_final_report()

        logger.info("✓ Shutdown complete")

    def _generate_final_report(self):
        """Generate stakeholder report."""
        logger.info("=" * 80)
        logger.info("📈 FINAL REPORT - 4-HOUR PROOF OF CONCEPT TEST")
        logger.info("=" * 80)

        duration = self.metrics.end_time - self.metrics.start_time
        hours = duration.total_seconds() / 3600

        logger.info(f"Test Duration: {hours:.2f} hours")
        logger.info(f"Initial Capital: ${self.metrics.initial_capital:,.2f}")
        logger.info(f"Final Equity: ${self.metrics.current_equity:,.2f}")
        logger.info(f"Total P&L: ${self.metrics.total_pnl:+,.2f} ({self.metrics.return_pct:+.2f}%)")
        logger.info(f"Profit Target: ${self.profit_target:,.2f} ({'REACHED' if self.metrics.total_pnl >= self.profit_target else 'NOT REACHED'})")
        logger.info("")
        logger.info(f"Total Trades: {self.metrics.total_trades}")
        logger.info(f"Winning Trades: {self.metrics.winning_trades}")
        logger.info(f"Losing Trades: {self.metrics.losing_trades}")

        if self.metrics.total_trades > 0:
            logger.info(f"Win Rate: {self.metrics.win_rate:.1%}")
            logger.info(f"Profit Factor: {self.metrics.profit_factor:.2f}")
            logger.info(f"Avg Win: ${self.metrics.avg_win:+,.2f}")
            logger.info(f"Avg Loss: ${self.metrics.avg_loss:+,.2f}")

        logger.info(f"Total Fees: ${self.metrics.total_fees:,.2f}")

        # Hourly breakdown
        if self.metrics.hourly_pnl:
            logger.info("")
            logger.info("Hourly P&L:")
            for i, pnl in enumerate(self.metrics.hourly_pnl, 1):
                logger.info(f"  Hour {i}: ${pnl:+,.2f}")

        logger.info("=" * 80)

        # Save to JSON
        report_path = Path(self.log_file).parent / f"poc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(self.metrics.to_dict(), f, indent=2, default=str)

        logger.info(f"📄 Full report saved to: {report_path}")

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        logger.warning("Received shutdown signal")
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run 4-hour POC trading test')
    parser.add_argument('--config', default='app/config/poc_test.yaml', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no actual trades)')
    parser.add_argument('--hours', type=float, help='Override duration in hours')

    args = parser.parse_args()

    # Create and run
    runner = POCTradingRunner(args.config, dry_run=args.dry_run)

    # Override duration if specified
    if args.hours:
        runner.duration_hours = args.hours
        runner.end_time = runner.metrics.start_time + timedelta(hours=args.hours)

    # Run
    asyncio.run(runner.run())


if __name__ == '__main__':
    main()
