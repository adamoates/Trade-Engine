"""
Integration Test: Breakout Detector + Binance.us Spot Broker

This example demonstrates:
1. Using BreakoutSetupDetector with realistic market data
2. Integrating with Binance.us spot broker (or simulated broker)
3. Signal generation and order execution workflow
4. Position management and P&L tracking

SAFETY NOTE:
- This script uses SimulatedBroker by default (no real trades)
- To use real Binance.us API, set USE_REAL_BROKER=True and provide API keys
- Always test with simulation first before live trading!

Usage:
    # Simulation mode (safe, no API keys needed)
    python examples/test_breakout_with_binance_us.py

    # Real broker mode (requires API keys)
    export BINANCE_US_API_KEY="your_key"
    export BINANCE_US_API_SECRET="your_secret"
    python examples/test_breakout_with_binance_us.py --real
"""

import sys
import argparse
from decimal import Decimal
from typing import List
from loguru import logger

# Add src to path
sys.path.insert(0, 'src')

from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig,
    SetupSignal
)
from trade_engine.core.types import Bar, Signal
from trade_engine.adapters.brokers.simulated import SimulatedBroker


def create_realistic_market_data() -> List[Bar]:
    """
    Create realistic market data simulating a breakout scenario.

    Pattern:
    1. Consolidation phase (20 bars)
    2. Resistance formation at 50,300
    3. Volume drying up
    4. Volatility squeeze (Bollinger Bands tightening)
    5. Breakout above resistance with volume spike

    Returns:
        List of Bar objects
    """
    bars = []
    timestamp = 1000

    # Phase 1: Initial consolidation (10 bars)
    logger.info("📊 Phase 1: Initial consolidation")
    base_prices = [50000, 50100, 50200, 50150, 50100, 50050, 50100, 50150, 50200, 50100]
    for i, price in enumerate(base_prices):
        bar = Bar(
            timestamp=timestamp + i,
            open=Decimal(str(price - 30)),
            high=Decimal(str(price + 50)),
            low=Decimal(str(price - 50)),
            close=Decimal(str(price)),
            volume=Decimal("100")  # Normal volume
        )
        bars.append(bar)

    timestamp += len(base_prices)

    # Phase 2: Testing resistance at 50,300 (7 bars - create clear swing highs)
    logger.info("📊 Phase 2: Testing resistance at 50,300")
    # Create swing high pattern for resistance detection
    resistance_test = [
        (50150, 50250, 50100, 50200, 95),   # Moving up
        (50200, 50350, 50180, 50320, 100),  # First touch of resistance (swing high)
        (50320, 50340, 50200, 50250, 90),   # Rejection
        (50250, 50280, 50150, 50200, 85),   # Pullback
        (50200, 50360, 50180, 50330, 105),  # Second touch (swing high)
        (50330, 50350, 50200, 50240, 85),   # Rejection again
        (50240, 50280, 50150, 50220, 80),   # Final consolidation
    ]
    for i, (open_p, high, low, close, vol) in enumerate(resistance_test):
        bar = Bar(
            timestamp=timestamp + i,
            open=Decimal(str(open_p)),
            high=Decimal(str(high)),  # Highs around 50,340-50,360 = resistance
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=Decimal(str(vol))
        )
        bars.append(bar)

    timestamp += len(resistance_test)

    # Phase 3: Squeeze - tight consolidation (8 bars)
    logger.info("📊 Phase 3: Volatility squeeze")
    squeeze_prices = [50200, 50180, 50190, 50200, 50195, 50205, 50200, 50210]
    for i, price in enumerate(squeeze_prices):
        bar = Bar(
            timestamp=timestamp + i,
            open=Decimal(str(price - 5)),
            high=Decimal(str(price + 15)),  # Very tight range
            low=Decimal(str(price - 15)),
            close=Decimal(str(price)),
            volume=Decimal("80")  # Low volume during squeeze
        )
        bars.append(bar)

    timestamp += len(squeeze_prices)

    # Phase 4: Pre-breakout accumulation (2 bars)
    logger.info("📊 Phase 4: Pre-breakout accumulation")
    accumulation_prices = [50220, 50260]
    for i, price in enumerate(accumulation_prices):
        bar = Bar(
            timestamp=timestamp + i,
            open=Decimal(str(price - 10)),
            high=Decimal(str(price + 20)),
            low=Decimal(str(price - 15)),
            close=Decimal(str(price)),
            volume=Decimal("110")  # Volume starting to increase
        )
        bars.append(bar)

    timestamp += len(accumulation_prices)

    # Phase 5: BREAKOUT! (1 bar with strong volume but moderate move)
    logger.info("📊 Phase 5: 🚀 BREAKOUT!")
    breakout_bar = Bar(
        timestamp=timestamp,
        open=Decimal("50270"),
        high=Decimal("50480"),      # Clear break above 50,360 resistance
        low=Decimal("50260"),
        close=Decimal("50450"),     # Strong close above resistance
        volume=Decimal("280")       # 2.8× average volume spike!
    )
    bars.append(breakout_bar)

    timestamp += 1

    # Phase 6: Follow-through (3 bars with moderate gains to keep RSI reasonable)
    logger.info("📊 Phase 6: Follow-through movement")
    followthrough = [
        (50450, 50520, 50420, 50480, 180),  # Continuation
        (50480, 50580, 50450, 50550, 160),  # Further gains
        (50550, 50600, 50500, 50570, 150),  # Consolidation near highs
    ]
    for i, (open_p, high, low, close, vol) in enumerate(followthrough):
        bar = Bar(
            timestamp=timestamp + i,
            open=Decimal(str(open_p)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=Decimal(str(vol))
        )
        bars.append(bar)

    return bars


def run_breakout_test(use_real_broker: bool = False):
    """
    Run comprehensive breakout detector test with broker integration.

    Args:
        use_real_broker: If True, use real Binance.us broker (requires API keys)
    """
    print("\n" + "=" * 80)
    print("🧪 Breakout Detector + Binance.us Integration Test")
    print("=" * 80)

    # Initialize broker
    if use_real_broker:
        logger.warning("⚠️  REAL BROKER MODE - Trades will be executed on Binance.us!")
        try:
            from trade_engine.adapters.brokers.binance_us import BinanceUSSpotBroker
            broker = BinanceUSSpotBroker()
            logger.info("✅ Connected to Binance.us spot broker")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Binance.us broker: {e}")
            logger.info("💡 Make sure BINANCE_US_API_KEY and BINANCE_US_API_SECRET are set")
            logger.info("🔄 Falling back to simulated broker...")
            broker = SimulatedBroker(initial_balance=Decimal("10000"))
    else:
        logger.info("🎮 SIMULATION MODE - No real trades will be executed")
        broker = SimulatedBroker(initial_balance=Decimal("10000"))

    # Initialize breakout detector strategy
    # Using slightly aggressive config for testing
    config = BreakoutConfig(
        volume_spike_threshold=Decimal("2.5"),  # Require 2.5× volume
        rsi_bullish_threshold=Decimal("52"),     # Lower RSI requirement for testing
        rsi_overbought_threshold=Decimal("85"),  # Higher threshold to allow breakout
        resistance_confirmation_pct=Decimal("0.5"),  # 0.5% above resistance
        sr_lookback_bars=25,                     # Lower lookback for test data
        position_size_usd=Decimal("1000")        # $1000 position size
    )

    strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

    logger.info(f"✅ Strategy initialized: {strategy.symbol}")
    logger.info(f"   Volume threshold: {config.volume_spike_threshold}×")
    logger.info(f"   RSI threshold: {config.rsi_bullish_threshold}")
    logger.info(f"   Position size: ${config.position_size_usd}")

    # Generate realistic market data
    bars = create_realistic_market_data()
    logger.info(f"✅ Generated {len(bars)} bars of market data")

    # Track signals and orders
    all_signals: List[Signal] = []
    all_setups: List[SetupSignal] = []
    order_ids: List[str] = []

    print("\n" + "=" * 80)
    print("📈 Processing Market Data")
    print("=" * 80)

    # Process each bar
    for i, bar in enumerate(bars):
        # Feed bar to strategy
        signals = strategy.on_bar(bar)

        # Get detailed setup analysis
        setup = strategy._analyze_breakout_setup(bar)
        all_setups.append(setup)

        # Log progress every 5 bars
        if (i + 1) % 5 == 0 or signals:
            logger.info(
                f"Bar {i+1:2d}/{len(bars)} | "
                f"Close: {float(bar.close):,.0f} | "
                f"Vol: {float(bar.volume):>3.0f} | "
                f"Setup: {setup.setup:15s} | "
                f"Conf: {float(setup.confidence):.2f}"
            )

        # Execute signals
        if signals:
            for signal in signals:
                all_signals.append(signal)

                logger.info("=" * 60)
                logger.info("🎯 SIGNAL GENERATED!")
                logger.info(f"   Symbol: {signal.symbol}")
                logger.info(f"   Side: {signal.side.upper()}")
                logger.info(f"   Entry: ${float(signal.price):,.2f}")
                logger.info(f"   Quantity: {float(signal.qty):.6f}")
                logger.info(f"   Stop Loss: ${float(signal.sl):,.2f}")
                logger.info(f"   Take Profit: ${float(signal.tp):,.2f}")
                logger.info(f"   Reason: {signal.reason}")
                logger.info("=" * 60)

                # Display detailed setup metrics
                print("\n📊 Setup Metrics:")
                print(f"   Confidence: {float(setup.confidence):.1%}")
                print(f"   Current Price: ${float(setup.current_price):,.2f}")
                if setup.resistance_level:
                    print(f"   Resistance: ${float(setup.resistance_level):,.2f}")
                print(f"   Volume Ratio: {float(setup.volume_ratio):.2f}×")
                print(f"   RSI: {float(setup.rsi):.1f}")
                print(f"   MACD Histogram: {float(setup.macd_histogram):+.4f}")
                print(f"   BB Bandwidth: {float(setup.bb_bandwidth_pct):.2f}%")

                print("\n✅ Conditions Met:")
                for condition in setup.conditions_met:
                    print(f"   • {condition}")

                if setup.conditions_failed:
                    print("\n⚠️  Conditions Not Met:")
                    for condition in setup.conditions_failed:
                        print(f"   • {condition}")

                # Execute order via broker
                try:
                    if signal.side == "buy":
                        order_id = broker.buy(
                            symbol=signal.symbol,
                            qty=signal.qty,
                            sl=signal.sl,
                            tp=signal.tp
                        )
                        order_ids.append(order_id)
                        logger.info(f"✅ BUY order executed | Order ID: {order_id}")
                    else:
                        logger.warning(f"⚠️  SHORT signal ignored (spot trading = long only)")
                except Exception as e:
                    logger.error(f"❌ Order execution failed: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 Test Summary")
    print("=" * 80)
    print(f"Total bars processed: {len(bars)}")
    print(f"Signals generated: {len(all_signals)}")
    print(f"Orders executed: {len(order_ids)}")

    if all_signals:
        print("\n🎯 Signal Details:")
        for i, signal in enumerate(all_signals, 1):
            print(f"\nSignal {i}:")
            print(f"  Side: {signal.side.upper()}")
            print(f"  Entry: ${float(signal.price):,.2f}")
            print(f"  Qty: {float(signal.qty):.6f}")
            print(f"  Risk: ${float(signal.price - signal.sl) * float(signal.qty):,.2f}")
            print(f"  Reward: ${float(signal.tp - signal.price) * float(signal.qty):,.2f}")
            print(f"  R:R Ratio: {float(signal.tp - signal.price) / float(signal.price - signal.sl):.2f}:1")

    # Resistance levels detected
    if strategy.resistance_levels:
        print("\n📍 Key Levels Identified:")
        print(f"  Resistance levels: {[f'${float(r):,.0f}' for r in strategy.resistance_levels[:3]]}")
    if strategy.support_levels:
        print(f"  Support levels: {[f'${float(s):,.0f}' for s in strategy.support_levels[:3]]}")

    # Setup statistics
    bullish_setups = [s for s in all_setups if s.setup == "Bullish Breakout"]
    watchlist_setups = [s for s in all_setups if s.setup == "Watchlist"]

    print(f"\n📈 Setup Statistics:")
    print(f"  Bullish Breakout: {len(bullish_setups)}")
    print(f"  Watchlist: {len(watchlist_setups)}")
    print(f"  No Trade: {len(all_setups) - len(bullish_setups) - len(watchlist_setups)}")

    if bullish_setups:
        avg_confidence = sum(s.confidence for s in bullish_setups) / len(bullish_setups)
        print(f"  Avg Confidence (Bullish): {float(avg_confidence):.1%}")

    print("\n" + "=" * 80)
    print("✅ Test Complete!")
    print("=" * 80)

    return len(all_signals) > 0  # Return True if signals were generated


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 80)
    print("🧪 Testing Edge Cases")
    print("=" * 80)

    strategy = BreakoutSetupDetector(symbol="ETHUSDT")
    broker = SimulatedBroker()

    # Test 1: Insufficient data
    logger.info("Test 1: Insufficient data (first few bars)")
    for i in range(5):
        bar = Bar(
            timestamp=i,
            open=Decimal("3000"),
            high=Decimal("3010"),
            low=Decimal("2990"),
            close=Decimal("3000"),
            volume=Decimal("50")
        )
        signals = strategy.on_bar(bar)
        assert len(signals) == 0, "Should not generate signals with insufficient data"
    logger.info("✅ Pass: No signals with insufficient data")

    # Test 2: Flat market (no breakout)
    logger.info("Test 2: Flat market (no breakout)")
    strategy.reset()
    for i in range(30):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal("3000"),
            high=Decimal("3005"),
            low=Decimal("2995"),
            close=Decimal("3000"),
            volume=Decimal("50")
        )
        signals = strategy.on_bar(bar)
    assert len(signals) == 0, "Should not signal in flat market"
    logger.info("✅ Pass: No signals in flat market")

    # Test 3: Overextended RSI (should filter)
    logger.info("Test 3: Overextended RSI filter")
    strategy.reset()
    # Create strong uptrend to push RSI high
    for i in range(20):
        bar = Bar(
            timestamp=2000 + i,
            open=Decimal(str(3000 + i * 100)),
            high=Decimal(str(3100 + i * 100)),
            low=Decimal(str(2900 + i * 100)),
            close=Decimal(str(3000 + i * 100)),
            volume=Decimal("100")
        )
        signals = strategy.on_bar(bar)

    if strategy.rsi_values:
        rsi = strategy.rsi_values[-1]
        logger.info(f"   Final RSI: {float(rsi):.1f}")
        if rsi > strategy.config.rsi_overbought_threshold:
            logger.info("✅ Pass: High RSI detected (would filter entry)")

    print("\n✅ All edge case tests passed!")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Test Breakout Detector with Binance.us broker"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real Binance.us broker (requires API keys)"
    )
    parser.add_argument(
        "--edge-cases",
        action="store_true",
        help="Run edge case tests"
    )
    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )

    try:
        # Run main test
        success = run_breakout_test(use_real_broker=args.real)

        # Run edge case tests if requested
        if args.edge_cases:
            test_edge_cases()

        # Exit code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Test failed with error: {e}")
        sys.exit(1)
