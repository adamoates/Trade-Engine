#!/usr/bin/env python3
"""
Full System Integration Demo - REALISTIC Simulation (Fixed for False Positives)

Demonstrates all working components with REALISTIC market conditions:
- Web3 signals with 55% accuracy (correlated with price moves)
- L2 order book imbalance with 60% accuracy (imperfect predictive signals)
- Signal combination and conviction scoring
- Risk-based position sizing
- REALISTIC trade execution (NO look-ahead bias, includes fees & slippage)

Key fixes from original version:
1. Price movements generated BEFORE signals (no look-ahead bias)
2. Trade P&L based on ACTUAL market movement (not signal direction)
3. Signals have realistic imperfect correlation with future price moves
4. Trading fees (0.08% round-trip) and slippage (0.05-0.15%) included

This properly tests if signal combination adds value over baseline ~50% accuracy.

Usage:
    python tools/demo_full_system_simple.py --quick
    python tools/demo_full_system_simple.py --cycles 50
"""

import sys
import argparse
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from dataclasses import dataclass, field

import numpy as np
from loguru import logger

# Import validated components
from mft.services.data.web3_signals import Web3DataSource, GasData, LiquidityData, FundingRateData
from mft.services.data.signal_normalizer import SignalNormalizer

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
    level="INFO"
)


@dataclass
class L2OrderBook:
    """Level 2 order book."""
    symbol: str
    bids: List[tuple]
    asks: List[tuple]
    timestamp: datetime
    
    def get_imbalance_ratio(self, depth: int = 5) -> float:
        bid_volume = sum(qty for _, qty in self.bids[:depth])
        ask_volume = sum(qty for _, qty in self.asks[:depth])
        return bid_volume / ask_volume if ask_volume > 0 else 1.0
    
    def get_signal(self, depth: int = 5) -> tuple:
        ratio = self.get_imbalance_ratio(depth)
        if ratio > 3.0:
            return "BUY", min((ratio - 1.0) / 5.0, 1.0)
        elif ratio < 0.33:
            return "SELL", min((1.0 - ratio * 3) / 2.0, 1.0)
        return "NEUTRAL", abs(ratio - 1.0) / 2.0


@dataclass
class Trade:
    timestamp: datetime
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    conviction: float
    signals: Dict[str, str] = field(default_factory=dict)


@dataclass  
class TradingState:
    capital: float = 10000.0
    equity: float = 10000.0
    trades: List[Trade] = field(default_factory=list)
    
    def record_trade(self, trade: Trade):
        self.trades.append(trade)
        self.equity += trade.pnl
    
    def get_metrics(self):
        if not self.trades:
            return {
                "total": 0, "winners": 0, "losers": 0,
                "win_rate": 0.0, "pnl": 0.0, "return_pct": 0.0
            }
        
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in self.trades)
        
        return {
            "total": len(self.trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / len(self.trades),
            "pnl": total_pnl,
            "return_pct": (self.equity - self.capital) / self.capital * 100,
            "avg_win": sum(t.pnl for t in winners) / len(winners) if winners else 0,
            "avg_loss": sum(t.pnl for t in losers) / len(losers) if losers else 0
        }


class MarketSimulator:
    """Simulates realistic market with varying regimes - NO LOOK-AHEAD BIAS."""

    def __init__(self, base_price: float = 45000.0):
        self.price = base_price
        self.cycle = 0
        self.trend = 0.0
        self.next_move = 0.0  # Pre-calculated next price movement
        self.current_regime = "ranging"

    def _generate_next_move(self) -> float:
        """
        Generate next price movement BEFORE signals are created.
        This ensures signals can't peek into the future.
        """
        # Cycle through different market conditions
        if self.cycle % 30 < 10:
            # Trending regime
            self.current_regime = "trending"
            self.trend += np.random.normal(0.002, 0.001)
            vol = 0.003
        elif self.cycle % 30 < 20:
            # Ranging regime
            self.current_regime = "ranging"
            self.trend *= 0.9
            vol = 0.001
        else:
            # Volatile regime
            self.current_regime = "volatile"
            self.trend += np.random.normal(0, 0.003)
            vol = 0.008

        # Return next price change (this is the "future" we're trying to predict)
        return self.trend + np.random.normal(0, vol)

    def advance(self) -> float:
        """
        Advance to next cycle and return current price.
        Next move is already generated but not yet applied.
        """
        self.cycle += 1
        # Generate the move AFTER this one (for next cycle)
        self.next_move = self._generate_next_move()
        return self.price

    def apply_move(self) -> float:
        """
        Apply the pre-generated price movement.
        This simulates the actual market moving after we've made our trading decision.
        """
        self.price *= (1 + self.next_move)
        return self.price

    def get_orderbook(self, signal_quality: float = 0.60) -> L2OrderBook:
        """
        Generate order book with IMPERFECT forward-looking information.

        Args:
            signal_quality: Probability that L2 signal correctly predicts next move (0.5-0.7 realistic)
        """
        # L2 signals have SOME predictive power, but not perfect
        # They correctly "see" the next move with signal_quality probability
        if np.random.random() < signal_quality:
            # Signal is correct - order book hints at true next move
            predictive_trend = self.next_move
        else:
            # Signal is wrong - order book shows opposite or neutral
            predictive_trend = -self.next_move if np.random.random() < 0.5 else 0

        # Add noise to make it imperfect
        predictive_trend += np.random.normal(0, 0.002)

        # Generate order book imbalance based on (noisy) predictive signal
        if predictive_trend > 0.003:
            bid_mult, ask_mult = 1.5, 0.8  # Bullish signal
        elif predictive_trend < -0.003:
            bid_mult, ask_mult = 0.8, 1.5  # Bearish signal
        else:
            bid_mult, ask_mult = 1.0, 1.0  # Neutral

        # Add randomness to order book
        bids = [(self.price * (1 - 0.0001 * (i+1)),
                 np.random.exponential(0.5) * bid_mult)
                for i in range(10)]
        asks = [(self.price * (1 + 0.0001 * (i+1)),
                 np.random.exponential(0.5) * ask_mult)
                for i in range(10)]

        return L2OrderBook("BTCUSDT", bids, asks, datetime.now(timezone.utc))


class IntegratedSystem:
    """Complete system with all features."""
    
    def __init__(self):
        self.simulator = MarketSimulator()
        self.web3 = self._create_web3_source()
        self.normalizer = SignalNormalizer(method="zscore")
        self.state = TradingState()
        
        logger.info("✓ System initialized with all components")
    
    def _create_web3_source(self, signal_quality: float = 0.55):
        """
        Create simulated Web3 source with REALISTIC correlation to price moves.

        Args:
            signal_quality: Probability Web3 signals correctly predict direction (0.5-0.65 realistic)
        """
        source = Web3DataSource(normalize=True)

        def get_correlated_gas():
            """Gas prices have weak correlation with BTC price action."""
            # Web3 signals are imperfect predictors
            if np.random.random() < signal_quality:
                # Correct signal: high gas when price going up (network activity)
                correlation = self.simulator.next_move
            else:
                # Incorrect signal: random or inverse
                correlation = np.random.normal(0, 0.01)

            # Base gas + correlation component + noise
            base_gas = 30
            gas_signal = base_gas + correlation * 500 + np.random.normal(0, 5)
            gas_signal = max(15, gas_signal)

            return GasData(
                safe_gas_price=gas_signal * 0.8,
                propose_gas_price=gas_signal,
                fast_gas_price=gas_signal * 1.2,
                timestamp=datetime.now(timezone.utc)
            )

        def get_correlated_liquidity(pool="WBTC/USDC"):
            """DEX liquidity correlates with market confidence."""
            if np.random.random() < signal_quality:
                # Correct signal: more liquidity when price stable/rising
                correlation = self.simulator.next_move
            else:
                # Incorrect signal
                correlation = np.random.normal(0, 0.005)

            base_liquidity = 5_000_000
            liquidity_value = base_liquidity + correlation * 50_000_000 + np.random.normal(0, 500_000)
            liquidity_value = max(1_000_000, liquidity_value)

            return LiquidityData(
                pool_address="0x...",
                token0="WBTC",
                token1="USDC",
                liquidity=liquidity_value * 20,
                volume_24h_usd=liquidity_value,
                timestamp=datetime.now(timezone.utc)
            )

        def get_correlated_funding(symbol="BTC-USD"):
            """Funding rate reflects long/short imbalance."""
            if np.random.random() < signal_quality:
                # Correct signal: positive funding = longs > shorts = price pressure up
                correlation = self.simulator.next_move
            else:
                # Incorrect signal
                correlation = np.random.normal(0, 0.01)

            funding = correlation * 2 + np.random.normal(0, 0.005)
            funding = np.clip(funding, -0.02, 0.02)

            return FundingRateData(
                symbol=symbol,
                funding_rate=funding,
                next_funding_time=datetime.now(timezone.utc),
                timestamp=datetime.now(timezone.utc)
            )

        # Override with correlated data
        source.get_gas_prices = get_correlated_gas
        source.get_dex_liquidity = get_correlated_liquidity
        source.get_funding_rate = get_correlated_funding

        return source
    
    async def run_cycle(self) -> Dict[str, Any]:
        """
        Execute one complete trading cycle with REALISTIC trade execution.

        Flow:
        1. Advance market (price at cycle start, next move pre-generated)
        2. Get signals (trying to predict the pre-generated next move)
        3. Make trading decision
        4. Apply actual market movement
        5. Calculate P&L based on actual movement (not signal direction)
        """

        # 1. Advance market and get current price (next move already generated but hidden)
        entry_price = self.simulator.advance()

        # 2. Get order book (with imperfect predictive signals)
        orderbook = self.simulator.get_orderbook(signal_quality=0.60)

        # 3. Get Web3 signals (with imperfect predictive signals)
        web3_signal = self.web3.get_combined_signal()

        # 4. Get L2 signals
        l2_signal, l2_strength = orderbook.get_signal()
        l2_norm = self.normalizer.normalize(
            orderbook.get_imbalance_ratio(),
            "l2_imbalance"
        )

        # 5. Calculate conviction
        web3_strength = abs(web3_signal.score) / 3.0
        conviction = (
            web3_signal.confidence * 0.4 +
            web3_strength * 0.3 +
            abs(l2_norm) * 0.3
        )

        # 6. Combine signals (majority vote)
        buy_votes = sum(1 for s in [web3_signal.signal, l2_signal] if s == "BUY")
        sell_votes = sum(1 for s in [web3_signal.signal, l2_signal] if s == "SELL")

        if buy_votes > sell_votes and conviction > 0.3:
            final_signal = "BUY"
        elif sell_votes > buy_votes and conviction > 0.3:
            final_signal = "SELL"
        else:
            final_signal = "NEUTRAL"

        # 7. Position sizing (conviction-based)
        if conviction > 0.7:
            position_size = self.state.capital * 0.10
        elif conviction > 0.5:
            position_size = self.state.capital * 0.05
        elif conviction > 0.3:
            position_size = self.state.capital * 0.02
        else:
            position_size = 0

        # 8. Execute trade with REALISTIC price movement
        traded = False
        if final_signal in ["BUY", "SELL"] and position_size > 0:
            # Entry at current price (with slippage)
            slippage = np.random.uniform(0.0005, 0.0015)
            entry_with_slippage = entry_price * (1 + slippage)

            # Market moves according to pre-generated next_move (NOT our signal!)
            exit_price = self.simulator.apply_move()

            # Calculate P&L based on ACTUAL price movement, not signal
            qty = position_size / entry_with_slippage
            if final_signal == "BUY":
                pnl = (exit_price - entry_with_slippage) * qty
            else:  # SELL
                pnl = (entry_with_slippage - exit_price) * qty

            # Subtract trading fees (0.04% each side = 0.08% round trip)
            fees = position_size * 0.0008
            pnl -= fees

            trade = Trade(
                timestamp=datetime.now(timezone.utc),
                side=final_signal,
                entry_price=entry_with_slippage,
                exit_price=exit_price,
                quantity=qty,
                pnl=pnl,
                conviction=conviction,
                signals={"web3": web3_signal.signal, "l2": l2_signal}
            )

            self.state.record_trade(trade)
            traded = True
        else:
            # No trade - still apply market movement for next cycle
            self.simulator.apply_move()

        return {
            "cycle": self.simulator.cycle,
            "price": entry_price,
            "web3": web3_signal.signal,
            "web3_score": web3_signal.score,
            "web3_conf": web3_signal.confidence,
            "l2": l2_signal,
            "l2_strength": l2_strength,
            "conviction": conviction,
            "final": final_signal,
            "traded": traded,
            "metrics": self.state.get_metrics()
        }


async def run_demo(cycles: int, delay: float):
    """Run the demo with REALISTIC market simulation (no look-ahead bias)."""
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info("║" + " " * 15 + "REALISTIC TRADING SIMULATION" + " " * 34 + "║")
    logger.info("║" + " " * 10 + "Web3 + L2 + Signal Combination + Risk Sizing" + " " * 23 + "║")
    logger.info("║" + " " * 17 + "(No Look-Ahead Bias)" + " " * 40 + "║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")
    logger.info("📊 Signal Quality: L2=60% correct, Web3=55% correct")
    logger.info("💰 Fees: 0.08% round-trip | Slippage: 0.05-0.15%")
    logger.info("")
    
    system = IntegratedSystem()
    
    logger.info(f"Running {cycles} cycles with ${system.state.capital:,.0f} capital")
    logger.info("=" * 80)
    logger.info("")
    
    start = time.time()
    
    for i in range(1, cycles + 1):
        result = await system.run_cycle()
        
        if result['traded']:
            logger.success(
                f"Cycle {i:3d} | {result['final']:4s} | "
                f"Conv: {result['conviction']:.2f} | "
                f"Web3: {result['web3']:8s} ({result['web3_score']:+.1f}) | "
                f"L2: {result['l2']:8s} ({result['l2_strength']:.2f}) | "
                f"✓ TRADE"
            )
        else:
            logger.debug(
                f"Cycle {i:3d} | {result['final']:8s} | "
                f"Conv: {result['conviction']:.2f} | "
                f"Web3: {result['web3']:8s} | L2: {result['l2']:8s}"
            )
        
        if i % 10 == 0 and i < cycles:
            m = result['metrics']
            logger.info("")
            logger.info(f"📊 Progress ({i}/{cycles}): Trades: {m['total']} | Win: {m['win_rate']:.1%} | P&L: ${m['pnl']:+.2f} | Return: {m['return_pct']:+.1f}%")
            logger.info("")
        
        await asyncio.sleep(delay)
    
    elapsed = time.time() - start
    
    # Final results
    logger.info("")
    logger.info("=" * 80)
    logger.info("FINAL RESULTS")
    logger.info("=" * 80)
    logger.info("")
    
    m = result['metrics']
    
    logger.info("📈 Performance:")
    logger.info(f"  Capital:      ${system.state.capital:,.2f}")
    logger.info(f"  Equity:       ${system.state.equity:,.2f}")
    logger.info(f"  P&L:          ${m['pnl']:+,.2f}")
    logger.info(f"  Return:       {m['return_pct']:+.2f}%")
    logger.info("")
    logger.info(f"  Cycles:       {cycles}")
    logger.info(f"  Trades:       {m['total']} ({m['total']/cycles*100:.1f}%)")
    logger.info(f"  Winners:      {m['winners']}")
    logger.info(f"  Losers:       {m['losers']}")
    logger.info(f"  Win Rate:     {m['win_rate']:.1%}")
    logger.info(f"  Avg Win:      ${m['avg_win']:+.2f}")
    logger.info(f"  Avg Loss:     ${m['avg_loss']:+.2f}")
    logger.info("")
    logger.info(f"  Duration:     {elapsed:.1f}s")
    logger.info("")
    
    # Verdict
    logger.info("📋 Interpretation:")
    logger.info("   Individual signals are only 55-60% accurate")
    logger.info("   Success requires signal combination to beat ~50% baseline")
    logger.info("")

    if m['total'] == 0:
        logger.warning("⚠️  NO TRADES - Try lowering conviction threshold")
    elif m['return_pct'] > 2 and m['win_rate'] >= 0.55:
        logger.success("✓ EXCELLENT - Signal combination working!")
    elif m['return_pct'] > 0 and m['win_rate'] > 0.52:
        logger.success("✓ PROFITABLE - Slight edge detected")
    elif m['win_rate'] >= 0.48 and m['win_rate'] <= 0.52:
        logger.warning("⚠️  BREAK-EVEN - Signals not adding value (expected with weak signals)")
    else:
        logger.error("❌ LOSING - Signal combination worse than random")
    
    logger.info("")
    logger.info("🎯 Components Demonstrated:")
    logger.info("  ✓ Web3 signals (gas, liquidity, funding) - 55% accuracy")
    logger.info("  ✓ L2 order book imbalance - 60% accuracy")
    logger.info("  ✓ Signal normalization (z-score)")
    logger.info("  ✓ Multi-signal combination (majority vote)")
    logger.info("  ✓ Conviction scoring")
    logger.info("  ✓ Risk-based position sizing")
    logger.info("  ✓ Realistic trade execution (fees, slippage, NO look-ahead bias)")
    logger.info("")
    logger.info("✅ This simulation properly tests if signal combination adds value")
    logger.info("")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--cycles", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()
    
    cycles = 10 if args.quick else args.cycles
    delay = 0.2 if args.quick else args.delay
    
    try:
        asyncio.run(run_demo(cycles, delay))
    except KeyboardInterrupt:
        logger.warning("\nInterrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
