#!/usr/bin/env python3
"""
Demo script showing Web3 signals in action with REAL data.

This script fetches live on-chain data from free public APIs and
demonstrates how to use it for trading signals.

Usage:
    python tools/demo_web3_signals.py
"""

from mft.services.data.web3_signals import Web3DataSource, get_web3_signal
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def demo_individual_signals():
    """Demonstrate fetching individual signals."""
    logger.info("=" * 60)
    logger.info("FETCHING INDIVIDUAL WEB3 SIGNALS")
    logger.info("=" * 60)
    logger.info("")

    source = Web3DataSource(timeout=10)

    # 1. Gas Prices
    logger.info("1/3: Fetching Ethereum gas prices (Etherscan API)...")
    gas = source.get_gas_prices()

    if gas:
        logger.success(f"✓ Gas prices retrieved:")
        logger.info(f"    Safe: {gas.safe_gas_price} gwei")
        logger.info(f"    Standard: {gas.propose_gas_price} gwei")
        logger.info(f"    Fast: {gas.fast_gas_price} gwei")

        if gas.propose_gas_price > 100:
            logger.warning(f"    ⚠️  HIGH GAS - Avoid trading (volatility)")
        elif gas.propose_gas_price > 50:
            logger.info(f"    ⚡ Moderate gas - Normal activity")
        else:
            logger.success(f"    ✓ Low gas - Calm market")
    else:
        logger.error("✗ Failed to fetch gas prices")

    logger.info("")

    # 2. DEX Liquidity
    logger.info("2/3: Fetching DEX liquidity (The Graph - Uniswap V3)...")
    liquidity = source.get_dex_liquidity("WBTC/USDC")

    if liquidity:
        logger.success(f"✓ DEX liquidity retrieved:")
        logger.info(f"    Pool: {liquidity.token0}/{liquidity.token1}")
        logger.info(f"    Liquidity: {liquidity.liquidity:,.0f}")
        logger.info(f"    24h Volume: ${liquidity.volume_24h_usd:,.2f}")

        if liquidity.volume_24h_usd < 1_000_000:
            logger.warning(f"    ⚠️  LOW VOLUME - Thin liquidity")
        else:
            logger.success(f"    ✓ Good liquidity")
    else:
        logger.error("✗ Failed to fetch DEX liquidity")

    logger.info("")

    # 3. Funding Rate
    logger.info("3/3: Fetching perpetual funding rate (dYdX API)...")
    funding = source.get_funding_rate("BTC-USD")

    if funding:
        logger.success(f"✓ Funding rate retrieved:")
        logger.info(f"    Rate: {funding.funding_rate:.4f} ({funding.funding_rate * 100:.2f}%)")
        logger.info(f"    Next funding: {funding.next_funding_time.strftime('%Y-%m-%d %H:%M UTC')}")

        if funding.funding_rate > 0.01:
            logger.warning(f"    ⚠️  POSITIVE FUNDING - Overleveraged longs (bearish)")
        elif funding.funding_rate < -0.01:
            logger.success(f"    ✓ NEGATIVE FUNDING - Overleveraged shorts (bullish)")
        else:
            logger.info(f"    ⚡ Neutral funding - Balanced market")
    else:
        logger.error("✗ Failed to fetch funding rate")

    logger.info("")


def demo_combined_signal():
    """Demonstrate combined signal generation."""
    logger.info("=" * 60)
    logger.info("GENERATING COMBINED WEB3 SIGNAL")
    logger.info("=" * 60)
    logger.info("")

    logger.info("Fetching all signals and combining into one score...")
    signal = get_web3_signal()

    logger.success(f"✓ Combined signal generated:")
    logger.info("")

    # Show score breakdown
    logger.info(f"📊 Score: {signal.score:+d} (range: -3 to +3)")

    if signal.score > 0:
        logger.success(f"    → Bullish signals dominant")
    elif signal.score < 0:
        logger.error(f"    → Bearish signals dominant")
    else:
        logger.info(f"    → Neutral / conflicting signals")

    # Show final signal
    logger.info("")
    if signal.signal == "BUY":
        logger.success(f"🟢 FINAL SIGNAL: {signal.signal}")
    elif signal.signal == "SELL":
        logger.error(f"🔴 FINAL SIGNAL: {signal.signal}")
    else:
        logger.info(f"⚪ FINAL SIGNAL: {signal.signal}")

    # Show confidence
    logger.info(f"📈 Confidence: {signal.confidence:.0%} ({int(signal.confidence * 3)}/3 sources)")

    if signal.confidence >= 0.75:
        logger.success(f"    → High confidence (multiple sources agree)")
    elif signal.confidence >= 0.5:
        logger.warning(f"    → Medium confidence")
    else:
        logger.warning(f"    → Low confidence (limited data)")

    logger.info("")

    # Show individual signal contributions
    logger.info("📋 Signal Breakdown:")

    if signal.gas_data:
        if signal.gas_data.propose_gas_price > 100:
            logger.warning(f"    Gas: {signal.gas_data.propose_gas_price:.0f} gwei → -1 (avoid volatility)")
        else:
            logger.info(f"    Gas: {signal.gas_data.propose_gas_price:.0f} gwei → 0 (normal)")

    if signal.funding_data:
        rate = signal.funding_data.funding_rate
        if rate < -0.01:
            logger.success(f"    Funding: {rate:.4f} → +1 (bullish)")
        elif rate > 0.01:
            logger.error(f"    Funding: {rate:.4f} → -1 (bearish)")
        else:
            logger.info(f"    Funding: {rate:.4f} → 0 (neutral)")

    if signal.liquidity_data:
        vol = signal.liquidity_data.volume_24h_usd
        if vol < 1_000_000:
            logger.warning(f"    Liquidity: ${vol:,.0f} → -1 (low volume)")
        else:
            logger.info(f"    Liquidity: ${vol:,.0f} → 0 (adequate)")

    logger.info("")


def demo_volatility_check():
    """Demonstrate high volatility detection."""
    logger.info("=" * 60)
    logger.info("VOLATILITY CHECK")
    logger.info("=" * 60)
    logger.info("")

    source = Web3DataSource()

    logger.info("Checking for high volatility conditions...")
    is_volatile = source.is_high_volatility()

    if is_volatile:
        logger.error("⚠️  HIGH VOLATILITY DETECTED")
        logger.warning("    → Skip trading - market too chaotic")
        logger.warning("    → Wait for conditions to normalize")
    else:
        logger.success("✓ Normal market conditions")
        logger.info("    → Safe to trade")

    logger.info("")


def demo_trading_integration():
    """Demonstrate how to integrate with trading logic."""
    logger.info("=" * 60)
    logger.info("TRADING INTEGRATION EXAMPLE")
    logger.info("=" * 60)
    logger.info("")

    # Simulate L2 order book signal
    l2_signal = "BUY"  # Pretend L2 imbalance says buy
    l2_confidence = 0.8

    logger.info(f"L2 Order Book Signal: {l2_signal} (confidence: {l2_confidence:.0%})")

    # Get Web3 signal
    web3_signal = get_web3_signal()
    logger.info(f"Web3 On-Chain Signal: {web3_signal.signal} (confidence: {web3_signal.confidence:.0%})")
    logger.info("")

    # Combined decision logic
    logger.info("Decision Logic:")

    if l2_signal == web3_signal.signal and web3_signal.confidence >= 0.67:
        logger.success(f"✓ BOTH SIGNALS AGREE - Execute trade with FULL size")
        logger.info(f"    L2: {l2_signal} | Web3: {web3_signal.signal}")
        logger.info(f"    Combined confidence: HIGH")
        action = "EXECUTE_FULL"

    elif web3_signal.confidence < 0.5:
        logger.warning(f"⚠️  LOW WEB3 CONFIDENCE - Execute with REDUCED size")
        logger.info(f"    Web3 data limited ({int(web3_signal.confidence * 3)}/3 sources)")
        action = "EXECUTE_HALF"

    elif l2_signal != web3_signal.signal:
        logger.error(f"✗ SIGNALS CONFLICT - Skip trade")
        logger.info(f"    L2: {l2_signal} | Web3: {web3_signal.signal}")
        action = "SKIP_TRADE"

    else:
        logger.info(f"⚡ Proceed with caution")
        action = "EXECUTE_HALF"

    logger.info("")
    logger.info(f"→ Final Action: {action}")
    logger.info("")


def main():
    """Run all demos."""
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 10 + "WEB3 SIGNALS DEMO - REAL DATA" + " " * 19 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    logger.info("Fetching live on-chain data from free public APIs...")
    logger.info("")

    try:
        # Demo individual signals
        demo_individual_signals()

        # Demo combined signal
        demo_combined_signal()

        # Demo volatility check
        demo_volatility_check()

        # Demo trading integration
        demo_trading_integration()

        logger.info("=" * 60)
        logger.success("✓ DEMO COMPLETE")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review app/data/web3_signals.py for implementation")
        logger.info("  2. Read docs/guides/web3-signals.md for usage guide")
        logger.info("  3. Run pytest tests/unit/test_web3_signals.py -v")
        logger.info("  4. Integrate into your trading strategy")
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
