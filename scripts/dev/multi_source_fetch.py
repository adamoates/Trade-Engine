#!/usr/bin/env python3
"""
Multi-source data fetcher with cross-validation.

Fetches market data from multiple sources (Yahoo Finance, CoinGecko, Binance)
and cross-validates prices to detect anomalies.

Educational tool for demonstrating data quality verification.
Not financial advice - for educational purposes only.

Usage:
    # Fetch BTC price from all sources
    python tools/multi_source_fetch.py --symbol BTC --quote

    # Fetch historical data with cross-validation
    python tools/multi_source_fetch.py --symbol AAPL --interval 1d --days 7

    # Show data quality metrics
    python tools/multi_source_fetch.py --symbol ETH --quality --days 30
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.data.types import AssetType
from app.data.source_yahoo import YahooFinanceSource
from app.data.source_coingecko import CoinGeckoSource
from app.data.aggregator import DataAggregator, print_disclaimer


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-source market data fetcher with cross-validation"
    )
    parser.add_argument("--symbol", required=True, help="Symbol to fetch (BTC, AAPL, SPY, etc.)")
    parser.add_argument("--asset-type", choices=["crypto", "stock", "etf", "index"],
                        default="crypto", help="Asset type (default: crypto)")
    parser.add_argument("--quote", action="store_true", help="Fetch real-time quote")
    parser.add_argument("--interval", default="1d", help="Candle interval (1d, 1h, etc.)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to fetch (default: 7)")
    parser.add_argument("--quality", action="store_true", help="Show data quality metrics")
    parser.add_argument("--no-disclaimer", action="store_true", help="Skip disclaimer")

    args = parser.parse_args()

    # Print disclaimer
    if not args.no_disclaimer:
        print_disclaimer()
        print()

    # Convert asset type
    asset_type_map = {
        "crypto": AssetType.CRYPTO,
        "stock": AssetType.STOCK,
        "etf": AssetType.ETF,
        "index": AssetType.INDEX
    }
    asset_type = asset_type_map[args.asset_type]

    try:
        # Initialize sources
        logger.info("Initializing data sources...")
        sources = []

        # Yahoo Finance (stocks, ETFs, indices, crypto)
        try:
            yahoo = YahooFinanceSource()
            if yahoo.validate_connection():
                sources.append(yahoo)
                logger.info("✅ Yahoo Finance connected")
            else:
                logger.warning("⚠️ Yahoo Finance connection failed")
        except Exception as e:
            logger.warning(f"⚠️ Yahoo Finance not available: {e}")

        # CoinGecko (crypto only)
        if asset_type == AssetType.CRYPTO:
            try:
                coingecko = CoinGeckoSource()
                if coingecko.validate_connection():
                    sources.append(coingecko)
                    logger.info("✅ CoinGecko connected")
                else:
                    logger.warning("⚠️ CoinGecko connection failed")
            except Exception as e:
                logger.warning(f"⚠️ CoinGecko not available: {e}")

        if not sources:
            logger.error("❌ No data sources available!")
            return 1

        # Create aggregator
        aggregator = DataAggregator(sources)

        # Normalize symbol
        normalized_symbols = {}
        for source in sources:
            try:
                normalized = source.normalize_symbol(args.symbol, asset_type)
                normalized_symbols[source.source_type.value] = normalized
                logger.debug(f"Symbol normalized for {source.source_type.value}: {normalized}")
            except Exception as e:
                logger.error(f"Failed to normalize symbol for {source.source_type.value}: {e}")

        # Real-time quote
        if args.quote:
            logger.info(f"\nFetching real-time quote for {args.symbol}...")

            # Use first normalized symbol
            symbol_to_use = list(normalized_symbols.values())[0]

            quote, validation = aggregator.fetch_quote_consensus(
                symbol=symbol_to_use,
                min_sources=1
            )

            print(f"\n📊 Real-Time Quote: {args.symbol}")
            print(f"   Price:    ${quote.price:.2f}")
            if quote.bid and quote.ask:
                print(f"   Bid/Ask:  ${quote.bid:.2f} / ${quote.ask:.2f}")
                if quote.spread:
                    print(f"   Spread:   {quote.spread:.2f} bps")
            if quote.volume_24h:
                print(f"   Volume:   {quote.volume_24h:,.0f}")

            print(f"\n{validation}")

            if validation.anomalies:
                print("\n⚠️ Price Anomalies Detected:")
                for source, price, reason in validation.anomalies:
                    print(f"   {source.value}: ${price:.2f} - {reason}")

        # Historical data with quality metrics
        elif args.quality:
            logger.info(f"\nFetching quality metrics for {args.symbol}...")

            end = datetime.utcnow()
            start = end - timedelta(days=args.days)

            # Use first normalized symbol
            symbol_to_use = list(normalized_symbols.values())[0]

            metrics = aggregator.get_quality_metrics(
                symbol=symbol_to_use,
                interval=args.interval,
                start=start,
                end=end
            )

            print(f"\n📊 Data Quality Report: {args.symbol} ({args.days} days)")
            print("=" * 70)

            for source_type, quality in metrics.items():
                print(f"\n{source_type.value.upper()}:")
                print(f"   Rows:              {quality.rows}")
                print(f"   Zero Volume Bars:  {quality.zero_volume_bars}")
                print(f"   Price Anomalies:   {quality.price_anomalies}")
                print(f"   Duplicates:        {quality.duplicate_timestamps}")
                print(f"   Quality Score:     {quality.quality_score:.1f}/100")

                if quality.quality_score < 80:
                    print(f"   ⚠️ LOW QUALITY - Use with caution!")
                elif quality.quality_score >= 95:
                    print(f"   ✅ EXCELLENT QUALITY")

        # Historical OHLCV
        else:
            logger.info(f"\nFetching {args.days}d of {args.interval} candles for {args.symbol}...")

            end = datetime.utcnow()
            start = end - timedelta(days=args.days)

            # Use first normalized symbol
            symbol_to_use = list(normalized_symbols.values())[0]

            candles, validations = aggregator.fetch_ohlcv_consensus(
                symbol=symbol_to_use,
                interval=args.interval,
                start=start,
                end=end,
                min_sources=1
            )

            print(f"\n📊 Historical Data: {args.symbol}")
            print(f"   Candles:  {len(candles)}")
            print(f"   Sources:  {len(sources)}")

            # Show first 5 and last 5 candles
            print(f"\n   First 5:")
            for candle in candles[:5]:
                print(f"      {candle}")

            if len(candles) > 10:
                print(f"\n   Last 5:")
                for candle in candles[-5:]:
                    print(f"      {candle}")

            # Show validation summary
            anomaly_count = sum(1 for v in validations if not v.reliable)
            if anomaly_count > 0:
                print(f"\n⚠️ {anomaly_count} anomalies detected during cross-validation")

        logger.info("\n✅ Done!")
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted by user")
        return 130

    except Exception as e:
        logger.exception(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
