#!/usr/bin/env python3
"""
Full-scale SIMULATED trading demo (no real APIs needed).

This demonstrates the complete system with mocked Web3 data,
so it works even when APIs are down. Perfect for testing and demos.

Usage:
    python tools/demo_full_scale_simulated.py --quick
"""

import sys
import argparse
from tools.demo_full_scale_trading import (
    TradingEngine,
    TradingSession,
    L2OrderBookSimulator,
    logger,
    asyncio,
    time,
    datetime,
    timezone
)
from trade_engine.services.data.web3_signals import Web3DataSource, Web3Signal, GasData, LiquidityData, FundingRateData
from unittest.mock import Mock
import numpy as np


class SimulatedWeb3DataSource(Web3DataSource):
    """Web3 data source with simulated realistic data."""

    def __init__(self, **kwargs):
        super().__init__(normalize=True, **kwargs)
        self.cycle = 0

    def get_gas_prices(self):
        """Generate realistic gas price data."""
        self.cycle += 1

        # Simulate gas price with trend + noise
        base = 30
        trend = 10 * np.sin(self.cycle * 0.1)  # Oscillating trend
        noise = np.random.normal(0, 5)
        gas_price = max(15, base + trend + noise)

        return GasData(
            safe_gas_price=gas_price * 0.8,
            propose_gas_price=gas_price,
            fast_gas_price=gas_price * 1.2,
            timestamp=datetime.now(timezone.utc)
        )

    def get_dex_liquidity(self, pool: str = "WBTC/USDC"):
        """Generate realistic DEX liquidity data."""
        # Simulate volume with trend + noise
        base_volume = 5_000_000
        trend = 2_000_000 * np.sin(self.cycle * 0.15)
        noise = np.random.normal(0, 500_000)
        volume = max(100_000, base_volume + trend + noise)

        return LiquidityData(
            pool_address="0x...",
            token0="WBTC",
            token1="USDC",
            liquidity=volume * 20,  # TVL is ~20x daily volume
            volume_24h_usd=volume,
            timestamp=datetime.now(timezone.utc)
        )

    def get_funding_rate(self, symbol: str = "BTC-USD"):
        """Generate realistic funding rate data."""
        # Simulate funding rate (mostly small, occasional extremes)
        if np.random.random() < 0.1:  # 10% chance of extreme
            rate = np.random.choice([-0.02, 0.02])
        else:
            rate = np.random.normal(0.0, 0.005)

        return FundingRateData(
            symbol=symbol,
            funding_rate=rate,
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        )


async def run_simulated_demo(iterations: int = 30, delay_seconds: int = 1):
    """Run full-scale simulated trading demo."""
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 18 + "FULL-SCALE SIMULATED DEMO" + " " * 33 + "║")
    logger.info("║" + " " * 12 + "Mocked Web3 + L2 Order Book + Trade Execution" + " " * 19 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")

    # Initialize components
    logger.info("🔧 Initializing trading components...")

    web3_source = SimulatedWeb3DataSource(timeout=1, retry_attempts=1)
    l2_simulator = L2OrderBookSimulator(symbol="BTCUSDT", base_price=45000.0)
    session = TradingSession(capital=10000.0)

    engine = TradingEngine(
        web3_source=web3_source,
        l2_simulator=l2_simulator,
        session=session
    )

    logger.success("✓ Trading engine initialized (SIMULATED mode)")
    logger.info(f"  Starting capital: ${session.capital:,.2f}")
    logger.info(f"  Trading cycles: {iterations}")
    logger.info(f"  Cycle interval: {delay_seconds}s")
    logger.info(f"  Mode: SIMULATED (no real API calls)")
    logger.info("")

    # Run trading cycles
    logger.info("=" * 80)
    logger.info("STARTING TRADING SESSION")
    logger.info("=" * 80)
    logger.info("")

    start_time = time.time()
    trades_by_signal = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}

    for i in range(1, iterations + 1):
        logger.info(f"Cycle {i}/{iterations}")

        try:
            stats = await engine.run_trading_cycle()
            trades_by_signal[stats['final_signal']] += 1

            # Log cycle summary (always, since simulated is fast)
            if stats['traded']:
                logger.success(
                    f"  ✓ TRADE EXECUTED | "
                    f"L2: {stats['l2_signal']:8s} ({stats['l2_imbalance']:.2f}) | "
                    f"Web3: {stats['web3_signal']:8s} (score: {stats['web3_score']:+.2f}) | "
                    f"Conviction: {stats['conviction']:.2f}"
                )
            else:
                logger.debug(
                    f"  L2: {stats['l2_signal']:8s} (imb: {stats['l2_imbalance']:.2f}) | "
                    f"Web3: {stats['web3_signal']:8s} (score: {stats['web3_score']:+.2f}, conf: {stats['web3_confidence']:.0%}) | "
                    f"Conviction: {stats['conviction']:.2f} [skipped]"
                )

            # Progress update every 10 cycles
            if i % 10 == 0 and i < iterations:
                equity = session.get_equity()
                win_rate = session.get_win_rate()
                total_pnl = sum(t.pnl for t in session.trades)

                logger.info("")
                logger.info(f"📊 Progress (Cycle {i}/{iterations})")
                logger.info(f"  Trades: {len(session.trades)} | Win rate: {win_rate:.1%} | P&L: ${total_pnl:+.2f} | Equity: ${equity:,.2f}")
                logger.info("")

        except Exception as e:
            logger.error(f"Cycle {i} failed: {e}")
            import traceback
            traceback.print_exc()

        # Delay between cycles
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
    logger.info(f"  Cycles run:        {iterations}")
    logger.info(f"  Trades executed:   {len(session.trades)} ({len(session.trades)/iterations*100:.1f}% of cycles)")
    logger.info(f"  BUY trades:        {sum(1 for t in session.trades if t.side == 'BUY')}")
    logger.info(f"  SELL trades:       {sum(1 for t in session.trades if t.side == 'SELL')}")
    logger.info(f"  Winners:           {winners}")
    logger.info(f"  Losers:            {losers}")
    logger.info(f"  Win rate:          {win_rate:.1%}")
    logger.info("")
    logger.info(f"  Avg win:           ${avg_win:+.2f}")
    logger.info(f"  Avg loss:          ${avg_loss:+.2f}")
    logger.info(f"  Profit factor:     {profit_factor:.2f}")
    logger.info(f"  Sharpe ratio:      {sharpe:.2f}")
    logger.info("")
    logger.info(f"  Session duration:  {elapsed_time:.1f}s")
    logger.info("")

    # Signal distribution
    logger.info("📊 Signal Distribution:")
    logger.info(f"  BUY signals:       {trades_by_signal['BUY']} ({trades_by_signal['BUY']/iterations*100:.1f}%)")
    logger.info(f"  SELL signals:      {trades_by_signal['SELL']} ({trades_by_signal['SELL']/iterations*100:.1f}%)")
    logger.info(f"  NEUTRAL signals:   {trades_by_signal['NEUTRAL']} ({trades_by_signal['NEUTRAL']/iterations*100:.1f}%)")
    logger.info("")

    # Verdict with detailed feedback
    if len(session.trades) == 0:
        logger.warning("⚠️  NO TRADES - Conviction threshold too high or signals too weak")
        logger.info("    → Try lowering conviction threshold from 0.3 to 0.2")
    elif total_pnl > 0 and win_rate >= 0.55:
        logger.success("✓ EXCELLENT - Profitable with >55% win rate")
    elif total_pnl > 0 and win_rate >= 0.50:
        logger.success("✓ GOOD - Profitable with breakeven+ win rate")
    elif total_pnl > 0:
        logger.info("⚪ POSITIVE P&L but low win rate - Lucky or needs optimization")
    elif total_pnl == 0:
        logger.info("⚪ BREAKEVEN - Not enough data or neutral signals")
    else:
        logger.warning("⚠️  NEGATIVE P&L - Signal combination needs tuning")

    logger.info("")
    logger.info("🎯 Demo Insights:")
    logger.info(f"  • Signal normalization builds history over {iterations} cycles")
    logger.info(f"  • L2 + Web3 agreement required for high-conviction trades")
    logger.info(f"  • Position sizing scales with conviction (20%-50%-100%)")
    logger.info(f"  • Simulated exit prices show ±0.1-0.2% typical slippage")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Run longer simulation (--iterations 100) for better statistics")
    logger.info("  2. Try different normalization methods (percentile vs zscore)")
    logger.info("  3. Adjust conviction thresholds in TradingEngine")
    logger.info("  4. Backtest on real historical data")
    logger.info("  5. Deploy to paper trading (60 days minimum)")
    logger.info("")


def main():
    """Parse arguments and run demo."""
    parser = argparse.ArgumentParser(description="Full-scale SIMULATED trading demo")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 10 iterations (~15 seconds)"
    )
    parser.add_argument(
        "--medium",
        action="store_true",
        help="Medium mode: 30 iterations (~45 seconds)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full mode: 100 iterations (~2 minutes)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        help="Custom number of iterations"
    )

    args = parser.parse_args()

    # Determine mode
    if args.quick:
        iterations = 10
        delay = 1
    elif args.medium:
        iterations = 30
        delay = 1
    elif args.full:
        iterations = 100
        delay = 1
    elif args.iterations:
        iterations = args.iterations
        delay = 1
    else:
        # Default: Medium
        iterations = 30
        delay = 1

    logger.info(f"Running {iterations} trading cycles (simulated mode)...")
    logger.info("")

    # Run demo
    try:
        asyncio.run(run_simulated_demo(
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
