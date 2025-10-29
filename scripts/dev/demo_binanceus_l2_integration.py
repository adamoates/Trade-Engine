#!/usr/bin/env python3
"""
Binance.us Spot L2 Order Book Imbalance Strategy - Integration Demo

Tests the complete system with Binance.us Spot (US-only, long-only):
- Binance.us Spot API (NO TESTNET - USES REAL MONEY!)
- Binance.us REST L2 feed (actual Binance.US order book data)
- L2ImbalanceStrategy (spot-only mode, long positions only)
- RiskManager (risk controls)

⚠️  DATA SOURCE: Uses actual Binance.US order book via REST API
    - Higher latency than WebSocket (100-500ms vs 10-50ms)
    - Matches actual execution venue (Binance.US)
    - No testnet available

⚠️  WARNING: Binance.us does NOT have a testnet. Live mode uses REAL MONEY.
    Always start with --dry-run mode to test before risking capital.

⚠️  SPOT-ONLY MODE: This strategy can only take LONG positions.
    Short signals are ignored. ~50% fewer signals than futures mode.

Usage:
    # Dry run (monitor only, NO TRADES) - RECOMMENDED
    python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

    # Live trading (USES REAL MONEY!) - Requires explicit confirmation
    python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 120 --live --i-understand-this-is-real-money
"""

import asyncio
import time
import sys
from pathlib import Path
from decimal import Decimal
from typing import Optional
import argparse

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from trade_engine.adapters.feeds.binance_us_l2 import BinanceUSL2Feed
from trade_engine.adapters.brokers.binance_us import BinanceUSSpotBroker
from trade_engine.domain.strategies.alpha_l2_imbalance import L2ImbalanceStrategy, L2StrategyConfig
from trade_engine.core.risk_manager import RiskManager
from trade_engine.core.types import Signal


class BinanceUSL2IntegrationDemo:
    """
    Binance.us Spot L2 integration demo.

    Tests Binance.us spot broker with L2 imbalance strategy (long-only).
    """

    def __init__(
        self,
        symbol: str,
        dry_run: bool = True,
        duration_seconds: int = 60,
        confirmed: bool = False
    ):
        """
        Initialize demo.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            dry_run: If True, monitor only (no trades)
            duration_seconds: How long to run
            confirmed: User confirmed they understand this is real money
        """
        self.symbol = symbol
        self.dry_run = dry_run
        self.duration_seconds = duration_seconds

        # Performance tracking
        self.latencies = []
        self.signal_count = 0
        self.long_signals_count = 0
        self.short_signals_ignored = 0
        self.trade_count = 0

        # Safety check for live mode
        if not dry_run and not confirmed:
            logger.error("="*80)
            logger.error("LIVE MODE REQUIRES EXPLICIT CONFIRMATION")
            logger.error("="*80)
            logger.error("Binance.us does NOT have a testnet - this uses REAL MONEY!")
            logger.error("Add --i-understand-this-is-real-money flag to proceed.")
            logger.error("="*80)
            sys.exit(1)

        logger.info(
            f"Binance.us L2 Demo initialized | "
            f"Symbol: {symbol} | "
            f"Mode: {'DRY-RUN' if dry_run else '⚠️  LIVE (REAL MONEY)'} | "
            f"Duration: {duration_seconds}s | "
            f"Strategy: SPOT-ONLY (LONG ONLY)"
        )

        if not dry_run:
            logger.warning("="*80)
            logger.warning("⚠️  LIVE TRADING MODE - USING REAL MONEY")
            logger.warning("="*80)

    async def run(self):
        """Run integration demo."""
        logger.info("="*80)
        logger.info("STARTING BINANCE.US SPOT L2 DEMO")
        logger.info("="*80)

        # Initialize L2 feed (using Binance.US REST API for actual market data)
        feed = BinanceUSL2Feed(
            symbol=self.symbol,
            depth=5,
            poll_interval_ms=500  # 500ms polling (vs 100ms WebSocket)
        )

        # Strategy config - SPOT-ONLY MODE
        config = L2StrategyConfig(
            spot_only=True,  # 🔑 KEY: Disables short signals
            buy_threshold=Decimal("3.0"),
            sell_threshold=Decimal("0.33"),  # Not used in spot-only mode
            depth=5,
            position_size_usd=Decimal("50"),  # Very conservative for demo
            cooldown_seconds=5
        )
        strategy = L2ImbalanceStrategy(
            symbol=self.symbol,
            order_book=feed.order_book,
            config=config
        )

        # Risk manager - VERY conservative limits
        risk_config = {
            "risk": {
                "max_daily_loss_usd": 25,  # Very low limit for safety
                "max_trades_per_day": 10,
                "max_position_usd": 50  # Match position size
            }
        }
        risk_manager = RiskManager(risk_config)

        # Initialize Binance.us broker
        broker = None
        if not self.dry_run:
            try:
                broker = BinanceUSSpotBroker()
                balance = broker.balance()
                logger.info(f"Connected to Binance.us LIVE (REAL MONEY)")
                logger.info(f"Account Balance: ${balance} USDT")

                if balance < Decimal("100"):
                    logger.warning(f"⚠️  Low account balance: ${balance} USDT")
                    logger.warning("Recommended minimum: $100 USDT")

            except Exception as e:
                logger.error(f"Failed to connect to Binance.us: {e}")
                logger.warning("Falling back to DRY-RUN mode")
                self.dry_run = True

        # Start REST polling in background
        feed_task = asyncio.create_task(feed.start())

        # Wait for first order book snapshot
        logger.info("Waiting for initial order book snapshot...")
        for _ in range(10):
            if feed.last_update_time > 0:
                break
            await asyncio.sleep(0.5)

        if feed.last_update_time == 0:
            logger.error("Failed to fetch initial order book snapshot")
            feed.stop()
            return

        logger.info(f"Order book loaded: {len(feed.order_book.bids)} bids, {len(feed.order_book.asks)} asks")
        logger.info(f"Polling every {feed.poll_interval_ms}ms from Binance.US")

        # Main trading loop
        start_time = time.time()
        last_bar_time = time.time()
        bar_interval = 1.0

        try:
            while time.time() - start_time < self.duration_seconds:
                await asyncio.sleep(0.1)

                now = time.time()
                if now - last_bar_time >= bar_interval:
                    await self._process_bar(
                        strategy=strategy,
                        risk_manager=risk_manager,
                        broker=broker,
                        order_book=feed.order_book
                    )
                    last_bar_time = now

        except KeyboardInterrupt:
            logger.info("Demo stopped by user")
        finally:
            feed.stop()
            await feed_task

        # Print summary
        self._print_summary(start_time)

    async def _process_bar(
        self,
        strategy: L2ImbalanceStrategy,
        risk_manager: RiskManager,
        broker: Optional[BinanceUSSpotBroker],
        order_book
    ):
        """Process one bar through the system."""
        start_time = time.time()

        if not order_book.is_valid():
            return

        mid_price = order_book.get_mid_price()
        if not mid_price:
            return

        # Create bar
        from trade_engine.core.types import Bar
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
            self.signal_count += 1

            # Track signal types
            if signal.side == "buy":
                self.long_signals_count += 1
            # Note: Short signals are ignored in spot-only mode, won't appear here

            logger.info(
                f"SIGNAL #{self.signal_count}: {signal.side.upper()} | "
                f"Price: {signal.price} | "
                f"Qty: {signal.qty:.6f} | "
                f"Reason: {signal.reason}"
            )

            # Risk check
            positions = broker.positions() if broker else {}
            risk_result = risk_manager.check_all(signal, positions)

            if not risk_result.passed:
                logger.warning(f"Risk check FAILED: {risk_result.reason}")
                continue

            # Execute trade
            if not self.dry_run and broker:
                try:
                    await self._execute_trade(broker, signal)
                    self.trade_count += 1
                    risk_manager.record_trade()
                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
            else:
                logger.info(f"DRY-RUN: Would execute {signal.side} order")

        # Track latency
        latency_ms = (time.time() - start_time) * 1000
        self.latencies.append(latency_ms)

        # Log state every 10 seconds
        if int(time.time()) % 10 == 0:
            imbalance = order_book.calculate_imbalance(strategy.config.depth)
            spread_bps = order_book.get_spread_bps()
            spread_str = f"{spread_bps:.2f}" if spread_bps else "0.00"

            logger.info(
                f"STATE | "
                f"Imbalance: {imbalance:.3f} | "
                f"Mid: {mid_price} | "
                f"Spread: {spread_str} bps | "
                f"Signals: {self.signal_count} (Long: {self.long_signals_count}) | "
                f"Latency: {latency_ms:.2f}ms"
            )

    async def _execute_trade(self, broker: BinanceUSSpotBroker, signal: Signal):
        """Execute trade on Binance.us (spot only, long-only)."""
        if signal.side == "buy":
            # Open long position
            order_id = broker.buy(
                symbol=signal.symbol,
                qty=signal.qty
                # Note: SL/TP not yet implemented for spot (requires OCO orders)
            )
            logger.success(f"BUY executed | Order ID: {order_id} | ⚠️  REAL MONEY")

        elif signal.side == "close":
            # Close long position (sell holdings)
            broker.close_all(symbol=signal.symbol)
            logger.success(f"Position CLOSED | ⚠️  REAL MONEY")

        # Note: "sell" for short entry won't appear in spot-only mode

    def _print_summary(self, start_time: float):
        """Print execution summary."""
        elapsed = time.time() - start_time

        logger.info("="*80)
        logger.info("BINANCE.US DEMO COMPLETE")
        logger.info("="*80)

        logger.info(f"Duration: {elapsed:.1f}s")
        logger.info(f"Signals Generated: {self.signal_count}")
        logger.info(f"  - Long signals: {self.long_signals_count}")
        logger.info(f"  - Short signals: 0 (ignored in spot-only mode)")
        logger.info(f"Trades Executed: {self.trade_count} ({'DRY-RUN' if self.dry_run else '⚠️  LIVE (REAL MONEY)'})")

        if self.latencies:
            avg_latency = sum(self.latencies) / len(self.latencies)
            max_latency = max(self.latencies)
            p95_latency = sorted(self.latencies)[int(len(self.latencies) * 0.95)]

            logger.info(f"Performance:")
            logger.info(f"  Avg Latency: {avg_latency:.2f}ms")
            logger.info(f"  P95 Latency: {p95_latency:.2f}ms")
            logger.info(f"  Max Latency: {max_latency:.2f}ms")

            if avg_latency < 50:
                logger.success(f"✓ Latency target MET (<50ms)")
            else:
                logger.warning(f"✗ Latency target MISSED (avg {avg_latency:.2f}ms > 50ms)")

        logger.info("="*80)
        logger.info("SPOT-ONLY MODE NOTES:")
        logger.info("  - Only LONG positions were taken")
        logger.info("  - Short signals are ignored (~50% signal reduction)")
        logger.info("  - For full strategy, use Kraken Futures (US-accessible)")
        logger.info("="*80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Binance.us Spot L2 Demo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  WARNING: Binance.us does NOT have a testnet.
   Live mode uses REAL MONEY. Always test with --dry-run first.

SPOT-ONLY MODE:
  - Can only take LONG positions (no shorting)
  - Short signals are ignored (~50% fewer signals)
  - For full L2 strategy, use Kraken Futures (US-accessible)

Examples:
  # Dry run (recommended, no trades)
  python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

  # Live trading (REAL MONEY - requires confirmation)
  python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 120 --live --i-understand-this-is-real-money
        """
    )
    parser.add_argument('--symbol', type=str, default='BTCUSDT',
                       help='Trading pair (default: BTCUSDT)')
    parser.add_argument('--duration', type=int, default=60,
                       help='Duration in seconds (default: 60)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no trades, monitor only)')
    parser.add_argument('--live', action='store_true',
                       help='⚠️  Live trading mode (USES REAL MONEY!)')
    parser.add_argument('--i-understand-this-is-real-money', action='store_true',
                       help='Required confirmation for live mode')

    args = parser.parse_args()

    # Default to dry-run unless explicitly set to live
    dry_run = not args.live

    # Safety check
    if args.live and not args.i_understand_this_is_real_money:
        logger.error("="*80)
        logger.error("LIVE MODE REQUIRES EXPLICIT CONFIRMATION")
        logger.error("="*80)
        logger.error("⚠️  Binance.us does NOT have a testnet - this uses REAL MONEY!")
        logger.error("Add --i-understand-this-is-real-money flag to proceed.")
        logger.error("")
        logger.error("Example:")
        logger.error("  python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --live --i-understand-this-is-real-money")
        logger.error("="*80)
        sys.exit(1)

    demo = BinanceUSL2IntegrationDemo(
        symbol=args.symbol,
        dry_run=dry_run,
        duration_seconds=args.duration,
        confirmed=args.i_understand_this_is_real_money
    )

    try:
        await demo.run()
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    asyncio.run(main())
