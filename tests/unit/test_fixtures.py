"""
Tests to validate fixture data integrity.

These tests ensure that:
1. All fixtures exist and are loadable
2. Fixture data has correct structure
3. Real market data is valid (no corrupt/fake data)
4. Fixtures match expected metadata
"""

import pytest
from datetime import datetime
from tests.fixtures.helpers import (
    load_fixture,
    get_binance_ohlcv_sample,
    get_coingecko_ohlcv_sample,
    get_multi_source_sample,
    get_anomaly_scenario,
    assert_valid_ohlcv,
    get_fixture_metadata,
    list_available_fixtures
)


class TestFixtureAvailability:
    """Test that all required fixtures exist."""

    def test_binance_1h_fixture_exists(self):
        """Test Binance 1h fixture can be loaded."""
        fixture = load_fixture("btc_usdt_binance_1h_sample.json")
        assert fixture is not None
        assert "metadata" in fixture
        assert "data" in fixture

    def test_binance_1d_fixture_exists(self):
        """Test Binance 1d fixture can be loaded."""
        fixture = load_fixture("btc_usdt_binance_1d_sample.json")
        assert fixture is not None

    def test_coingecko_fixture_exists(self):
        """Test CoinGecko fixture can be loaded."""
        fixture = load_fixture("btc_usd_coingecko_daily_sample.json")
        assert fixture is not None

    def test_multi_source_fixture_exists(self):
        """Test multi-source fixture can be loaded."""
        fixture = load_fixture("btc_usd_multi_source_sample.json")
        assert fixture is not None

    def test_anomalies_fixture_exists(self):
        """Test anomalies fixture can be loaded."""
        fixture = load_fixture("known_anomalies.json")
        assert fixture is not None


class TestBinanceFixtureIntegrity:
    """Test Binance.US fixture data integrity."""

    def test_binance_1h_has_correct_structure(self):
        """Test fixture has required metadata and data fields."""
        fixture = load_fixture("btc_usdt_binance_1h_sample.json")

        # Metadata
        assert "metadata" in fixture
        meta = fixture["metadata"]
        assert meta["source"] in ["binance", "binance_us"]  # Accept both versions
        assert meta["symbol"] == "BTCUSDT"
        assert meta["interval"] == "1h"
        assert "candle_count" in meta
        assert "fetched_at" in meta

        # Verify using US API if specified
        if "api_endpoint" in meta:
            assert "binance.us" in meta["api_endpoint"], "Should use Binance.US API for US access"

        # Data
        assert "data" in fixture
        assert len(fixture["data"]) == meta["candle_count"]

    def test_binance_1h_candles_are_valid(self):
        """Test all candles have valid OHLCV data."""
        candles = get_binance_ohlcv_sample("1h")

        # Should have ~168 candles (7 days hourly)
        assert len(candles) >= 160
        assert len(candles) <= 170

        # Validate OHLCV structure
        assert_valid_ohlcv(candles, min_count=160)

    def test_binance_1h_has_realistic_prices(self):
        """Test prices are in realistic range for BTC/USDT."""
        candles = get_binance_ohlcv_sample("1h")

        for candle in candles:
            # BTC price should be between $1K and $200K
            assert 1000 < candle["close"] < 200000
            assert 1000 < candle["open"] < 200000

            # Volume should be positive (not zero - exchange is active)
            assert candle["volume"] > 0

    def test_binance_1h_timestamps_are_sequential(self):
        """Test timestamps are in order and properly spaced."""
        candles = get_binance_ohlcv_sample("1h")

        for i in range(len(candles) - 1):
            current_ts = candles[i]["timestamp"]
            next_ts = candles[i + 1]["timestamp"]

            # Next timestamp should be after current
            assert next_ts > current_ts

            # Should be approximately 1 hour apart (3600000ms)
            # Allow some variance for exchange timing
            diff = next_ts - current_ts
            assert 3550000 < diff < 3650000  # ±50 seconds

    def test_binance_1d_has_daily_intervals(self):
        """Test daily fixture has correct interval."""
        candles = get_binance_ohlcv_sample("1d")

        assert len(candles) >= 25  # ~30 days

        # Check daily spacing (~86400000ms)
        for i in range(len(candles) - 1):
            diff = candles[i + 1]["timestamp"] - candles[i]["timestamp"]
            assert 86000000 < diff < 87000000  # ±1000 seconds


class TestCoinGeckoFixtureIntegrity:
    """Test CoinGecko fixture data integrity."""

    def test_coingecko_has_correct_structure(self):
        """Test fixture has required fields."""
        fixture = load_fixture("btc_usd_coingecko_daily_sample.json")

        assert "metadata" in fixture
        assert fixture["metadata"]["source"] == "coingecko"
        assert "data" in fixture

    def test_coingecko_candles_are_valid(self):
        """Test CoinGecko OHLCV is valid."""
        candles = get_coingecko_ohlcv_sample()

        # Should have at least 20 days (API may return less than requested 90)
        assert len(candles) >= 20

        # Validate structure (CoinGecko doesn't include volume)
        for candle in candles:
            assert "timestamp" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle

            # Valid prices
            assert candle["high"] >= candle["low"]
            assert candle["open"] > 0
            assert candle["close"] > 0


class TestMultiSourceFixture:
    """Test multi-source consensus fixture."""

    def test_multi_source_has_multiple_sources(self):
        """Test fixture contains data from multiple sources."""
        fixture = get_multi_source_sample()

        assert "data" in fixture
        sources = fixture["data"]

        # Should have at least 2 sources (Binance.US and CoinGecko)
        assert len(sources) >= 2

        # Should have both major sources
        assert "binance" in sources
        assert "coingecko" in sources

    def test_multi_source_prices_are_consistent(self):
        """Test prices from different sources are reasonably close."""
        fixture = get_multi_source_sample()
        sources = fixture["data"]

        prices = [source_data["price"] for source_data in sources.values()]

        # Calculate price range
        min_price = min(prices)
        max_price = max(prices)
        range_pct = (max_price - min_price) / min_price * 100

        # Prices should be within 5% of each other
        assert range_pct < 5.0, f"Price range too large: {range_pct:.2f}%"


class TestAnomalyFixtures:
    """Test known anomaly scenarios."""

    def test_flash_crash_scenario_exists(self):
        """Test flash crash scenario is available."""
        candles = get_anomaly_scenario("flash_crash")

        assert len(candles) >= 3
        # Second candle should have significant drop
        assert candles[1]["low"] < candles[0]["low"] * 0.9  # >10% drop

    def test_zero_volume_scenario_exists(self):
        """Test zero volume (exchange halt) scenario."""
        candles = get_anomaly_scenario("zero_volume")

        # Should have a candle with zero volume
        assert any(c["volume"] == 0 for c in candles)

    def test_price_spike_scenario_exists(self):
        """Test price spike (manipulation) scenario."""
        candles = get_anomaly_scenario("price_spike")

        # Should have a candle with extreme high
        max_high = max(c["high"] for c in candles)
        avg_close = sum(c["close"] for c in candles) / len(candles)

        # Spike should be >10x average
        assert max_high > avg_close * 10

    def test_data_gap_scenario_exists(self):
        """Test data gap scenario."""
        candles = get_anomaly_scenario("data_gap")

        # Should have exactly 2 candles with a large gap
        assert len(candles) == 2

        # Check the gap between the two candles
        diff = candles[1]["timestamp"] - candles[0]["timestamp"]
        # Gap should be > 5 minutes (300000ms)
        assert diff > 300000, f"Gap was only {diff}ms, expected >300000ms"


class TestFixtureHelpers:
    """Test fixture helper functions."""

    def test_list_available_fixtures(self):
        """Test listing available fixtures."""
        fixtures = list_available_fixtures()

        # Should have at least the 3 fixtures we generated
        assert len(fixtures) >= 3
        assert "btc_usd_coingecko_daily_sample.json" in fixtures
        assert "known_anomalies.json" in fixtures

    def test_get_fixture_metadata(self):
        """Test getting metadata without loading full data."""
        meta = get_fixture_metadata("btc_usd_coingecko_daily_sample.json")

        assert "source" in meta
        assert "candle_count" in meta
        assert "fetched_at" in meta

    def test_assert_valid_ohlcv_catches_invalid_data(self):
        """Test validation catches invalid OHLCV."""
        # Invalid: high < low
        invalid_candles = [
            {"timestamp": 1000, "open": 50000, "high": 49000, "low": 51000, "close": 50000}
        ]

        with pytest.raises(AssertionError, match="high < low"):
            assert_valid_ohlcv(invalid_candles)

    def test_assert_valid_ohlcv_catches_negative_prices(self):
        """Test validation catches negative prices."""
        invalid_candles = [
            {"timestamp": 1000, "open": -50000, "high": 51000, "low": 49000, "close": 50000}
        ]

        with pytest.raises(AssertionError, match="must be positive"):
            assert_valid_ohlcv(invalid_candles)


class TestFixtureFreshness:
    """Test that fixtures are not too old."""

    def test_coingecko_fixture_is_recent(self):
        """Test fixture was generated recently."""
        meta = get_fixture_metadata("btc_usd_coingecko_daily_sample.json")

        fetched_at = datetime.fromisoformat(meta["fetched_at"].replace("Z", "+00:00"))
        age_days = (datetime.now(fetched_at.tzinfo) - fetched_at).days

        # Fixture should be less than 180 days old
        assert age_days < 180, f"Fixture is {age_days} days old - please regenerate"
