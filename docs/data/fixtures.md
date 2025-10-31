# Using Historical Test Fixtures

**Last Updated**: 2025-10-23
**Category**: guides
**Status**: active

---

## Overview

This guide shows how to use **real historical cryptocurrency data** in your tests instead of mocked/fake data. Using actual market data prevents false positives and ensures your code works with real-world edge cases.

## Why Use Real Historical Data?

### ❌ Problems with Mocked Data

```python
# BAD: Fake data that doesn't match reality
mock_response.json.return_value = [
    [1000, "50000", "51000", "49000", "50500", "100", 1060, "5000000", 10, "50", "2500000", "0"]
]
```

**Issues**:
- Timestamps don't match real intervals
- Prices/volumes are arbitrary
- Misses edge cases (gaps, halts, spikes)
- Tests pass but code fails in production

### ✅ Benefits of Real Historical Data

```python
# GOOD: Real Binance data from 2024
from tests.fixtures.helpers import mock_binance_klines_response

mock_response.json.return_value = mock_binance_klines_response("1h")
```

**Benefits**:
- Real timestamps, prices, volumes
- Contains actual market anomalies
- Tests validate against production data
- Catches parsing bugs immediately

---

## Quick Start

### Step 1: Generate Fixtures

```bash
# Generate real historical data from free public APIs
python tests/fixtures/generate_fixtures.py

# Verify fixtures were created
ls tests/fixtures/*.json
```

This fetches:
- Binance hourly data (168 candles)
- Binance daily data (30 candles)
- CoinGecko daily data (90 candles)
- Multi-source consensus data
- Known anomaly scenarios

### Step 2: Update Your Tests

**Before** (using fake data):

```python
def test_fetch_ohlcv_returns_candles(self, mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        [1609459200000, "29000", "29500", "28500", "29200", "1000", ...],  # Fake
        [1609545600000, "29200", "30000", "29000", "29800", "1200", ...]   # Fake
    ]
    mock_get.return_value = mock_response
```

**After** (using real data):

```python
from tests.fixtures.helpers import mock_binance_klines_response

def test_fetch_ohlcv_returns_candles(self, mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_binance_klines_response("1h")  # Real data
    mock_get.return_value = mock_response
```

---

## Usage Examples

### Example 1: Test Binance OHLCV Parsing

```python
from tests.fixtures.helpers import (
    get_binance_ohlcv_sample,
    assert_valid_ohlcv
)

def test_parse_binance_klines_with_real_data():
    """Test parsing actual Binance API response."""
    # Get real Binance data (168 hourly candles)
    raw_candles = get_binance_ohlcv_sample("1h")

    # Parse using your adapter
    source = BinanceDataSource()
    parsed_candles = source._parse_klines(raw_candles)

    # Validate against real market data
    assert len(parsed_candles) == 168
    assert_valid_ohlcv(parsed_candles, min_count=168)

    # Real BTC prices are in realistic range
    for candle in parsed_candles:
        assert 20000 < candle.close < 100000  # Realistic BTC range
        assert candle.volume > 0  # Real volume
```

### Example 2: Test Multi-Source Cross-Validation

```python
from tests.fixtures.helpers import get_multi_source_sample

def test_cross_validation_with_real_sources():
    """Test cross-validation logic with actual source data."""
    # Get real prices from Binance, CoinGecko, etc.
    fixture = get_multi_source_sample()
    sources = fixture["data"]

    # Test your aggregator
    aggregator = DataAggregator()
    result = aggregator._cross_validate(sources)

    # Real sources should have <5% price deviation
    assert result.price_range_pct < 5.0
```

### Example 3: Test Anomaly Detection

```python
from tests.fixtures.helpers import get_anomaly_scenario

def test_detects_flash_crash():
    """Test flash crash detection with real anomaly pattern."""
    # Get real flash crash pattern
    candles = get_anomaly_scenario("flash_crash")

    detector = AnomalyDetector()
    anomalies = detector.detect(candles)

    # Should detect the crash
    assert len(anomalies) > 0
    assert anomalies[0].type == "flash_crash"
    assert anomalies[0].severity > 0.5
```

### Example 4: Test Data Quality Metrics

```python
from tests.fixtures.helpers import get_binance_ohlcv_sample

def test_calculates_quality_metrics_on_real_data():
    """Test data quality calculation with actual market data."""
    candles = get_binance_ohlcv_sample("1h")

    source = BinanceDataSource()
    metrics = source.calculate_quality_metrics(candles)

    # Real data should have high completeness
    assert metrics.completeness > 0.95
    # Real BTC volume should be substantial
    assert metrics.avg_volume > 100
```

---

## Available Fixtures

### Binance Fixtures

| Fixture | Symbol | Interval | Candles | Use For |
|---------|--------|----------|---------|---------|
| `btc_usdt_binance_1h_sample.json` | BTC/USDT | 1 hour | 168 | Hourly data parsing |
| `btc_usdt_binance_1d_sample.json` | BTC/USDT | 1 day | 30 | Daily data parsing |

**Get data**:
```python
from tests.fixtures.helpers import get_binance_ohlcv_sample

hourly = get_binance_ohlcv_sample("1h")   # 168 candles
daily = get_binance_ohlcv_sample("1d")    # 30 candles
```

### CoinGecko Fixtures

| Fixture | Symbol | Interval | Candles | Use For |
|---------|--------|----------|---------|---------|
| `btc_usd_coingecko_daily_sample.json` | BTC/USD | Daily | 90 | CoinGecko adapter |

**Get data**:
```python
from tests.fixtures.helpers import get_coingecko_ohlcv_sample

daily = get_coingecko_ohlcv_sample()  # 90 candles
```

### Multi-Source Fixtures

| Fixture | Sources | Use For |
|---------|---------|---------|
| `btc_usd_multi_source_sample.json` | Binance, CoinGecko | Cross-validation |

**Get data**:
```python
from tests.fixtures.helpers import get_multi_source_sample

sources = get_multi_source_sample()
binance_price = sources["data"]["binance"]["price"]
coingecko_price = sources["data"]["coingecko"]["price"]
```

### Anomaly Scenarios

| Scenario | Description | Use For |
|----------|-------------|---------|
| `flash_crash` | 20% drop in 1 minute | Crash detection |
| `zero_volume` | Exchange halt (0 volume) | Halt detection |
| `price_spike` | 100x manipulation spike | Spike detection |
| `data_gap` | Missing timestamps | Gap handling |

**Get data**:
```python
from tests.fixtures.helpers import get_anomaly_scenario

crash = get_anomaly_scenario("flash_crash")
halt = get_anomaly_scenario("zero_volume")
spike = get_anomaly_scenario("price_spike")
gap = get_anomaly_scenario("data_gap")
```

---

## Helper Functions

### `load_fixture(filename)` → dict

Load any fixture file.

```python
from tests.fixtures.helpers import load_fixture

fixture = load_fixture("btc_usdt_binance_1h_sample.json")
metadata = fixture["metadata"]
data = fixture["data"]
```

### `mock_binance_klines_response(interval)` → list

Get Binance data in API response format (for mocking).

```python
from tests.fixtures.helpers import mock_binance_klines_response
from unittest.mock import patch

@patch('requests.get')
def test_with_real_binance_response(mock_get):
    mock_get.return_value.json.return_value = mock_binance_klines_response("1h")

    source = BinanceDataSource()
    candles = source.fetch_ohlcv("BTCUSDT", "1h", start, end)

    assert len(candles) == 168  # Real data count
```

### `mock_coingecko_ohlc_response()` → list

Get CoinGecko data in API response format.

```python
from tests.fixtures.helpers import mock_coingecko_ohlc_response

@patch('requests.get')
def test_with_real_coingecko_response(mock_get):
    mock_get.return_value.json.return_value = mock_coingecko_ohlc_response()
    # Test with real API structure
```

### `assert_valid_ohlcv(candles, min_count)`

Validate OHLCV data structure and relationships.

```python
from tests.fixtures.helpers import assert_valid_ohlcv

candles = source.fetch_ohlcv(...)
assert_valid_ohlcv(candles, min_count=100)

# Checks:
# - Has minimum count
# - All required fields present
# - Prices are positive
# - High >= Low
# - High >= Open, Close
# - Low <= Open, Close
```

---

## Migration Guide

### Migrating Existing Tests

**Step 1**: Identify tests using mocked data

```bash
# Find tests with hardcoded responses
grep -r "mock_response.json.return_value = \[" tests/
```

**Step 2**: Replace with fixture helpers

```python
# Before
mock_response.json.return_value = [
    [1000, "50000", "51000", "49000", "50500", "100", ...]  # Fake
]

# After
from tests.fixtures.helpers import mock_binance_klines_response
mock_response.json.return_value = mock_binance_klines_response("1h")  # Real
```

**Step 3**: Update assertions

```python
# Before (assumes specific fake values)
assert candles[0].close == 50500

# After (validates against real data characteristics)
assert 20000 < candles[0].close < 100000  # Realistic BTC range
assert candles[0].volume > 0  # Real exchanges have volume
```

---

## Updating Fixtures

Fixtures should be updated quarterly or when APIs change.

### Regenerate All Fixtures

```bash
python tests/fixtures/generate_fixtures.py
```

### Regenerate and Commit

```bash
python tests/fixtures/generate_fixtures.py
git add tests/fixtures/*.json
git commit -m "chore: Update test fixtures with fresh historical data"
```

### Verify Freshness

Fixtures include `fetched_at` timestamp:

```python
from tests.fixtures.helpers import get_fixture_metadata

meta = get_fixture_metadata("btc_usdt_binance_1h_sample.json")
print(f"Fixture generated: {meta['fetched_at']}")
```

The test suite includes a freshness check that fails if fixtures are >180 days old.

---

## Best Practices

### ✅ Do

- Use real historical data for all adapter tests
- Include anomaly scenarios in edge case tests
- Validate against real price ranges (not exact values)
- Test with multiple data sources
- Update fixtures when APIs change

### ❌ Don't

- Hardcode fake timestamps/prices
- Use sequential integers (1, 2, 3) for prices
- Assume specific exact values
- Mock entire responses without real structure
- Let fixtures become >6 months old

---

## Troubleshooting

### Fixtures Not Found

```
FileNotFoundError: Fixture not found: btc_usdt_binance_1h_sample.json
Run: python tests/fixtures/generate_fixtures.py
```

**Solution**:
```bash
python tests/fixtures/generate_fixtures.py
```

### API Rate Limits

If fixture generation hits rate limits:

```python
# Edit generate_fixtures.py
time.sleep(2)  # Increase delay between requests
```

### Fixture Too Old

```
AssertionError: Fixture is 200 days old - please regenerate
```

**Solution**:
```bash
python tests/fixtures/generate_fixtures.py
```

---

## See Also

- `tests/fixtures/README.md` - Fixture documentation
- `tests/fixtures/generate_fixtures.py` - Generation script
- `tests/fixtures/helpers.py` - Helper functions
- `tests/unit/test_fixtures.py` - Fixture validation tests

---

**Remember**: Real data = Real confidence. Use historical fixtures to ensure your code works with actual market conditions!
