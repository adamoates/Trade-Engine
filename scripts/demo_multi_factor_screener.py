"""
Demo: Multi-Factor Stock Screener

Shows how to find stocks matching multiple buy signals:
- Price breakout (20-day high)
- Volume surge (2x+ average)
- MA alignment (50/200 golden cross)
- MACD bullish crossover
- RSI momentum (40-70)
- Strong % gain today

Usage:
    python scripts/demo_multi_factor_screener.py

Output:
    Ranked list of stocks with signal matches and scores
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_engine.services.screening import MultiFactorScreener
from loguru import logger


def main():
    """Run multi-factor screener on S&P 500 stocks."""

    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )

    print("\n" + "="*80)
    print("Multi-Factor Stock Screener - Signal Matching Demo")
    print("="*80 + "\n")

    # Example universe (replace with your full list)
    # You can get S&P 500 tickers from: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
    universe = [
        # Tech giants
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        # Finance
        "JPM", "BAC", "WFC", "GS", "MS",
        # Healthcare
        "UNH", "JNJ", "PFE", "ABBV", "TMO",
        # Consumer
        "WMT", "HD", "NKE", "SBUX", "MCD",
        # Industrial
        "CAT", "BA", "GE", "LMT", "RTX"
    ]

    print(f"📊 Scanning {len(universe)} stocks for signal matches...\n")

    # Initialize screener
    screener = MultiFactorScreener(
        min_market_cap=Decimal("500_000_000"),  # $500M minimum
        min_price=Decimal("10.0"),              # $10 minimum
        lookback_days=20,                       # 20-day breakout
        ma_short=50,                            # 50-day MA
        ma_long=200                             # 200-day MA
    )

    # Run scan with your exact criteria
    matches = screener.scan_universe(
        symbols=universe,
        min_gain_percent=Decimal("8.0"),      # 8%+ gain today
        min_volume_ratio=Decimal("2.0"),      # 2x volume
        min_breakout_score=70,                 # Strong breakout
        min_signals_matched=4                  # At least 4/7 signals
    )

    # Display results
    print("\n" + "="*80)
    print(f"Found {len(matches)} stocks matching criteria")
    print("="*80 + "\n")

    if not matches:
        print("❌ No stocks matched all criteria")
        print("\nTry adjusting thresholds:")
        print("  - Lower min_gain_percent (e.g., 5%)")
        print("  - Lower min_volume_ratio (e.g., 1.5x)")
        print("  - Lower min_signals_matched (e.g., 3)")
        return

    # Print top matches
    print("🎯 Top Signal Matches (ranked by composite score):\n")

    for i, match in enumerate(matches[:10], 1):  # Top 10
        print(f"\n{'─'*80}")
        print(f"#{i}  {match.symbol}  -  Score: {match.composite_score}/100")
        print(f"{'─'*80}")

        print(f"\n📈 Price Action:")
        print(f"   Current Price:    ${match.price:.2f}")
        print(f"   Today's Gain:     ${match.gain_dollars:.2f} ({match.gain_percent:.1f}%)")

        print(f"\n📊 Volume:")
        print(f"   Volume Ratio:     {match.volume_ratio:.1f}x average")

        print(f"\n🎯 Technical Signals ({match.signals_matched}/7 matched):")
        print(f"   ✓ Breakout Score:  {match.breakout_score}/100")
        print(f"   ✓ Momentum Score:  {match.momentum_score}/100")
        print(f"   {'✓' if match.ma_alignment else '✗'} MA Alignment:   {'50MA > 200MA, Price > 50MA' if match.ma_alignment else 'Not aligned'}")
        print(f"   {'✓' if match.macd_bullish else '✗'} MACD Signal:    {'Bullish crossover' if match.macd_bullish else 'No crossover'}")
        print(f"   ✓ RSI Value:       {match.rsi_value:.1f} (40-70 optimal)")

        print(f"\n💡 Interpretation:")
        if match.composite_score >= 80:
            print("   🔥 STRONG BUY SIGNAL - Multiple confirmations")
        elif match.composite_score >= 60:
            print("   ✅ GOOD BUY SIGNAL - Solid setup")
        else:
            print("   ⚠️  MODERATE SIGNAL - Needs fundamental confirmation")

    # Summary statistics
    print("\n" + "="*80)
    print("Summary Statistics")
    print("="*80 + "\n")

    avg_score = sum(m.composite_score for m in matches) / len(matches)
    avg_gain = sum(m.gain_percent for m in matches) / Decimal(str(len(matches)))
    avg_volume = sum(m.volume_ratio for m in matches) / Decimal(str(len(matches)))

    print(f"Average Composite Score: {avg_score:.1f}/100")
    print(f"Average Gain:            {avg_gain:.1f}%")
    print(f"Average Volume Ratio:    {avg_volume:.1f}x")

    # Export recommendations
    print("\n" + "="*80)
    print("Next Steps")
    print("="*80 + "\n")

    print("1. Check fundamentals for top picks:")
    for match in matches[:5]:
        print(f"   - {match.symbol}: Recent news, earnings, catalysts?")

    print("\n2. Verify institutional flow:")
    print("   - Options activity (put/call ratio)")
    print("   - Dark pool prints")
    print("   - Insider buying")

    print("\n3. Set entry/exit levels:")
    for match in matches[:3]:
        stop_loss = match.price * Decimal("0.95")  # 5% stop
        target = match.price * Decimal("1.10")     # 10% target
        print(f"   - {match.symbol}: Entry ${match.price:.2f}, Stop ${stop_loss:.2f}, Target ${target:.2f}")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
