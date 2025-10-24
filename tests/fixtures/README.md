# Test Fixtures - Historical Data

**Last Updated**: 2025-10-23
**Category**: testing
**Status**: active

---

## Purpose

This directory contains **real historical cryptocurrency data** used for testing data sources and aggregation logic. Using actual market data prevents false positives and ensures tests validate against real-world scenarios.

## Data Sources

All fixture data is sourced from free, publicly available APIs:

1. **CoinGecko API** - Primary source (no API key required)
2. **Binance Public API** - Exchange data (no authentication needed)
3. **CryptoCompare** - Backup source

## Fixture Files

### `btc_usdt_binance_1h_sample.json`
- **Source**: Binance API
- **Symbol**: BTC/USDT
- **Interval**: 1 hour
- **Period**: 2024-01-01 to 2024-01-07 (168 candles)
- **Use**: Test Binance adapter OHLCV parsing

### `eth_usd_coingecko_daily_sample.json`
- **Source**: CoinGecko API
- **Symbol**: ETH/USD
- **Interval**: Daily
- **Period**: 2024-01-01 to 2024-12-31 (366 candles)
- **Use**: Test CoinGecko adapter data normalization

### `btc_usd_multi_source_sample.json`
- **Sources**: Binance, CoinGecko, CryptoCompare
- **Symbol**: BTC/USD
- **Timestamp**: 2024-06-15 12:00:00 UTC
- **Use**: Test cross-validation and consensus logic

### `known_anomalies.json`
- **Contains**: Real market anomalies and edge cases
  - Flash crash (FTX collapse Nov 2022)
  - Exchange halt (Coinbase Feb 2021)
  - Price spike (manipulation attempt)
- **Use**: Test anomaly detection

## Data Format

All fixtures follow this schema:

```json
{
  "metadata": {
    "source": "binance|coingecko|cryptocompare",
    "symbol": "BTC/USDT",
    "interval": "1h",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-07T23:59:59Z",
    "candle_count": 168,
    "fetched_at": "2025-10-23T12:00:00Z"
  },
  "data": [
    {
      "timestamp": 1704067200000,
      "open": 42000.50,
      "high": 42500.00,
      "low": 41800.25,
      "close": 42200.75,
      "volume": 1234.56
    }
  ]
}
```

## Updating Fixtures

To refresh fixture data with latest historical data:

```bash
# Run the fixture generator script
python tests/fixtures/generate_fixtures.py

# Verify new fixtures
pytest tests/unit/test_fixtures.py -v
```

## Usage in Tests

```python
import json
from pathlib import Path

def load_fixture(filename: str) -> dict:
    """Load JSON fixture data."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / filename
    with open(fixture_path) as f:
        return json.load(f)

def test_binance_parses_real_data():
    # Use real Binance API response
    fixture = load_fixture("btc_usdt_binance_1h_sample.json")

    # Test with actual market data
    source = BinanceDataSource()
    candles = source._parse_klines(fixture["data"])

    assert len(candles) == fixture["metadata"]["candle_count"]
    assert candles[0].open > 0  # Real prices
    assert candles[0].volume > 0  # Real volume
```

## Benefits

✅ **Realistic Testing** - Catch edge cases from real market conditions
✅ **No False Positives** - Tests fail when actual parsing breaks
✅ **Regression Detection** - Fixture data doesn't change, catches bugs
✅ **Offline Testing** - No API calls during test runs
✅ **Reproducible** - Same data across all test runs

## Maintenance

- **Update frequency**: Quarterly or when APIs change
- **Storage**: Keep fixtures under 1MB each
- **Version control**: Commit fixtures to git
- **Validation**: Run fixture validation before committing

## Anti-Patterns to Avoid

❌ **Don't** generate fake/random data
❌ **Don't** use hardcoded magic numbers
❌ **Don't** mock entire API responses without real structure
❌ **Don't** skip edge cases (gaps, halts, anomalies)

✅ **Do** use real API responses
✅ **Do** include known anomalies
✅ **Do** document data provenance
✅ **Do** test with multiple date ranges

---

**See also:**
- `tests/fixtures/generate_fixtures.py` - Script to fetch fresh data
- `tests/unit/test_fixtures.py` - Fixture validation tests
