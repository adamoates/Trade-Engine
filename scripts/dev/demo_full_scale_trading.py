#!/usr/bin/env python3
"""
Full-scale trading demo: Web3 signals + L2 order book + Trade execution.

This simulates a complete trading session over 1 hour, fetching real Web3 data,
simulating L2 order book imbalance, and making trading decisions.

Usage:
    python tools/demo_full_scale_trading.py

    # Quick mode (10 iterations, ~2 minutes)
    python tools/demo_full_scale_trading.py --quick

    # Full simulation (60 iterations, ~10 minutes)
    python tools/demo_full_scale_trading.py --full
"""

import asyncio
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from loguru import logger
import argparse

from trade_engine.services.data.web3_signals import Web3DataSource, Web3Signal
from trade_engine.services.data.signal_normalizer import SignalNormalizer

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


@dataclass
class L2OrderBook:
    """Simulated Level 2 order book."""
    symbol: str
    bids: List[Tuple[float, float]]  # [(price, quantity), ...]
    asks: List[Tuple[float, float]]  # [(price, quantity), ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_imbalance_ratio(self, depth: int = 5) -> float:
        """
        Calculate bid/ask volume ratio (L2 imbalance signal).

        Returns:
            Ratio > 3.0 = strong buying pressure (BUY signal)
            Ratio < 0.33 = strong selling pressure (SELL signal)
            Ratio ≈ 1.0 = balanced (NEUTRAL)
        """
        top_bids = self.bids[:depth]
        top_asks = self.asks[:depth]

        bid_volume = sum(qty for _, qty in top_bids)
        ask_volume = sum(qty for _, qty in top_asks)

        if ask_volume == 0:
            return float('inf') if bid_volume > 0 else 1.0

        return bid_volume / ask_volume


@dataclass
class Trade:
    """Executed trade."""
    timestamp: datetime
    symbol: str
    side: str  # "BUY" or "SELL"
    size: float
    entry_price: float
    l2_signal: str
    l2_imbalance: float
    web3_signal: str
    web3_score: float
    web3_confidence: float
    combined_conviction: float
    exit_price: float = 0.0
    pnl: float = 0.0
    exit_reason: str = ""


@dataclass
class TradingSession:
    """Trading session state."""
    capital: float = 10000.0
    position: float = 0.0  # Current position size (BTC)
    trades: List[Trade] = field(default_factory=list)
    pnl_history: List[float] = field(default_factory=list)

    def get_equity(self) -> float:
        """Get current equity."""
        return self.capital + sum(t.pnl for t in self.trades)

    def get_win_rate(self) -> float:
        """Calculate win rate."""
        if not self.trades:
            return 0.0
        winners = sum(1 for t in self.trades if t.pnl > 0)
        return winners / len(self.trades)

    def get_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (annualized)."""
        if len(self.pnl_history) < 2:
            return 0.0

        import numpy as np
        returns = np.array(self.pnl_history)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualize (assuming hourly returns)
        sharpe = (mean_return / std_return) * np.sqrt(252 * 24)
        return sharpe


class L2OrderBookSimulator:
    """Simulate realistic L2 order book with varying imbalance."""

    def __init__(self, symbol: str = "BTCUSDT", base_price: float = 45000.0):
        self.symbol = symbol
        self.base_price = base_price
        self.time_step = 0

    def generate_order_book(self) -> L2OrderBook:
        """
        Generate realistic L2 order book with time-varying imbalance.

        Simulates market microstructure:
        - Normal: Balanced bid/ask (ratio ≈ 1.0)
        - Buying pressure: More bids than asks (ratio > 3.0)
        - Selling pressure: More asks than bids (ratio < 0.33)
        """
        import numpy as np

        # Simulate market regime (changes over time)
        self.time_step += 1
        regime_cycle = np.sin(self.time_step * 0.2)  # Slow oscillation
        noise = np.random.randn() * 0.5

        # Imbalance factor (-1 to +1)
        imbalance_factor = regime_cycle + noise
        imbalance_factor = np.clip(imbalance_factor, -1.0, 1.0)

        # Generate bid side (buying pressure)
        bid_multiplier = 1.0 + max(0, imbalance_factor)  # 1.0 to 2.0
        bids = []
        for i in range(10):
            price = self.base_price - (i + 1) * 10
            quantity = np.random.uniform(0.5, 2.0) * bid_multiplier
            bids.append((price, quantity))

        # Generate ask side (selling pressure)
        ask_multiplier = 1.0 + max(0, -imbalance_factor)  # 1.0 to 2.0
        asks = []
        for i in range(10):
            price = self.base_price + (i + 1) * 10
            quantity = np.random.uniform(0.5, 2.0) * ask_multiplier
            asks.append((price, quantity))

        return L2OrderBook(
            symbol=self.symbol,
            bids=bids,
            asks=asks
        )


class TradingEngine:
    """Combines Web3 + L2 signals and executes trades."""

    def __init__(
        self,
        web3_source: Web3DataSource,
        l2_simulator: L2OrderBookSimulator,
        session: TradingSession
    ):
        self.web3_source = web3_source
        self.l2_simulator = l2_simulator
        self.session = session
        self.l2_normalizer = SignalNormalizer(method="zscore")

    def calculate_l2_signal(self, order_book: L2OrderBook) -> Tuple[str, float]:
        """
        Calculate L2 order book signal.

        Returns:
            (signal, imbalance_ratio)
        """
        ratio = order_book.get_imbalance_ratio(depth=5)

        # Normalize L2 imbalance (builds history over time)
        normalized_l2 = self.l2_normalizer.normalize(ratio, "l2_imbalance")

        if normalized_l2 > 0.5:
            return "BUY", ratio
        elif normalized_l2 < -0.5:
            return "SELL", ratio
        else:
            return "NEUTRAL", ratio

    def combine_signals(
        self,
        l2_signal: str,
        l2_imbalance: float,
        web3_signal: Web3Signal
    ) -> Tuple[str, float]:
        """
        Combine L2 + Web3 signals with confidence scoring.

        Returns:
            (final_signal, conviction)

        Conviction scale:
        - 0.0-0.3: Low conviction (skip trade)
        - 0.3-0.7: Medium conviction (half size)
        - 0.7-1.0: High conviction (full size)
        """
        # Both signals must agree
        if l2_signal != web3_signal.signal:
            return "NEUTRAL", 0.0

        # Calculate conviction based on:
        # 1. Web3 confidence (data availability)
        # 2. Web3 score magnitude
        # 3. L2 imbalance strength

        web3_strength = abs(web3_signal.score) / 3.0  # Normalize to 0-1
        l2_strength = abs(self.l2_normalizer.normalize(l2_imbalance, "l2_imbalance"))

        conviction = (
            web3_signal.confidence * 0.4 +  # 40% weight on data availability
            web3_strength * 0.3 +            # 30% weight on Web3 score
            l2_strength * 0.3                # 30% weight on L2 imbalance
        )

        return l2_signal, conviction

    def calculate_position_size(self, conviction: float) -> float:
        """
        Calculate position size based on conviction.

        Kelly Criterion-inspired sizing:
        - High conviction: 10% of capital
        - Medium conviction: 5% of capital
        - Low conviction: 2% of capital
        """
        max_position_pct = 0.10  # 10% max

        if conviction > 0.7:
            size_pct = max_position_pct
        elif conviction > 0.3:
            size_pct = max_position_pct * 0.5
        else:
            size_pct = max_position_pct * 0.2

        # Convert to BTC
        btc_price = self.l2_simulator.base_price
        size_btc = (self.session.get_equity() * size_pct) / btc_price

        return size_btc

    def execute_trade(
        self,
        signal: str,
        conviction: float,
        order_book: L2OrderBook,
        web3_signal: Web3Signal,
        l2_imbalance: float
    ) -> bool:
        """
        Execute trade if conviction threshold met.

        Returns:
            True if trade executed, False otherwise
        """
        if conviction < 0.3:
            logger.debug(f"Skipping trade - low conviction: {conviction:.2f}")
            return False

        if signal == "NEUTRAL":
            return False

        # Calculate position size
        size = self.calculate_position_size(conviction)

        # Entry price (use best bid/ask)
        if signal == "BUY":
            entry_price = order_book.asks[0][0]  # Best ask
        else:
            entry_price = order_book.bids[0][0]  # Best bid

        # Create trade
        trade = Trade(
            timestamp=datetime.now(timezone.utc),
            symbol=order_book.symbol,
            side=signal,
            size=size,
            entry_price=entry_price,
            l2_signal=signal,
            l2_imbalance=l2_imbalance,
            web3_signal=web3_signal.signal,
            web3_score=web3_signal.score,
            web3_confidence=web3_signal.confidence,
            combined_conviction=conviction
        )

        # Simulate exit (for demo purposes - instant exit with noise)
        import numpy as np
        price_change_pct = np.random.normal(0.001, 0.002)  # ±0.1-0.2%

        if signal == "BUY":
            trade.exit_price = entry_price * (1 + price_change_pct)
            trade.pnl = (trade.exit_price - trade.entry_price) * trade.size
        else:
            trade.exit_price = entry_price * (1 - price_change_pct)
            trade.pnl = (trade.entry_price - trade.exit_price) * trade.size

        trade.exit_reason = "demo_instant_exit"

        # Record trade
        self.session.trades.append(trade)
        self.session.pnl_history.append(trade.pnl)

        logger.info(
            f"Trade #{len(self.session.trades)}: {signal} {size:.4f} BTC @ ${entry_price:,.0f} | "
            f"Conviction: {conviction:.2f} | PnL: ${trade.pnl:+.2f}"
        )

        return True

    async def run_trading_cycle(self) -> Dict:
        """
        Run one trading cycle:
        1. Fetch Web3 signals
        2. Generate L2 order book
        3. Combine signals
        4. Execute trade if applicable

        Returns:
            Cycle statistics
        """
        # 1. Fetch Web3 signals
        web3_signal = self.web3_source.get_combined_signal()

        # 2. Generate L2 order book
        order_book = self.l2_simulator.generate_order_book()

        # 3. Calculate L2 signal
        l2_signal, l2_imbalance = self.calculate_l2_signal(order_book)

        # 4. Combine signals
        final_signal, conviction = self.combine_signals(
            l2_signal,
            l2_imbalance,
            web3_signal
        )

        # 5. Execute trade if applicable
        traded = self.execute_trade(
            final_signal,
            conviction,
            order_book,
            web3_signal,
            l2_imbalance
        )

        return {
            "web3_signal": web3_signal.signal,
            "web3_score": web3_signal.score,
            "web3_confidence": web3_signal.confidence,
            "l2_signal": l2_signal,
            "l2_imbalance": l2_imbalance,
            "final_signal": final_signal,
            "conviction": conviction,
            "traded": traded
        }


async def run_full_scale_demo(iterations: int = 60, delay_seconds: int = 10):
    """
    Run full-scale trading demo.

    Args:
        iterations: Number of trading cycles (default: 60 for 1 hour)
        delay_seconds: Delay between cycles (default: 10 seconds)
    """
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 20 + "FULL-SCALE TRADING DEMO" + " " * 35 + "║")
    logger.info("║" + " " * 15 + "Web3 Signals + L2 Order Book + Trade Execution" + " " * 16 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")

    # Initialize components
    logger.info("🔧 Initializing trading components...")

    web3_source = Web3DataSource(
        normalize=True,
        normalization_method="zscore",
        timeout=10
    )

    l2_simulator = L2OrderBookSimulator(
        symbol="BTCUSDT",
        base_price=45000.0
    )

    session = TradingSession(capital=10000.0)

    engine = TradingEngine(
        web3_source=web3_source,
        l2_simulator=l2_simulator,
        session=session
    )

    logger.success("✓ Trading engine initialized")
    logger.info(f"  Starting capital: ${session.capital:,.2f}")
    logger.info(f"  Trading cycles: {iterations}")
    logger.info(f"  Cycle interval: {delay_seconds}s")
    logger.info("")

    # Run trading cycles
    logger.info("=" * 80)
    logger.info("STARTING TRADING SESSION")
    logger.info("=" * 80)
    logger.info("")

    start_time = time.time()

    for i in range(1, iterations + 1):
        logger.info(f"Cycle {i}/{iterations}")

        try:
            stats = await engine.run_trading_cycle()

            # Log cycle summary
            logger.debug(
                f"  L2: {stats['l2_signal']:8s} (imbalance: {stats['l2_imbalance']:.2f}) | "
                f"Web3: {stats['web3_signal']:8s} (score: {stats['web3_score']:+.2f}, conf: {stats['web3_confidence']:.0%}) | "
                f"Final: {stats['final_signal']:8s} (conviction: {stats['conviction']:.2f})"
            )

            # Progress update every 10 cycles
            if i % 10 == 0:
                equity = session.get_equity()
                win_rate = session.get_win_rate()
                total_pnl = sum(t.pnl for t in session.trades)

                logger.info("")
                logger.info(f"📊 Progress Update (Cycle {i}/{iterations})")
                logger.info(f"  Trades executed: {len(session.trades)}")
                logger.info(f"  Win rate: {win_rate:.1%}")
                logger.info(f"  Total P&L: ${total_pnl:+.2f}")
                logger.info(f"  Current equity: ${equity:,.2f}")
                logger.info("")

        except Exception as e:
            logger.error(f"Cycle {i} failed: {e}")

        # Delay between cycles (except last one)
        if i < iterations:
            await asyncio.sleep(delay_seconds)

    elapsed_time = time.time() - start_time

    # Final statistics
    logger.info("")
    logger.info("=" * 80)
    logger.info("TRADING SESSION COMPLETE")
    logger.info("=" * 80)
    logger.info("")

    equity = session.get_equity()
    win_rate = session.get_win_rate()
    total_pnl = sum(t.pnl for t in session.trades)
    sharpe = session.get_sharpe_ratio()

    winners = sum(1 for t in session.trades if t.pnl > 0)
    losers = len(session.trades) - winners

    avg_win = sum(t.pnl for t in session.trades if t.pnl > 0) / winners if winners > 0 else 0
    avg_loss = sum(t.pnl for t in session.trades if t.pnl < 0) / losers if losers > 0 else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    logger.info("📈 Performance Summary:")
    logger.info("")
    logger.info(f"  Starting capital:  ${session.capital:,.2f}")
    logger.info(f"  Ending equity:     ${equity:,.2f}")
    logger.info(f"  Total P&L:         ${total_pnl:+,.2f} ({(total_pnl/session.capital)*100:+.2f}%)")
    logger.info("")
    logger.info(f"  Trades executed:   {len(session.trades)}")
    logger.info(f"  Winners:           {winners}")
    logger.info(f"  Losers:            {losers}")
    logger.info(f"  Win rate:          {win_rate:.1%}")
    logger.info("")
    logger.info(f"  Avg win:           ${avg_win:+.2f}")
    logger.info(f"  Avg loss:          ${avg_loss:+.2f}")
    logger.info(f"  Profit factor:     {profit_factor:.2f}")
    logger.info(f"  Sharpe ratio:      {sharpe:.2f}")
    logger.info("")
    logger.info(f"  Session duration:  {elapsed_time:.1f}s ({elapsed_time/60:.1f} min)")
    logger.info("")

    # Verdict
    if total_pnl > 0 and win_rate > 0.5:
        logger.success("✓ PROFITABLE SESSION - System working as expected")
    elif total_pnl > 0:
        logger.info("⚪ POSITIVE P&L but low win rate - Needs optimization")
    else:
        logger.warning("⚠️  NEGATIVE P&L - Review signal combination logic")

    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Review individual trades for patterns")
    logger.info("  2. Adjust conviction thresholds (currently 0.3)")
    logger.info("  3. Fine-tune L2 normalization depth (currently 5 levels)")
    logger.info("  4. Run longer simulation (1000+ cycles) for statistical significance")
    logger.info("  5. Backtest on historical data with validate_clean_ohlcv.py")
    logger.info("")


def main():
    """Parse arguments and run demo."""
    parser = argparse.ArgumentParser(description="Full-scale trading demo")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 10 iterations, 2-second delay (~30 seconds total)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full mode: 60 iterations, 10-second delay (~10 minutes total)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        help="Custom number of iterations"
    )
    parser.add_argument(
        "--delay",
        type=int,
        help="Custom delay between cycles (seconds)"
    )

    args = parser.parse_args()

    # Determine mode
    if args.quick:
        iterations = 10
        delay = 2
    elif args.full:
        iterations = 60
        delay = 10
    elif args.iterations or args.delay:
        iterations = args.iterations or 30
        delay = args.delay or 5
    else:
        # Default: Medium mode
        iterations = 30
        delay = 5

    # Run demo
    try:
        asyncio.run(run_full_scale_demo(
            iterations=iterations,
            delay_seconds=delay
        ))
    except KeyboardInterrupt:
        logger.warning("\n\nDemo interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
