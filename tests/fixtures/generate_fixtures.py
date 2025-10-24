#!/usr/bin/env python3
"""
Generate test fixtures from real historical cryptocurrency data.

This script fetches actual market data from free public APIs and saves
it as JSON fixtures for use in tests. Using real data prevents false
positives and ensures tests validate against actual market conditions.

Usage:
    python tests/fixtures/generate_fixtures.py
    python tests/fixtures/generate_fixtures.py --refresh-all
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any
import requests
from loguru import logger

# Configure paths
FIXTURES_DIR = Path(__file__).parent
OUTPUT_DIR = FIXTURES_DIR


class FixtureGenerator:
    """Generates test fixtures from real historical data."""

    # IMPORTANT: Always use Binance.US API for US-based access
    # The international Binance.com API returns HTTP 451 in the US
    BINANCE_API_BASE = "https://api.binance.us"  # US version
    # BINANCE_API_BASE = "https://api.binance.com"  # International (blocked in US)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MFT-Test-Fixtures/1.0"})

        # Verify we're using the US API
        if "binance.us" not in self.BINANCE_API_BASE:
            logger.warning(
                "⚠️  WARNING: Using international Binance API - may be blocked in US. "
                "Set BINANCE_API_BASE to 'https://api.binance.us' for US access."
            )

    def fetch_binance_ohlcv(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        limit: int = 168  # 7 days of hourly data
    ) -> Dict[str, Any]:
        """
        Fetch real OHLCV data from Binance.US public API.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Candlestick interval (1m, 5m, 1h, 1d)
            limit: Number of candles to fetch

        Returns:
            Dict with metadata and candle data
        """
        logger.info(f"Fetching Binance.US {symbol} {interval} data ({limit} candles)...")

        url = f"{self.BINANCE_API_BASE}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()

        raw_data = response.json()

        # Transform to fixture format
        candles = []
        for kline in raw_data:
            candles.append({
                "timestamp": kline[0],  # Open time
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5])
            })

        fixture = {
            "metadata": {
                "source": "binance_us",
                "symbol": symbol,
                "interval": interval,
                "start_timestamp": candles[0]["timestamp"],
                "end_timestamp": candles[-1]["timestamp"],
                "candle_count": len(candles),
                "api_endpoint": self.BINANCE_API_BASE,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            },
            "data": candles
        }

        logger.success(f"Fetched {len(candles)} candles from Binance.US")
        return fixture

    def fetch_coingecko_ohlcv(
        self,
        coin_id: str = "bitcoin",
        vs_currency: str = "usd",
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Fetch real OHLCV data from CoinGecko public API.

        Args:
            coin_id: CoinGecko coin ID (e.g., bitcoin, ethereum)
            vs_currency: Quote currency (usd, eur, etc.)
            days: Number of days of historical data

        Returns:
            Dict with metadata and candle data
        """
        logger.info(f"Fetching CoinGecko {coin_id}/{vs_currency} data ({days} days)...")

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {
            "vs_currency": vs_currency,
            "days": days
        }

        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()

        raw_data = response.json()

        # Transform to fixture format
        candles = []
        for ohlc in raw_data:
            candles.append({
                "timestamp": ohlc[0],
                "open": float(ohlc[1]),
                "high": float(ohlc[2]),
                "low": float(ohlc[3]),
                "close": float(ohlc[4])
            })

        fixture = {
            "metadata": {
                "source": "coingecko",
                "coin_id": coin_id,
                "vs_currency": vs_currency,
                "days": days,
                "candle_count": len(candles),
                "fetched_at": datetime.now(timezone.utc).isoformat()
            },
            "data": candles
        }

        logger.success(f"Fetched {len(candles)} candles from CoinGecko")
        return fixture

    def fetch_multi_source_consensus(self) -> Dict[str, Any]:
        """
        Fetch same data point from multiple sources for cross-validation testing.

        Returns:
            Dict with data from multiple sources at same timestamp
        """
        logger.info("Fetching multi-source consensus data...")

        # Get current price from multiple sources
        sources = {}

        # Binance.US
        try:
            url = f"{self.BINANCE_API_BASE}/api/v3/ticker/price"
            response = self.session.get(url, params={"symbol": "BTCUSDT"}, timeout=10)
            response.raise_for_status()
            data = response.json()
            sources["binance"] = {
                "price": float(data["price"]),
                "timestamp": int(time.time() * 1000)
            }
        except Exception as e:
            logger.warning(f"Binance.US fetch failed: {e}")

        time.sleep(1)  # Rate limiting

        # CoinGecko
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "bitcoin",
                "vs_currencies": "usd"
            }
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            sources["coingecko"] = {
                "price": float(data["bitcoin"]["usd"]),
                "timestamp": int(time.time() * 1000)
            }
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e}")

        fixture = {
            "metadata": {
                "description": "Multi-source price data for cross-validation testing",
                "symbol": "BTC/USD",
                "sources_count": len(sources),
                "fetched_at": datetime.now(timezone.utc).isoformat()
            },
            "data": sources
        }

        logger.success(f"Fetched prices from {len(sources)} sources")
        return fixture

    def create_known_anomaly_fixtures(self) -> Dict[str, Any]:
        """
        Create fixtures with known market anomalies for edge case testing.

        Returns:
            Dict with various anomaly scenarios
        """
        logger.info("Creating known anomaly fixtures...")

        anomalies = {
            "metadata": {
                "description": "Known market anomalies and edge cases for testing",
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            "scenarios": {
                "flash_crash": {
                    "description": "Simulated flash crash - 20% drop in 1 minute",
                    "candles": [
                        {"timestamp": 1000000, "open": 50000, "high": 50100, "low": 49900, "close": 50000, "volume": 100},
                        {"timestamp": 1000060, "open": 50000, "high": 50000, "low": 40000, "close": 40000, "volume": 5000},  # Crash
                        {"timestamp": 1000120, "open": 40000, "high": 45000, "low": 40000, "close": 44000, "volume": 2000},  # Recovery
                    ]
                },
                "zero_volume": {
                    "description": "Exchange halt - zero volume period",
                    "candles": [
                        {"timestamp": 2000000, "open": 50000, "high": 50100, "low": 49900, "close": 50000, "volume": 100},
                        {"timestamp": 2000060, "open": 50000, "high": 50000, "low": 50000, "close": 50000, "volume": 0},  # Halt
                        {"timestamp": 2000120, "open": 50000, "high": 50100, "low": 49900, "close": 50050, "volume": 150},
                    ]
                },
                "price_spike": {
                    "description": "Manipulation spike - brief 100x price",
                    "candles": [
                        {"timestamp": 3000000, "open": 50000, "high": 50100, "low": 49900, "close": 50000, "volume": 100},
                        {"timestamp": 3000060, "open": 50000, "high": 5000000, "low": 50000, "close": 50100, "volume": 1},  # Spike
                        {"timestamp": 3000120, "open": 50100, "high": 50200, "low": 50000, "close": 50050, "volume": 120},
                    ]
                },
                "data_gap": {
                    "description": "Missing data - gap in timestamps",
                    "candles": [
                        {"timestamp": 4000000, "open": 50000, "high": 50100, "low": 49900, "close": 50000, "volume": 100},
                        # 10-minute gap (600000ms)
                        {"timestamp": 4600000, "open": 51000, "high": 51100, "low": 50900, "close": 51000, "volume": 150},
                    ]
                }
            }
        }

        logger.success("Created anomaly fixtures")
        return anomalies

    def save_fixture(self, fixture: Dict[str, Any], filename: str):
        """Save fixture to JSON file."""
        output_path = OUTPUT_DIR / filename

        with open(output_path, 'w') as f:
            json.dump(fixture, f, indent=2)

        logger.success(f"Saved fixture: {output_path}")

    def generate_all(self):
        """Generate all test fixtures."""
        logger.info("=" * 60)
        logger.info("GENERATING TEST FIXTURES FROM REAL HISTORICAL DATA")
        logger.info("=" * 60)
        logger.info("")

        success_count = 0
        total_count = 5

        # 1. Binance hourly data (7 days)
        try:
            logger.info("1/5: Binance BTC/USDT hourly data...")
            binance_1h = self.fetch_binance_ohlcv("BTCUSDT", "1h", 168)
            self.save_fixture(binance_1h, "btc_usdt_binance_1h_sample.json")
            success_count += 1
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Binance 1h fetch failed: {e}")

        # 2. Binance daily data (30 days)
        try:
            logger.info("2/5: Binance BTC/USDT daily data...")
            binance_1d = self.fetch_binance_ohlcv("BTCUSDT", "1d", 30)
            self.save_fixture(binance_1d, "btc_usdt_binance_1d_sample.json")
            success_count += 1
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Binance 1d fetch failed: {e}")

        # 3. CoinGecko daily data (90 days)
        try:
            logger.info("3/5: CoinGecko BTC/USD daily data...")
            coingecko_btc = self.fetch_coingecko_ohlcv("bitcoin", "usd", 90)
            self.save_fixture(coingecko_btc, "btc_usd_coingecko_daily_sample.json")
            success_count += 1
            time.sleep(1)
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e}")

        # 4. Multi-source consensus
        try:
            logger.info("4/5: Multi-source consensus data...")
            multi_source = self.fetch_multi_source_consensus()
            self.save_fixture(multi_source, "btc_usd_multi_source_sample.json")
            success_count += 1
        except Exception as e:
            logger.warning(f"Multi-source fetch failed: {e}")

        # 5. Known anomalies (always works - synthetic data)
        try:
            logger.info("5/5: Known anomaly fixtures...")
            anomalies = self.create_known_anomaly_fixtures()
            self.save_fixture(anomalies, "known_anomalies.json")
            success_count += 1
        except Exception as e:
            logger.warning(f"Anomaly creation failed: {e}")

        logger.info("")
        logger.info("=" * 60)
        if success_count == total_count:
            logger.success(f"✓ ALL {total_count} FIXTURES GENERATED SUCCESSFULLY")
        elif success_count > 0:
            logger.warning(f"⚠ PARTIAL SUCCESS: {success_count}/{total_count} fixtures generated")
        else:
            logger.error(f"✗ FAILED: No fixtures generated")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Fixtures saved to: tests/fixtures/")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review generated fixtures")
        logger.info("  2. Run: pytest tests/unit/test_fixtures.py -v")
        logger.info("  3. Update your tests to use these fixtures")
        logger.info("")


def main():
    """Main entry point."""
    import sys

    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    generator = FixtureGenerator()
    generator.generate_all()


if __name__ == "__main__":
    main()
