# Data Source Adapter Interface Specification

**Last Updated**: 2025-10-30
**Status**: Official Specification
**Phase**: 0 → 1 Transition

---

## Overview

The **Data Source Adapter** interface defines the contract for fetching historical and real-time market data from various sources. Unlike feeds (which stream real-time data), data sources provide on-demand access to OHLCV candles, ticker snapshots, and fundamental data.

**Key Design Principles**:
1. **Flexibility**: Support multiple timeframes and data types
2. **Type Safety**: All price/volume values use `Decimal` (NON-NEGOTIABLE)
3. **Rate Limiting**: Respect API rate limits, implement backoff
4. **Caching**: Cache responses to minimize API calls

---

## Interface Definition

### DataSourceAdapter (`trade_engine.adapters.data_sources.base.DataSourceAdapter`)

**Location**: `src/trade_engine/adapters/data_sources/base.py`
**Purpose**: REST API access to historical and snapshot data
**Use Case**: Backtesting, scanner pre-analysis, data collection

**Required Methods**:
```python
async def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    limit: Optional[int] = None
) -> pd.DataFrame

async def fetch_ticker(symbol: str) -> Dict

def supports_timeframe(timeframe: str) -> bool
def get_supported_symbols() -> List[str]
def normalize_symbol(symbol: str) -> str
def get_rate_limit() -> int
```

---

## Method Specifications

### `async def fetch_ohlcv(...) -> pd.DataFrame`

Fetch OHLCV (candlestick) data for backtesting or analysis.

**Arguments**:
- `symbol` (str): Trading pair (e.g., "BTC/USD" standard format)
- `timeframe` (str): Candle timeframe ("1m", "5m", "15m", "1h", "4h", "1d")
- `start` (datetime): Start datetime (UTC)
- `end` (datetime): End datetime (UTC)
- `limit` (Optional[int]): Maximum number of candles (default: all between start/end)

**Returns**:
- `pd.DataFrame`: DataFrame with columns:
  - `timestamp` (int): Unix timestamp in milliseconds
  - `open` (Decimal): Open price
  - `high` (Decimal): High price
  - `low` (Decimal): Low price
  - `close` (Decimal): Close price
  - `volume` (Decimal): Volume in base currency

**Raises**:
- `ValueError`: Invalid symbol or timeframe
- `RateLimitError`: API rate limit exceeded
- `DataNotAvailableError`: Data not available for requested period

**Implementation Requirements**:
- ✅ Must return Decimal for OHLCV values (NOT float)
- ✅ Must return sorted by timestamp (ascending)
- ✅ Must handle pagination if response exceeds API limit
- ✅ Must validate data quality (no gaps, no duplicates)
- ✅ Must respect rate limits (implement backoff)
- ✅ Should cache results for repeated queries

**Example**:
```python
from datetime import datetime, timedelta

source = BinanceFuturesDataSource()

df = await source.fetch_ohlcv(
    symbol="BTC/USDT",
    timeframe="1h",
    start=datetime.utcnow() - timedelta(days=7),
    end=datetime.utcnow(),
    limit=168  # 7 days * 24 hours
)

print(df.head())
#    timestamp          open          high           low         close      volume
# 0  1635724800000  Decimal('50000')  Decimal('50100')  Decimal('49900')  Decimal('50050')  Decimal('123.45')
# 1  1635728400000  Decimal('50050')  Decimal('50200')  Decimal('50000')  Decimal('50100')  Decimal('234.56')
```

---

### `async def fetch_ticker(symbol: str) -> Dict`

Fetch current ticker snapshot (bid, ask, last, volume).

**Arguments**:
- `symbol` (str): Trading pair

**Returns**:
- `Dict`: Ticker data
  ```python
  {
      "symbol": "BTCUSDT",
      "bid": Decimal("50000.00"),
      "ask": Decimal("50001.00"),
      "last": Decimal("50000.50"),
      "volume_24h": Decimal("12345.67"),
      "timestamp": 1635724800123
  }
  ```

**Raises**:
- `ValueError`: Invalid symbol
- `RateLimitError`: API rate limit exceeded

**Implementation Requirements**:
- ✅ Must return Decimal for price/volume values
- ✅ Must include timestamp of snapshot
- ✅ Should cache for 1-5 seconds (tickers change rapidly)

**Example**:
```python
ticker = await source.fetch_ticker("BTC/USDT")
print(f"Bid: {ticker['bid']}, Ask: {ticker['ask']}")
# Bid: 50000.00, Ask: 50001.00
```

---

### `def supports_timeframe(timeframe: str) -> bool`

Check if data source supports a specific timeframe.

**Arguments**:
- `timeframe` (str): Timeframe string (e.g., "1m", "1h", "1d")

**Returns**:
- `True`: Timeframe is supported
- `False`: Timeframe not supported

**Standard Timeframes**:
- `"1m"`: 1 minute
- `"5m"`: 5 minutes
- `"15m"`: 15 minutes
- `"1h"`: 1 hour
- `"4h"`: 4 hours
- `"1d"`: 1 day
- `"1w"`: 1 week

**Example**:
```python
if source.supports_timeframe("1m"):
    df = await source.fetch_ohlcv("BTC/USDT", "1m", start, end)
else:
    print("1-minute candles not supported")
```

---

### `def get_supported_symbols() -> List[str]`

Get list of all supported trading pairs.

**Returns**:
- `List[str]`: List of symbols in standard format (e.g., ["BTC/USDT", "ETH/USDT"])

**Implementation Requirements**:
- ✅ Should cache symbol list (updates infrequently)
- ✅ Must return standard format (e.g., "BTC/USDT", not "BTCUSDT")
- ✅ Should filter out inactive/delisted symbols

**Example**:
```python
symbols = source.get_supported_symbols()
# Returns: ["BTC/USDT", "ETH/USDT", "BNB/USDT", ...]

# Filter for USDT pairs only
usdt_pairs = [s for s in symbols if s.endswith("/USDT")]
```

---

### `def normalize_symbol(symbol: str) -> str`

Convert standard symbol format to source-specific format.

**Arguments**:
- `symbol` (str): Standard format (e.g., "BTC/USDT")

**Returns**:
- `str`: Source-specific format (e.g., "BTCUSDT" for Binance)

**Examples**:
```python
# Binance
source.normalize_symbol("BTC/USDT")  # Returns: "BTCUSDT"

# Kraken
source.normalize_symbol("BTC/USD")   # Returns: "PF_XBTUSD"

# Coinbase
source.normalize_symbol("BTC/USD")   # Returns: "BTC-USD"
```

---

### `def get_rate_limit() -> int`

Get API rate limit (requests per minute).

**Returns**:
- `int`: Maximum requests per minute

**Common Limits**:
- Binance: 2400 requests/minute (with API key)
- Kraken: 15 requests/minute (public), 20 requests/minute (private)
- Coinbase: 10 requests/second

**Example**:
```python
rate_limit = source.get_rate_limit()
delay_between_requests = 60 / rate_limit  # seconds

print(f"Rate limit: {rate_limit} req/min, delay: {delay_between_requests:.2f}s")
# Rate limit: 2400 req/min, delay: 0.025s
```

---

## Extended Methods (Optional)

### `async def fetch_trades(symbol: str, start: datetime, end: datetime) -> pd.DataFrame`

Fetch individual trade history (tick data).

**Returns**:
```python
pd.DataFrame with columns:
- timestamp (int): Trade timestamp (ms)
- price (Decimal): Trade price
- quantity (Decimal): Trade size
- side (str): "buy" or "sell"
- trade_id (str): Exchange trade ID
```

---

### `async def fetch_funding_rate(symbol: str) -> Dict`

Fetch current funding rate (futures only).

**Returns**:
```python
{
    "symbol": "BTCUSDT",
    "funding_rate": Decimal("0.0001"),  # 0.01% every 8 hours
    "next_funding_time": 1635724800000,
    "mark_price": Decimal("50000.00")
}
```

---

### `async def fetch_open_interest(symbol: str) -> Decimal`

Fetch current open interest (futures only).

**Returns**:
- `Decimal`: Total open interest in base currency

---

## Error Handling Requirements

### Exception Hierarchy

```python
class DataSourceError(Exception):
    """Base exception for all data source errors."""
    pass

class RateLimitError(DataSourceError):
    """Raised when API rate limit exceeded."""
    pass

class DataNotAvailableError(DataSourceError):
    """Raised when requested data is not available."""
    pass

class InvalidSymbolError(DataSourceError):
    """Raised when symbol is invalid or not supported."""
    pass

class InvalidTimeframeError(DataSourceError):
    """Raised when timeframe is not supported."""
    pass
```

### Rate Limit Handling

**Required Implementation**:
```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class BinanceDataSource(DataSourceAdapter):
    def __init__(self):
        self._request_times = []
        self._rate_limit = 2400  # requests per minute

    async def _enforce_rate_limit(self):
        """Ensure we don't exceed rate limit."""
        now = time.time()

        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        # Check if at limit
        if len(self._request_times) >= self._rate_limit:
            sleep_time = 60 - (now - self._request_times[0])
            logger.warning(f"Rate limit reached, sleeping {sleep_time:.1f}s")
            await asyncio.sleep(sleep_time)
            self._request_times.clear()

        self._request_times.append(now)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _request(self, method: str, endpoint: str, **params):
        """Make API request with rate limiting and retry."""
        await self._enforce_rate_limit()

        try:
            # Make request
            response = await self._http_client.request(method, endpoint, **params)
            return response.json()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
```

---

## Caching Requirements

### Cache Strategy

**What to Cache**:
1. ✅ Symbol list (update every 1 hour)
2. ✅ OHLCV data (immutable once candle closes)
3. ✅ Ticker snapshots (cache for 1-5 seconds)
4. ❌ Real-time order book (never cache, too dynamic)

**Implementation**:
```python
from functools import lru_cache
import time

class DataSourceWithCache(DataSourceAdapter):
    def __init__(self):
        self._ohlcv_cache = {}
        self._ticker_cache = {}
        self._symbols_cache = None
        self._symbols_cache_time = 0

    @lru_cache(maxsize=100)
    def get_supported_symbols(self) -> List[str]:
        """Cached symbol list (1 hour TTL)."""
        if time.time() - self._symbols_cache_time > 3600:
            self._symbols_cache = self._fetch_symbols()
            self._symbols_cache_time = time.time()
        return self._symbols_cache

    async def fetch_ohlcv(self, symbol, timeframe, start, end, limit=None):
        """Cache completed candles only."""
        cache_key = f"{symbol}_{timeframe}_{start}_{end}"

        if cache_key in self._ohlcv_cache:
            logger.debug(f"Cache hit: {cache_key}")
            return self._ohlcv_cache[cache_key]

        df = await self._fetch_ohlcv_from_api(symbol, timeframe, start, end, limit)

        # Only cache if end time is in the past (data is immutable)
        if end < datetime.utcnow():
            self._ohlcv_cache[cache_key] = df

        return df
```

---

## Performance Requirements

### Latency Targets

| Operation | Target | Acceptable |
|-----------|--------|------------|
| fetch_ticker() | <100ms | <500ms |
| fetch_ohlcv() (100 candles) | <500ms | <2s |
| fetch_ohlcv() (1000 candles) | <2s | <10s |
| get_supported_symbols() (cached) | <1ms | <10ms |

### Memory Constraints

| Data | Max Cache Size |
|------|----------------|
| OHLCV cache | 100MB |
| Symbol list | 1MB |
| Ticker cache | 10MB |

---

## Logging Requirements

### Required Log Events

**Data Fetch**:
```python
logger.info(
    "ohlcv_fetched",
    symbol="BTCUSDT",
    timeframe="1h",
    candles=len(df),
    start=str(start),
    end=str(end),
    duration_ms=(end_time - start_time) * 1000,
    timestamp=int(time.time())
)
```

**Rate Limit Warning**:
```python
logger.warning(
    "rate_limit_approached",
    requests_used=len(self._request_times),
    requests_limit=self._rate_limit,
    sleep_time=sleep_time,
    timestamp=int(time.time())
)
```

**Cache Hit**:
```python
logger.debug(
    "cache_hit",
    cache_key=cache_key,
    data_type="ohlcv",
    timestamp=int(time.time())
)
```

---

## Testing Requirements

### Unit Tests

**Required Test Coverage**:
1. ✅ Symbol normalization (standard → exchange format)
2. ✅ Timeframe support validation
3. ✅ Rate limit enforcement
4. ✅ Cache hit/miss logic
5. ✅ OHLCV data validation (no gaps, sorted)
6. ✅ Decimal precision (no float usage)
7. ✅ Error handling (rate limits, invalid symbols)

**Example**:
```python
@pytest.mark.asyncio
async def test_fetch_ohlcv_returns_decimal():
    source = BinanceFuturesDataSource()

    df = await source.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="1h",
        start=datetime.utcnow() - timedelta(hours=24),
        end=datetime.utcnow()
    )

    # Verify Decimal type (not float)
    assert isinstance(df['open'].iloc[0], Decimal)
    assert isinstance(df['high'].iloc[0], Decimal)
    assert isinstance(df['close'].iloc[0], Decimal)
    assert isinstance(df['volume'].iloc[0], Decimal)
```

### Integration Tests

**Required Tests**:
1. ✅ Fetch real OHLCV data from API
2. ✅ Verify data quality (no gaps, sorted)
3. ✅ Test rate limit handling (make 100 requests)
4. ✅ Test cache effectiveness (repeated queries)

---

## Current Implementations

### Status

**No data source adapters implemented yet**. This interface is defined for future implementation in Phase 1-2.

### Planned Implementations

#### 1. BinanceFuturesDataSource
**Purpose**: Fetch historical OHLCV data for backtesting
**Endpoint**: `https://fapi.binance.com/fapi/v1/klines`
**Rate Limit**: 2400 req/min
**Timeframes**: 1m, 5m, 15m, 1h, 4h, 1d

#### 2. BinanceUSDataSource
**Purpose**: Fetch spot market data (US-compliant)
**Endpoint**: `https://api.binance.us/api/v3/klines`
**Rate Limit**: 1200 req/min
**Timeframes**: 1m, 5m, 15m, 1h, 4h, 1d

#### 3. KrakenDataSource
**Purpose**: Fetch data from Kraken (US-accessible)
**Endpoint**: `https://futures.kraken.com/derivatives/api/v3/chart/history`
**Rate Limit**: 15 req/min (much lower)
**Timeframes**: 1m, 5m, 1h, 1d

---

## Use Cases

### 1. Backtesting (Phase 1)

```python
source = BinanceFuturesDataSource()

# Fetch 90 days of 1-hour candles
df = await source.fetch_ohlcv(
    symbol="BTC/USDT",
    timeframe="1h",
    start=datetime.utcnow() - timedelta(days=90),
    end=datetime.utcnow()
)

# Run backtest
backtest = Backtest(strategy=L2ImbalanceStrategy, data=df)
results = backtest.run()
```

---

### 2. Scanner Pre-Analysis (Phase 2)

```python
source = BinanceFuturesDataSource()

# Get all USDT perpetual futures
symbols = [s for s in source.get_supported_symbols() if s.endswith("/USDT")]

# Calculate 24h volume for each
volumes = {}
for symbol in symbols:
    df = await source.fetch_ohlcv(
        symbol=symbol,
        timeframe="1h",
        start=datetime.utcnow() - timedelta(hours=24),
        end=datetime.utcnow()
    )
    volumes[symbol] = df['volume'].sum()

# Sort by volume (most liquid first)
top_10 = sorted(volumes.items(), key=lambda x: x[1], reverse=True)[:10]
```

---

### 3. Data Collection (Phase 3)

```python
source = BinanceFuturesDataSource()

# Collect 1-minute data for 7 days
start = datetime.utcnow() - timedelta(days=7)
end = datetime.utcnow()

df = await source.fetch_ohlcv(
    symbol="BTC/USDT",
    timeframe="1m",
    start=start,
    end=end
)

# Store in TimescaleDB for future analysis
df.to_sql('ohlcv_1m', engine, if_exists='append')
```

---

## Best Practices

### 1. Decimal Usage (NON-NEGOTIABLE)
```python
# ✅ CORRECT
df['open'] = df['open'].apply(lambda x: Decimal(str(x)))

# ❌ WRONG
df['open'] = df['open'].astype(float)
```

### 2. Rate Limit Respect
```python
# ✅ CORRECT - Enforce rate limit
await self._enforce_rate_limit()
response = await self._request("GET", endpoint)

# ❌ WRONG - Spam API until banned
while True:
    response = await self._request("GET", endpoint)
```

### 3. Cache Immutable Data
```python
# ✅ CORRECT - Cache completed candles
if end < datetime.utcnow():
    self._cache[key] = df

# ❌ WRONG - Cache incomplete candles
self._cache[key] = df  # Last candle still forming!
```

### 4. Handle Pagination
```python
# ✅ CORRECT - Paginate if limit exceeded
all_candles = []
while True:
    df = await self._fetch_ohlcv(..., start=current_start, limit=1000)
    all_candles.append(df)
    if len(df) < 1000:
        break
    current_start = df['timestamp'].iloc[-1]

return pd.concat(all_candles)

# ❌ WRONG - Assume all data in one response
df = await self._fetch_ohlcv(..., limit=None)  # May exceed API limit
```

---

## Next Steps

### For Implementing New Data Sources

See [how-to-add-adapters.md](./how-to-add-adapters.md) for step-by-step guide.

### For Phase 1 Implementation

Priority: Implement `BinanceFuturesDataSource` for backtesting support.

### For Integration Testing

See [test_data_source_adapter_template.py](../../tests/integration/adapters/test_data_source_adapter_template.py) (to be created).

---

**Document Version**: 1.0
**Last Review**: 2025-10-30
**Next Review**: Phase 1 completion
