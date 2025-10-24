#!/usr/bin/env python3
"""
Kraken Futures L2 Order Book Imbalance Strategy - Integration Demo

Tests the complete system with Kraken Futures (US-accessible):
- Kraken Futures API (demo environment)
- L2ImbalanceStrategy (signal generation)
- RiskManager (risk controls)

Usage:
    # Dry run (monitor only)
    python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 60 --dry-run

    # Live demo trading
    python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 120 --live
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
from app.adapters.feed_binance_l2 import BinanceFuturesL2Feed  # Can reuse for any L2 feed
from app.adapters.broker_kraken import KrakenFuturesBroker
from app.strategies.alpha_l2_imbalance import L2ImbalanceStrategy, L2StrategyConfig
from app.engine.risk_manager import RiskManager
from app.engine.types import Signal


class KrakenL2IntegrationDemo:
    """
    Kraken Futures L2 integration demo.

    Tests Kraken Futures broker with L2 imbalance strategy.
    """

    def __init__(
        self,
        symbol: str,
        dry_run: bool = True,
        duration_seconds: int = 60
    ):
        """
        Initialize demo.

        Args:
            symbol: Kraken symbol (e.g., "PF_XBTUSD" for BTC perpetual)
            dry_run: If True, monitor only (no trades)
            duration_seconds: How long to run
        """
        self.symbol = symbol
        self.dry_run = dry_run
        self.duration_seconds = duration_seconds

        # Performance tracking
        self.latencies = []
        self.signal_count = 0
        self.trade_count = 0

        logger.info(
            f"Kraken L2 Demo initialized | "
            f"Symbol: {symbol} | "
            f"Mode: {'DRY-RUN' if dry_run else 'LIVE DEMO'} | "
            f"Duration: {duration_seconds}s"
        )

    async def run(self):
        """Run integration demo."""
        logger.info("="*80)
        logger.info("STARTING KRAKEN FUTURES L2 DEMO")
        logger.info("="*80)

        # Map Kraken symbol to Binance for L2 feed
        # Kraken: PF_XBTUSD -> Binance: BTCUSDT
        # (We'll use Binance L2 feed, Kraken broker)
        binance_symbol = self._map_kraken_to_binance_symbol(self.symbol)

        # Initialize L2 feed (using Binance for order book data)
        feed = BinanceFuturesL2Feed(
            symbol=binance_symbol,
            depth=5,
            update_interval_ms=100,
            testnet=True
        )

        config = L2StrategyConfig(
            buy_threshold=Decimal("3.0"),
            sell_threshold=Decimal("0.33"),
            depth=5,
            position_size_usd=Decimal("100"),  # Small size for demo
            cooldown_seconds=5
        )
        strategy = L2ImbalanceStrategy(
            symbol=self.symbol,  # Use Kraken symbol for strategy
            order_book=feed.order_book,
            config=config
        )

        risk_config = {
            "risk": {
                "max_daily_loss_usd": 50,
                "max_trades_per_day": 20,
                "max_position_usd": 100
            }
        }
        risk_manager = RiskManager(risk_config)

        # Initialize Kraken broker
        broker = None
        if not self.dry_run:
            try:
                broker = KrakenFuturesBroker(demo=True)
                logger.info("Connected to Kraken Futures DEMO")
            except Exception as e:
                logger.error(f"Failed to connect to Kraken: {e}")
                logger.warning("Falling back to DRY-RUN mode")
                self.dry_run = True

        # Fetch initial snapshot
        await feed._fetch_snapshot()
        logger.info(f"Order book snapshot loaded: {len(feed.order_book.bids)} bids, {len(feed.order_book.asks)} asks")

        # Connect WebSocket
        await feed._connect_websocket()
        logger.info("WebSocket connected")

        # Start processing messages
        feed.running = True
        message_task = asyncio.create_task(feed._process_ws_messages())

        # Main trading loop
        start_time = time.time()
        last_bar_time = time.time()
        bar_interval = 1.0

        try:
            while time.time() - start_time < self.duration_seconds:
                await asyncio.sleep(0.01)

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
            feed.running = False
            if feed.ws_connection:
                await feed.ws_connection.close()

        # Print summary
        self._print_summary(start_time)

    def _map_kraken_to_binance_symbol(self, kraken_symbol: str) -> str:
        """
        Map Kraken symbol to Binance symbol.

        Kraken: PF_XBTUSD (perpetual futures)
        Binance: BTCUSDT
        """
        mapping = {
            "PF_XBTUSD": "BTCUSDT",
            "PF_ETHUSD": "ETHUSDT",
            "PF_SOLUSD": "SOLUSDT",
            "PF_ADAUSD": "ADAUSDT"
        }

        binance_symbol = mapping.get(kraken_symbol)
        if not binance_symbol:
            # Default: strip PF_ prefix and replace USD with USDT
            binance_symbol = kraken_symbol.replace("PF_", "").replace("XBT", "BTC").replace("USD", "USDT")

        logger.info(f"Mapped {kraken_symbol} -> {binance_symbol} for L2 feed")
        return binance_symbol

    async def _process_bar(
        self,
        strategy: L2ImbalanceStrategy,
        risk_manager: RiskManager,
        broker: Optional[KrakenFuturesBroker],
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
        from app.engine.types import Bar
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

            logger.info(
                f"SIGNAL #{self.signal_count}: {signal.side.upper()} | "
                f"Price: {signal.price} | "
                f"Qty: {signal.qty:.4f} | "
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
                f"Signals: {self.signal_count} | "
                f"Latency: {latency_ms:.2f}ms"
            )

    async def _execute_trade(self, broker: KrakenFuturesBroker, signal: Signal):
        """Execute trade on Kraken."""
        if signal.side == "buy":
            order_id = broker.buy(
                symbol=signal.symbol,
                qty=signal.qty,
                sl=signal.sl,
                tp=signal.tp
            )
            logger.success(f"BUY executed | Order ID: {order_id}")

        elif signal.side == "sell":
            order_id = broker.sell(
                symbol=signal.symbol,
                qty=signal.qty,
                sl=signal.sl,
                tp=signal.tp
            )
            logger.success(f"SELL executed | Order ID: {order_id}")

        elif signal.side == "close":
            broker.close_all(symbol=signal.symbol)
            logger.success(f"Position CLOSED")

    def _print_summary(self, start_time: float):
        """Print execution summary."""
        elapsed = time.time() - start_time

        logger.info("="*80)
        logger.info("KRAKEN DEMO COMPLETE")
        logger.info("="*80)

        logger.info(f"Duration: {elapsed:.1f}s")
        logger.info(f"Signals Generated: {self.signal_count}")
        logger.info(f"Trades Executed: {self.trade_count} ({'DRY-RUN' if self.dry_run else 'LIVE'})")

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


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Kraken Futures L2 Demo')
    parser.add_argument('--symbol', type=str, default='PF_XBTUSD',
                       help='Kraken symbol (default: PF_XBTUSD)')
    parser.add_argument('--duration', type=int, default=60,
                       help='Duration in seconds (default: 60)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no trades)')
    parser.add_argument('--live', action='store_true',
                       help='Live demo trading mode')

    args = parser.parse_args()

    dry_run = not args.live if args.live else True

    demo = KrakenL2IntegrationDemo(
        symbol=args.symbol,
        dry_run=dry_run,
        duration_seconds=args.duration
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
