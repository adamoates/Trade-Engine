"""
Fixture helper utilities for loading historical test data.

These utilities make it easy to load real historical cryptocurrency
data in tests, replacing mocked responses with actual market data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


# Fixture directory
FIXTURES_DIR = Path(__file__).parent


def load_fixture(filename: str) -> Dict[str, Any]:
    """
    Load a JSON fixture file.

    Args:
        filename: Name of fixture file (e.g., "btc_usdt_binance_1h_sample.json")

    Returns:
        Dict containing fixture metadata and data

    Raises:
        FileNotFoundError: If fixture file doesn't exist

    Example:
        >>> fixture = load_fixture("btc_usdt_binance_1h_sample.json")
        >>> candles = fixture["data"]
        >>> assert len(candles) == fixture["metadata"]["candle_count"]
    """
    fixture_path = FIXTURES_DIR / filename

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Fixture not found: {filename}\n"
            f"Run: python tests/fixtures/generate_fixtures.py"
        )

    with open(fixture_path) as f:
        return json.load(f)


def get_binance_ohlcv_sample(interval: str = "1h") -> List[Dict[str, Any]]:
    """
    Get Binance OHLCV sample data.

    Args:
        interval: Candle interval (1h or 1d)

    Returns:
        List of candle dicts with real Binance data

    Example:
        >>> candles = get_binance_ohlcv_sample("1h")
        >>> assert all("timestamp" in c for c in candles)
        >>> assert all(c["volume"] > 0 for c in candles)
    """
    if interval == "1h":
        fixture = load_fixture("btc_usdt_binance_1h_sample.json")
    elif interval == "1d":
        fixture = load_fixture("btc_usdt_binance_1d_sample.json")
    else:
        raise ValueError(f"Unsupported interval: {interval}")

    return fixture["data"]


def get_coingecko_ohlcv_sample() -> List[Dict[str, Any]]:
    """
    Get CoinGecko OHLCV sample data.

    Returns:
        List of candle dicts with real CoinGecko data
    """
    fixture = load_fixture("btc_usd_coingecko_daily_sample.json")
    return fixture["data"]


def get_multi_source_sample() -> Dict[str, Any]:
    """
    Get multi-source consensus sample.

    Returns:
        Dict with prices from multiple sources at same timestamp

    Example:
        >>> data = get_multi_source_sample()
        >>> assert "binance" in data["data"]
        >>> assert "coingecko" in data["data"]
    """
    fixture = load_fixture("btc_usd_multi_source_sample.json")
    return fixture


def get_anomaly_scenario(scenario: str) -> List[Dict[str, Any]]:
    """
    Get known anomaly scenario for edge case testing.

    Args:
        scenario: Anomaly type (flash_crash, zero_volume, price_spike, data_gap)

    Returns:
        List of candles demonstrating the anomaly

    Example:
        >>> crash = get_anomaly_scenario("flash_crash")
        >>> assert crash[1]["low"] < crash[0]["low"] * 0.9  # 10%+ drop
    """
    fixture = load_fixture("known_anomalies.json")

    if scenario not in fixture["scenarios"]:
        available = list(fixture["scenarios"].keys())
        raise ValueError(
            f"Unknown scenario: {scenario}\n"
            f"Available: {available}"
        )

    return fixture["scenarios"][scenario]["candles"]


def mock_binance_klines_response(interval: str = "1h") -> List[List]:
    """
    Get real Binance klines in API response format.

    This returns actual Binance data formatted as the API returns it,
    suitable for mocking requests.get().json()

    Args:
        interval: Candle interval (1h or 1d)

    Returns:
        List of klines in Binance API format

    Example:
        >>> with patch('requests.get') as mock_get:
        ...     mock_get.return_value.json.return_value = mock_binance_klines_response("1h")
        ...     # Test with real API response structure
    """
    candles = get_binance_ohlcv_sample(interval)

    # Convert to Binance API format
    klines = []
    for candle in candles:
        klines.append([
            candle["timestamp"],          # Open time
            str(candle["open"]),           # Open
            str(candle["high"]),           # High
            str(candle["low"]),            # Low
            str(candle["close"]),          # Close
            str(candle["volume"]),         # Volume
            candle["timestamp"] + 59999,   # Close time
            "0",                           # Quote volume
            100,                           # Number of trades
            "0",                           # Taker buy volume
            "0",                           # Taker buy quote volume
            "0"                            # Ignore
        ])

    return klines


def mock_coingecko_ohlc_response() -> List[List]:
    """
    Get real CoinGecko OHLC in API response format.

    Returns:
        List of OHLC in CoinGecko API format

    Example:
        >>> with patch('requests.get') as mock_get:
        ...     mock_get.return_value.json.return_value = mock_coingecko_ohlc_response()
        ...     # Test with real API response structure
    """
    candles = get_coingecko_ohlcv_sample()

    # Convert to CoinGecko API format
    ohlc = []
    for candle in candles:
        ohlc.append([
            candle["timestamp"],
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"]
        ])

    return ohlc


def assert_valid_ohlcv(candles: List[Dict[str, Any]], min_count: int = 1):
    """
    Assert that OHLCV data is valid.

    Checks:
    - Has minimum number of candles
    - All required fields present
    - Prices are positive
    - High >= Low
    - High >= Open, Close
    - Low <= Open, Close

    Args:
        candles: List of OHLCV candle dicts
        min_count: Minimum number of candles expected

    Raises:
        AssertionError: If data is invalid

    Example:
        >>> candles = get_binance_ohlcv_sample("1h")
        >>> assert_valid_ohlcv(candles, min_count=100)
    """
    assert len(candles) >= min_count, f"Expected at least {min_count} candles, got {len(candles)}"

    for i, candle in enumerate(candles):
        # Required fields
        required = ["timestamp", "open", "high", "low", "close"]
        for field in required:
            assert field in candle, f"Candle {i} missing field: {field}"

        # Positive prices
        assert candle["open"] > 0, f"Candle {i}: open must be positive"
        assert candle["high"] > 0, f"Candle {i}: high must be positive"
        assert candle["low"] > 0, f"Candle {i}: low must be positive"
        assert candle["close"] > 0, f"Candle {i}: close must be positive"

        # Price relationships
        assert candle["high"] >= candle["low"], f"Candle {i}: high < low"
        assert candle["high"] >= candle["open"], f"Candle {i}: high < open"
        assert candle["high"] >= candle["close"], f"Candle {i}: high < close"
        assert candle["low"] <= candle["open"], f"Candle {i}: low > open"
        assert candle["low"] <= candle["close"], f"Candle {i}: low > close"

        # Volume (if present)
        if "volume" in candle:
            assert candle["volume"] >= 0, f"Candle {i}: negative volume"


def get_fixture_metadata(filename: str) -> Dict[str, Any]:
    """
    Get metadata from a fixture file without loading full data.

    Args:
        filename: Fixture filename

    Returns:
        Metadata dict

    Example:
        >>> meta = get_fixture_metadata("btc_usdt_binance_1h_sample.json")
        >>> assert meta["source"] == "binance"
        >>> assert meta["candle_count"] > 0
    """
    fixture = load_fixture(filename)
    return fixture["metadata"]


def list_available_fixtures() -> List[str]:
    """
    List all available fixture files.

    Returns:
        List of fixture filenames

    Example:
        >>> fixtures = list_available_fixtures()
        >>> assert "btc_usdt_binance_1h_sample.json" in fixtures
    """
    return [f.name for f in FIXTURES_DIR.glob("*.json")]


# Convenience exports for common use cases
__all__ = [
    "load_fixture",
    "get_binance_ohlcv_sample",
    "get_coingecko_ohlcv_sample",
    "get_multi_source_sample",
    "get_anomaly_scenario",
    "mock_binance_klines_response",
    "mock_coingecko_ohlc_response",
    "assert_valid_ohlcv",
    "get_fixture_metadata",
    "list_available_fixtures"
]
