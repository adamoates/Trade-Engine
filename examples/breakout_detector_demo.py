"""
Breakout Setup Detector - Demo Usage

This example demonstrates how to use the BreakoutSetupDetector strategy
to identify bullish breakout setups in real-time or historical data.

The detector combines:
- Price breakout above resistance with volume confirmation
- Momentum indicators (RSI, MACD)
- Volatility squeeze (Bollinger Bands)
- Derivatives signals (Open Interest, Funding Rate, Put/Call Ratio)
- Risk filters (overextension, trap detection)
"""

from decimal import Decimal
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig
)
from trade_engine.core.types import Bar


def demo_basic_usage():
    """Basic usage with default configuration."""
    print("=" * 80)
    print("Demo 1: Basic Usage with Default Configuration")
    print("=" * 80)

    # Initialize strategy
    strategy = BreakoutSetupDetector(symbol="BTCUSDT")

    # Simulate market data (normally from exchange feed)
    # Creating a pattern: consolidation → resistance → breakout

    print("\nPhase 1: Consolidation (building resistance)")
    consolidation_bars = [
        (50000, 50100, 49900, 50000, 100),  # Bar 1
        (50000, 50200, 49800, 50100, 110),  # Bar 2
        (50100, 50300, 50000, 50200, 120),  # Bar 3 (resistance forming at 50300)
        (50200, 50300, 50100, 50150, 105),  # Bar 4
        (50150, 50280, 50050, 50100, 100),  # Bar 5
        (50100, 50290, 50000, 50200, 115),  # Bar 6 (tested 50300 again)
        (50200, 50250, 50100, 50150, 95),   # Bar 7
        (50150, 50200, 50050, 50100, 100),  # Bar 8
    ]

    for i, (open_p, high, low, close, volume) in enumerate(consolidation_bars):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal(str(open_p)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=Decimal(str(volume))
        )
        signals = strategy.on_bar(bar)
        print(f"  Bar {i+1}: Close={close}, Vol={volume}, Signals={len(signals)}")

    print(f"\n  Resistance levels detected: {[float(r) for r in strategy.resistance_levels[:3]]}")

    # Continue with more consolidation bars (need 20+ for all indicators)
    print("\nPhase 2: Extended consolidation (building indicators)")
    for i in range(15):
        bar = Bar(
            timestamp=2000 + i,
            open=Decimal("50000"),
            high=Decimal("50200"),
            low=Decimal("49900"),
            close=Decimal(str(50000 + (i % 3) * 50)),
            volume=Decimal("100")
        )
        signals = strategy.on_bar(bar)

    if strategy.rsi_values:
        print(f"  RSI: {float(strategy.rsi_values[-1]):.1f}")
    if strategy.macd_histogram_values:
        print(f"  MACD Histogram: {float(strategy.macd_histogram_values[-1]):+.2f}")

    # Breakout with volume spike
    print("\nPhase 3: Breakout attempt")
    breakout_bar = Bar(
        timestamp=3000,
        open=Decimal("50200"),
        high=Decimal("51000"),
        low=Decimal("50150"),
        close=Decimal("50800"),  # Breaking above 50300 resistance
        volume=Decimal("300")    # 3x normal volume
    )
    signals = strategy.on_bar(breakout_bar)

    print(f"  Breakout bar: Close={50800}, Volume=300 (3x avg)")
    print(f"  Signals generated: {len(signals)}")

    if signals:
        signal = signals[0]
        print(f"\n  ✅ SIGNAL GENERATED:")
        print(f"     Symbol: {signal.symbol}")
        print(f"     Side: {signal.side.upper()}")
        print(f"     Quantity: {float(signal.qty):.6f}")
        print(f"     Entry Price: {float(signal.price):.2f}")
        print(f"     Stop Loss: {float(signal.sl):.2f}")
        print(f"     Take Profit: {float(signal.tp):.2f}")
        print(f"     Reason: {signal.reason}")
    else:
        print("  No signal generated (may need more confirmations)")


def demo_with_custom_config():
    """Usage with custom configuration."""
    print("\n\n" + "=" * 80)
    print("Demo 2: Custom Configuration (More Aggressive)")
    print("=" * 80)

    # Create custom config with more aggressive thresholds
    config = BreakoutConfig(
        volume_spike_threshold=Decimal("1.5"),  # Lower threshold (1.5x instead of 2x)
        rsi_bullish_threshold=Decimal("50"),    # Lower RSI requirement
        rsi_overbought_threshold=Decimal("80"), # Higher overbought limit
        resistance_confirmation_pct=Decimal("0.3"),  # Only need 0.3% above resistance
        position_size_usd=Decimal("2000")       # Larger position size
    )

    strategy = BreakoutSetupDetector(symbol="ETHUSDT", config=config)

    print("\nCustom Config:")
    print(f"  Volume spike threshold: {float(config.volume_spike_threshold)}x")
    print(f"  RSI bullish threshold: {float(config.rsi_bullish_threshold)}")
    print(f"  Position size: ${float(config.position_size_usd)}")

    # Process bars
    for i in range(25):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal(str(3000 + i * 5)),
            high=Decimal(str(3010 + i * 5)),
            low=Decimal(str(2990 + i * 5)),
            close=Decimal(str(3000 + i * 5)),
            volume=Decimal("50")
        )
        signals = strategy.on_bar(bar)

    print(f"\nAfter 25 bars:")
    print(f"  Resistance levels: {len(strategy.resistance_levels)}")
    print(f"  Support levels: {len(strategy.support_levels)}")
    if strategy.rsi_values:
        print(f"  Current RSI: {float(strategy.rsi_values[-1]):.1f}")


def demo_with_derivatives_data():
    """Usage with derivatives data (Open Interest, Funding Rate, Put/Call)."""
    print("\n\n" + "=" * 80)
    print("Demo 3: With Derivatives Data")
    print("=" * 80)

    strategy = BreakoutSetupDetector(symbol="BTCUSDT")

    # Process initial bars
    print("\nProcessing 25 bars of consolidation...")
    for i in range(25):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal(str(50000 + (i % 5) * 20)),
            volume=Decimal("100")
        )

        # Simulate derivatives data updates
        # Open Interest increasing (bullish signal)
        oi = Decimal(str(1000000 + i * 10000))
        strategy.update_derivatives_data(open_interest=oi)

        signals = strategy.on_bar(bar)

    # Set additional derivatives data
    strategy.update_derivatives_data(
        funding_rate=Decimal("0.0002"),  # Positive funding (0.02% per 8h)
        put_call_ratio=Decimal("0.65")   # Bullish (more calls than puts)
    )

    print(f"\nDerivatives Data:")
    print(f"  Open Interest change: {float(strategy._get_oi_change_pct() or 0) * 100:.1f}%")
    print(f"  Funding Rate: {float(strategy.current_funding_rate or 0) * 100:.3f}% per 8h")
    print(f"  Put/Call Ratio: {float(strategy.current_put_call_ratio or 0):.2f}")

    # Breakout with strong confirmation
    print("\nBreakout with all confirmations:")
    breakout_bar = Bar(
        timestamp=5000,
        open=Decimal("50000"),
        high=Decimal("51500"),
        low=Decimal("50000"),
        close=Decimal("51200"),  # Strong breakout
        volume=Decimal("350")    # 3.5x volume
    )
    signals = strategy.on_bar(breakout_bar)

    if signals:
        print(f"  ✅ Signal generated with derivatives confirmation!")
    else:
        print(f"  Setup detected but may need more confirmation")


def demo_detailed_setup_analysis():
    """Demonstrate detailed setup analysis output."""
    print("\n\n" + "=" * 80)
    print("Demo 4: Detailed Setup Analysis")
    print("=" * 80)

    strategy = BreakoutSetupDetector(symbol="BTCUSDT")

    # Build up market data
    print("\nBuilding market context...")
    for i in range(30):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal(str(50000 + i * 50)),
            high=Decimal(str(50200 + i * 50)),
            low=Decimal(str(49800 + i * 50)),
            close=Decimal(str(50000 + i * 50)),
            volume=Decimal(str(100 + i * 2))
        )
        strategy.on_bar(bar)

    # Analyze current setup (internal method for demo)
    latest_bar = Bar(
        timestamp=5000,
        open=Decimal("51500"),
        high=Decimal("52000"),
        low=Decimal("51400"),
        close=Decimal("51800"),
        volume=Decimal("300")
    )

    setup = strategy._analyze_breakout_setup(latest_bar)

    print(f"\n📊 Setup Analysis:")
    print(f"   Symbol: {setup.symbol}")
    print(f"   Setup Type: {setup.setup}")
    print(f"   Confidence: {float(setup.confidence):.2%}")
    print(f"   Action: {setup.action}")

    print(f"\n✅ Conditions Met ({len(setup.conditions_met)}):")
    for condition in setup.conditions_met:
        print(f"   • {condition}")

    if setup.conditions_failed:
        print(f"\n❌ Conditions Failed ({len(setup.conditions_failed)}):")
        for condition in setup.conditions_failed:
            print(f"   • {condition}")

    print(f"\n📈 Technical Metrics:")
    print(f"   Current Price: ${float(setup.current_price):,.2f}")
    if setup.resistance_level:
        print(f"   Resistance Level: ${float(setup.resistance_level):,.2f}")
    print(f"   Volume Ratio: {float(setup.volume_ratio):.2f}x")
    print(f"   RSI: {float(setup.rsi):.1f}")
    print(f"   MACD Histogram: {float(setup.macd_histogram):+.4f}")
    print(f"   BB Bandwidth: {float(setup.bb_bandwidth_pct):.2f}%")


def demo_risk_filter_scenarios():
    """Demonstrate risk filter scenarios."""
    print("\n\n" + "=" * 80)
    print("Demo 5: Risk Filter Scenarios")
    print("=" * 80)

    print("\nScenario 1: Overextended RSI (filtered)")
    print("-" * 40)
    strategy = BreakoutSetupDetector(symbol="BTCUSDT")

    # Create strong uptrend leading to overextended RSI
    for i in range(20):
        bar = Bar(
            timestamp=1000 + i,
            open=Decimal(str(50000 + i * 300)),
            high=Decimal(str(50500 + i * 300)),
            low=Decimal(str(49500 + i * 300)),
            close=Decimal(str(50000 + i * 300)),
            volume=Decimal("150")
        )
        strategy.on_bar(bar)

    if strategy.rsi_values:
        print(f"  Current RSI: {float(strategy.rsi_values[-1]):.1f}")
        print(f"  Threshold: {float(strategy.config.rsi_overbought_threshold):.1f}")

        if strategy.rsi_values[-1] > strategy.config.rsi_overbought_threshold:
            print("  ⚠️ Risk filter: RSI overextended - Entry filtered")
        else:
            print("  ✅ RSI within acceptable range")

    print("\nScenario 2: OI Spike with Flat Price (potential trap)")
    print("-" * 40)
    strategy2 = BreakoutSetupDetector(symbol="BTCUSDT")

    # Flat price action
    for i in range(10):
        bar = Bar(
            timestamp=2000 + i,
            open=Decimal("50000"),
            high=Decimal("50020"),
            low=Decimal("49980"),
            close=Decimal("50000"),
            volume=Decimal("100")
        )
        strategy2.on_bar(bar)

    # Large OI increase
    for i in range(24):
        oi = Decimal(str(1000000 + i * 30000))  # 72% increase
        strategy2.update_derivatives_data(open_interest=oi)

    oi_change = strategy2._get_oi_change_pct()
    print(f"  OI change: +{float(oi_change or 0) * 100:.1f}%")
    print(f"  Price range: 49980 - 50020 (0.04%)")
    print("  ⚠️ Risk filter: Large OI spike with flat price - Potential trap")


if __name__ == "__main__":
    # Run all demos
    demo_basic_usage()
    demo_with_custom_config()
    demo_with_derivatives_data()
    demo_detailed_setup_analysis()
    demo_risk_filter_scenarios()

    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("  • Strategy detects breakouts with multi-factor confirmation")
    print("  • Customizable thresholds for different trading styles")
    print("  • Derivatives data provides additional confirmation")
    print("  • Risk filters prevent overextended entries")
    print("  • Detailed setup analysis for debugging and optimization")
    print("\nNext Steps:")
    print("  • Backtest with historical data")
    print("  • Optimize parameters for your market/timeframe")
    print("  • Integrate with live exchange feed")
    print("  • Add position sizing and risk management")
