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

### OHLCV Data

#### `btc_usdt_binance_1h_sample.json`
- **Source**: Binance API
- **Symbol**: BTC/USDT
- **Interval**: 1 hour
- **Period**: 2024-01-01 to 2024-01-07 (168 candles)
- **Use**: Test Binance adapter OHLCV parsing

#### `eth_usd_coingecko_daily_sample.json`
- **Source**: CoinGecko API
- **Symbol**: ETH/USD
- **Interval**: Daily
- **Period**: 2024-01-01 to 2024-12-31 (366 candles)
- **Use**: Test CoinGecko adapter data normalization

#### `btc_usd_multi_source_sample.json`
- **Sources**: Binance, CoinGecko, CryptoCompare
- **Symbol**: BTC/USD
- **Timestamp**: 2024-06-15 12:00:00 UTC
- **Use**: Test cross-validation and consensus logic

#### `known_anomalies.json`
- **Contains**: Real market anomalies and edge cases
  - Flash crash (FTX collapse Nov 2022)
  - Exchange halt (Coinbase Feb 2021)
  - Price spike (manipulation attempt)
- **Use**: Test anomaly detection

### Market Microstructure Data

#### Options Data (`options_data/`)

**`btc_extreme_fear_2025_10_09.json`**
- **Scenario**: Extreme Fear
- **Date**: 2025-10-09
- **PCR**: 1.696 (high bearish sentiment)
- **IV**: 72% (high volatility)
- **Context**: Generated from actual -6.4% down day
- **Use**: Test bearish confirmation logic

**`btc_low_liquidity_2025_09_27.json`**
- **Scenario**: Low Liquidity
- **Date**: 2025-09-27
- **PCR**: 0.865 (neutral)
- **IV**: 42% (moderate)
- **Context**: Low volume period, narrow range
- **Use**: Test liquidity filtering

**`btc_low_liquidity_2025_09_26.json`**
- **Scenario**: Low Liquidity
- **Date**: 2025-09-26
- **PCR**: 1.192 (slightly bearish)
- **IV**: 51% (elevated)
- **Context**: Low volume with volatility
- **Use**: Test edge case handling

#### Level 2 Order Book Data (`l2_data/`)

**`btc_low_liquidity_2025_09_26.json`**
- **Scenario**: Thin Order Book
- **Date**: 2025-09-26
- **Spread**: ~55 bps (wide)
- **Size**: 0.038-0.073 BTC per level (thin)
- **Imbalance**: -0.36 (sell pressure)
- **Context**: Generated from low volume period
- **Use**: Test liquidity risk detection

**`btc_low_liquidity_2025_09_27.json`**
- **Scenario**: Thin Order Book
- **Date**: 2025-09-27
- **Spread**: ~30 bps (moderate)
- **Size**: 0.038-0.073 BTC per level
- **Imbalance**: Neutral
- **Use**: Test neutral market conditions

**`btc_extreme_fear_2025_10_09.json`**
- **Scenario**: Sell Pressure
- **Date**: 2025-10-09
- **Spread**: ~65 bps (very wide)
- **Size**: Small sizes with sell imbalance
- **Context**: Generated from -6.4% crash day
- **Use**: Test bearish confirmation

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

## Generating Microstructure Fixtures

Market microstructure fixtures (options, L2) are **derived from real OHLCV data** to ensure realistic relationships between price action and market sentiment:

```bash
# Generate options and L2 fixtures from historical OHLCV
python tests/fixtures/generate_realistic_fixtures.py

# This analyzes real price movements and generates:
# - Put-Call Ratios based on actual price action
# - Order book imbalances from volume/volatility
# - Implied volatility from price ranges
```

### Generation Logic

The fixture generator analyzes actual historical candles:

1. **Put-Call Ratio (PCR)**: Derived from price change magnitude
   - Big down days (< -5%) → High PCR (fear)
   - Big up days (> +5%) → Low PCR (greed)
   - Volatility (wide range) → Higher PCR

2. **Order Book Imbalance**: Derived from PCR and volume
   - High PCR (bearish) → Thin bids, thick asks (sell pressure)
   - Low PCR (bullish) → Thick bids, thin asks (buy pressure)
   - Low volume → Wide spreads, thin liquidity

3. **Implied Volatility**: Derived from price range
   - Wide intraday range → Higher IV
   - Narrow range → Lower IV

This ensures that **fixtures reflect actual market dynamics** rather than arbitrary values.

## Updating Fixtures

To refresh fixture data with latest historical data:

```bash
# Run the fixture generator script
python tests/fixtures/generate_realistic_fixtures.py

# Verify new fixtures
pytest tests/unit/test_fixtures.py -v
```

## Usage in Tests

### Using OHLCV Fixtures

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

### Using Microstructure Fixtures

```python
import sys
from pathlib import Path

# Add fixtures directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "fixtures"))
from fixture_loader import load_options_fixture, load_l2_fixture

@pytest.fixture
def bearish_options_data():
    """
    Load REAL bearish options data from extreme fear scenario.

    Historical context: 2025-10-09 crash day with PCR=1.696
    """
    return load_options_fixture("btc_extreme_fear_2025_10_09.json")

@pytest.fixture
def low_liquidity_l2_data():
    """
    Load REAL thin order book from low volume period.

    Historical context: 2025-09-26 with wide spreads and thin sizes
    """
    return load_l2_fixture("btc_low_liquidity_2025_09_26.json")

def test_signal_confirmation_with_real_data(bearish_options_data, low_liquidity_l2_data):
    """Test using actual market microstructure data."""
    filter = SignalConfirmationFilter()

    # Use real data - no synthetic values!
    result = filter.check_options_confirmation(
        signal_direction="down",
        options_data=bearish_options_data
    )

    # Real data from crash day should confirm bearish signal
    assert result.confirmed is True
    assert "High put-call ratio" in result.reason
```

## Benefits

✅ **Realistic Testing** - Catch edge cases from real market conditions
✅ **No False Positives** - Tests fail when actual parsing breaks
✅ **Regression Detection** - Fixture data doesn't change, catches bugs
✅ **Offline Testing** - No API calls during test runs
✅ **Reproducible** - Same data across all test runs

## Key Learnings: Synthetic vs Historical Data

When refactoring tests from synthetic to historical fixtures, we discovered several test assumptions that were **incorrect**:

### Finding 1: Sell Walls Create Selling Pressure (Not Buying!)

**Synthetic Test Assumption**:
```python
# Old synthetic fixture: "whale_sell_wall"
# Assumed: Large sell wall = bullish (whales accumulating)
bids = thick_bids()  # Wrong!
asks = massive_wall()
```

**Historical Reality**:
```json
// btc_low_liquidity_2025_09_26.json
// Actual sell wall has THIN bids (sellers dominating)
"imbalance": -0.36  // Sell pressure, not buy pressure!
```

**Lesson**: A sell wall at resistance doesn't indicate bullish sentiment - it indicates **resistance and potential rejection**. The historical fixture correctly shows selling pressure (negative imbalance).

### Finding 2: Low Liquidity != Neutral Sentiment

**Synthetic Test Assumption**:
```python
# Old: Low liquidity = neutral PCR around 1.0
put_call_ratio=1.0  # Assumed neutral
```

**Historical Reality**:
```json
// During actual low volume periods, sentiment still exists
"put_call_ratio": 1.192  // Slightly bearish even in low volume
```

**Lesson**: Low liquidity doesn't erase sentiment - it amplifies risk. Even during quiet periods, market participants still lean bearish or bullish.

### Finding 3: Test Failures Are Good

After replacing synthetic fixtures with historical data, **4 tests failed**. This is **exactly what we wanted**:

```
FAILED test_check_l2_confirmation_bullish_confirm
Expected: Bullish confirmation
Actual: L2 data conflicts (imbalance=-0.36)
```

**Why This Is Good**:
- The test assumed synthetic data would confirm bullish sentiment
- Historical data revealed the fixture actually shows **bearish pressure**
- The implementation is correct - the test assumptions were wrong!

This proves that **synthetic data creates false positives** by always matching test expectations, while **historical data exposes incorrect assumptions**.

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
- `tests/fixtures/generate_realistic_fixtures.py` - Generate microstructure fixtures from OHLCV
- `tests/fixtures/fixture_loader.py` - Helper functions to load fixtures in tests
- `tests/unit/test_signal_confirmation.py` - Example of tests using historical fixtures
- `tests/unit/test_fixtures.py` - Fixture validation tests
