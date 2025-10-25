#!/usr/bin/env python3
"""
Demo script showing signal normalization in action.

This demonstrates how the SignalNormalizer builds up history over time
and improves signal quality.

Usage:
    python tools/demo_signal_normalization.py
"""

from mft.services.data.signal_normalizer import SignalNormalizer
from loguru import logger
import sys
import numpy as np

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def demo_zscore_normalization():
    """Demonstrate z-score normalization building history."""
    logger.info("=" * 60)
    logger.info("Z-SCORE NORMALIZATION DEMO")
    logger.info("=" * 60)
    logger.info("")

    normalizer = SignalNormalizer(method="zscore", lookback_days=30)

    # Simulate gas prices over time
    logger.info("Simulating 24 hours of gas price data (hourly samples)...")
    logger.info("")

    # Normal gas prices: 20-40 gwei with occasional spikes
    np.random.seed(42)
    normal_prices = np.random.normal(30, 5, 20)  # Mean=30, std=5
    spike_prices = [100, 120]  # Occasional spikes

    all_prices = list(normal_prices) + spike_prices

    logger.info("Building normalization history...")
    for i, price in enumerate(normal_prices):
        normalized = normalizer.normalize(price, "gas_price")
        if i % 5 == 0:  # Log every 5th sample
            logger.info(f"  Sample {i+1:2d}: {price:5.1f} gwei → normalized: {normalized:+.3f}")

    logger.info("")
    logger.success("✓ History built (20 samples)")
    logger.info("")

    # Get statistics
    stats = normalizer.get_signal_stats("gas_price")
    logger.info("📊 Historical Statistics:")
    logger.info(f"    Mean: {stats['mean']:.1f} gwei")
    logger.info(f"    Std:  {stats['std']:.1f} gwei")
    logger.info(f"    Min:  {stats['min']:.1f} gwei")
    logger.info(f"    Max:  {stats['max']:.1f} gwei")
    logger.info("")

    # Test normalization on various values
    logger.info("🧪 Testing normalization on various gas prices:")
    logger.info("")

    test_values = [
        (20.0, "Low gas (calm market)"),
        (30.0, "Normal gas (mean)"),
        (40.0, "Elevated gas"),
        (100.0, "EXTREME gas spike"),
        (150.0, "CRISIS-level gas")
    ]

    for value, description in test_values:
        normalized = normalizer.normalize(value, "gas_price")

        if normalized < -0.5:
            sentiment = "🟢 BULLISH (low gas, calm)"
        elif normalized < 0.0:
            sentiment = "⚪ NEUTRAL-BULLISH"
        elif normalized < 0.5:
            sentiment = "⚪ NEUTRAL-BEARISH"
        else:
            sentiment = "🔴 BEARISH (high gas, volatile)"

        logger.info(f"  {value:6.1f} gwei ({description:25s}) → {normalized:+.3f} {sentiment}")

    logger.info("")


def demo_percentile_normalization():
    """Demonstrate percentile normalization."""
    logger.info("=" * 60)
    logger.info("PERCENTILE NORMALIZATION DEMO")
    logger.info("=" * 60)
    logger.info("")

    normalizer = SignalNormalizer(method="percentile", lookback_days=30)

    # Build history
    logger.info("Building funding rate history...")
    funding_rates = [-0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015, 0.02, 0.025]

    for rate in funding_rates:
        normalizer.normalize(rate, "funding_rate")

    logger.success("✓ History built (9 samples)")
    logger.info("")

    # Get statistics
    stats = normalizer.get_signal_stats("funding_rate")
    logger.info("📊 Historical Statistics:")
    logger.info(f"    Mean: {stats['mean']:.4f} ({stats['mean']*100:.2f}%)")
    logger.info(f"    Min:  {stats['min']:.4f} ({stats['min']*100:.2f}%)")
    logger.info(f"    Max:  {stats['max']:.4f} ({stats['max']*100:.2f}%)")
    logger.info("")

    # Test normalization
    logger.info("🧪 Testing percentile normalization:")
    logger.info("")

    test_values = [
        (-0.03, "Extreme negative (shorts overleveraged)"),
        (-0.01, "Moderate negative"),
        (0.0, "Neutral"),
        (0.01, "Moderate positive"),
        (0.03, "Extreme positive (longs overleveraged)")
    ]

    for value, description in test_values:
        normalized = normalizer.normalize(value, "funding_rate")

        if normalized < -0.5:
            sentiment = "🟢 STRONG BULLISH (shorts squeezed)"
        elif normalized < 0.0:
            sentiment = "🟢 BULLISH"
        elif normalized < 0.5:
            sentiment = "🔴 BEARISH"
        else:
            sentiment = "🔴 STRONG BEARISH (longs squeezed)"

        logger.info(f"  {value:+.4f} ({description:40s}) → {normalized:+.3f} {sentiment}")

    logger.info("")


def demo_multiple_signals():
    """Demonstrate independent signal normalization."""
    logger.info("=" * 60)
    logger.info("MULTIPLE INDEPENDENT SIGNALS")
    logger.info("=" * 60)
    logger.info("")

    normalizer = SignalNormalizer(method="zscore")

    # Build different histories for different signals
    logger.info("Building histories for 3 different signals...")

    # Gas prices: 20-40 gwei
    for _ in range(20):
        normalizer.normalize(np.random.normal(30, 5), "gas_price")

    # Funding rates: -0.01 to +0.01
    for _ in range(20):
        normalizer.normalize(np.random.normal(0.0, 0.005), "funding_rate")

    # Liquidity: $1M to $10M
    for _ in range(20):
        normalizer.normalize(np.random.normal(5_000_000, 2_000_000), "liquidity_volume")

    logger.success("✓ Histories built")
    logger.info("")

    # Show statistics for all signals
    logger.info("📊 Statistics for all signals:")
    logger.info("")

    for signal_name in ["gas_price", "funding_rate", "liquidity_volume"]:
        stats = normalizer.get_signal_stats(signal_name)
        logger.info(f"  {signal_name:20s} | Mean: {stats['mean']:>12.2f} | Std: {stats['std']:>10.2f}")

    logger.info("")

    # Normalize new values
    logger.info("🧪 Normalizing current market conditions:")
    logger.info("")

    gas_norm = normalizer.normalize(50.0, "gas_price")
    funding_norm = normalizer.normalize(-0.015, "funding_rate")
    liquidity_norm = normalizer.normalize(3_000_000, "liquidity_volume")

    logger.info(f"  Gas price:  50.0 gwei       → {gas_norm:+.3f} (elevated)")
    logger.info(f"  Funding:    -0.0150 (-1.5%) → {funding_norm:+.3f} (shorts paying)")
    logger.info(f"  Liquidity:  $3.0M          → {liquidity_norm:+.3f} (below average)")
    logger.info("")

    # Combined signal
    combined_score = -(gas_norm) + (-funding_norm) + liquidity_norm  # Invert gas & funding
    logger.info(f"📈 Combined Signal Score: {combined_score:+.3f}")

    if combined_score > 0.5:
        logger.success("  → STRONG BUY")
    elif combined_score > 0.0:
        logger.info("  → WEAK BUY")
    elif combined_score > -0.5:
        logger.warning("  → WEAK SELL")
    else:
        logger.error("  → STRONG SELL")

    logger.info("")


def demo_history_evolution():
    """Show how normalization improves with more data."""
    logger.info("=" * 60)
    logger.info("NORMALIZATION QUALITY VS HISTORY SIZE")
    logger.info("=" * 60)
    logger.info("")

    logger.info("Testing how normalization quality improves over time...")
    logger.info("")

    normalizer = SignalNormalizer(method="zscore")

    # Simulate gas price data stream
    np.random.seed(42)
    gas_prices = np.random.normal(30, 5, 100)  # 100 samples

    checkpoints = [1, 5, 10, 20, 50, 100]
    test_value = 45.0  # High gas

    logger.info(f"Testing normalization of {test_value} gwei at different history sizes:")
    logger.info("")

    for i, price in enumerate(gas_prices, start=1):
        normalized = normalizer.normalize(price, "gas_price")

        if i in checkpoints:
            test_norm = normalizer.normalize(test_value, "gas_price")
            stats = normalizer.get_signal_stats("gas_price")

            logger.info(f"  After {i:3d} samples: normalized={test_norm:+.3f} | mean={stats['mean']:5.1f} | std={stats['std']:4.1f}")

    logger.info("")
    logger.success("✓ Normalization stabilizes after ~20-50 samples")
    logger.info("")


def main():
    """Run all demos."""
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 12 + "SIGNAL NORMALIZATION DEMO" + " " * 21 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")

    try:
        # Demo 1: Z-score normalization
        demo_zscore_normalization()

        # Demo 2: Percentile normalization
        demo_percentile_normalization()

        # Demo 3: Multiple independent signals
        demo_multiple_signals()

        # Demo 4: History evolution
        demo_history_evolution()

        logger.info("=" * 60)
        logger.success("✓ ALL DEMOS COMPLETE")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review app/data/signal_normalizer.py for implementation")
        logger.info("  2. Run pytest tests/unit/test_signal_normalizer.py -v")
        logger.info("  3. Integrate with Web3 signals: Web3DataSource(normalize=True)")
        logger.info("  4. Run for 24-48 hours to build production-quality history")
        logger.info("")

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
