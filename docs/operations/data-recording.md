# Live Market Data Recording for Backtesting

## Overview

The Trade Engine includes a comprehensive market data recording infrastructure to capture real-time data from exchanges for backtesting strategies.

**Why Record Data?**
- Test strategies with **real market conditions** (not synthetic data)
- Build historical datasets for **L2 order book imbalance** strategy validation
- Capture **tick-by-tick trades** for precise slippage modeling
- Aggregate **1-minute bars** from live data for strategy development

## Supported Data Types

### 1. L2 Order Book Snapshots (Recommended for L2 Imbalance Strategy)

**What it records:**
- Top 5 bid levels (price + quantity)
- Top 5 ask levels (price + quantity)
- Captured at configurable intervals (default: 1 second)

**Use case:**
- Backtesting L2 order book imbalance strategy
- Testing bid/ask volume ratio signals
- Analyzing order book dynamics

**Storage format (CSV):**
```csv
timestamp,symbol,bid_price_1,bid_qty_1,bid_price_2,bid_qty_2,...,ask_price_1,ask_qty_1,...
1706572800000,BTCUSDT,42500.50,1.25,42500.00,2.50,...,42501.00,1.75,...
```

**Recording command:**
```bash
python scripts/record_market_data.py \
  --type l2 \
  --symbol BTCUSDT \
  --exchange binance \
  --interval 1.0 \
  --duration 86400  # Record for 24 hours
```

**Expected data size:**
- 1 second intervals: ~86,400 snapshots/day (~5-10 MB CSV)
- 0.5 second intervals: ~172,800 snapshots/day (~10-20 MB CSV)

---

### 2. Tick-by-Tick Trades

**What it records:**
- Individual trade executions
- Price, quantity, side (buy/sell)
- Microsecond-level timestamps

**Use case:**
- Precise execution timing analysis
- Slippage modeling
- Building custom OHLCV bars

**Storage format (CSV):**
```csv
timestamp,symbol,price,quantity,side
1706572800123,BTCUSDT,42500.50,0.125,buy
1706572800456,BTCUSDT,42500.75,0.050,sell
```

**Recording command:**
```bash
python scripts/record_market_data.py \
  --type trades \
  --symbol BTCUSDT \
  --exchange binance \
  --duration 3600  # Record for 1 hour
```

**Expected data size:**
- BTC/USDT: ~10,000-50,000 trades/hour (~500 KB - 2 MB CSV)
- High-volume pairs can generate 100,000+ trades/hour

---

### 3. OHLCV Bars (Aggregated from Trades)

**What it records:**
- Open, High, Low, Close, Volume
- Aggregated from live trade stream
- Configurable intervals: 1m, 5m, 15m, 1h, 4h

**Use case:**
- Testing bar-based strategies (Volume RVOL, Regime Detector)
- Building historical datasets without API rate limits
- Cross-validating exchange API data

**Storage format (CSV):**
```csv
timestamp,symbol,interval,open,high,low,close,volume
1706572800000,BTCUSDT,1m,42500.00,42510.50,42495.00,42505.25,12.5
```

**Recording command:**
```bash
python scripts/record_market_data.py \
  --type ohlcv \
  --symbol BTCUSDT \
  --interval 1m \
  --duration 86400  # Record for 24 hours
```

**Expected data size:**
- 1-minute bars: ~1,440 bars/day (~50-100 KB CSV)
- 5-minute bars: ~288 bars/day (~10-20 KB CSV)

---

## Recording Multiple Data Types Simultaneously

You can record L2 snapshots, trades, and OHLCV bars **at the same time** from a single WebSocket connection:

```bash
python scripts/record_market_data.py \
  --type l2,trades,ohlcv \
  --symbol BTCUSDT \
  --exchange binance \
  --interval 1.0 \
  --duration 86400
```

This will create:
- `data/l2_snapshots/l2_snapshots_20250130.csv`
- `data/trades/trades_20250130.csv`
- `data/ohlcv/ohlcv_20250130.csv`

---

## Storage Backends

### CSV Storage (Default)

**Pros:**
- Simple, human-readable
- Easy to inspect and debug
- Works with pandas, Excel, etc.
- No database setup required

**Cons:**
- Slower for large datasets (>1M rows)
- No indexing or querying

**File structure:**
```
data/
├── l2_snapshots/
│   ├── l2_snapshots_20250130.csv
│   ├── l2_snapshots_20250131.csv
├── trades/
│   ├── trades_20250130.csv
│   ├── trades_20250131.csv
├── ohlcv/
│   ├── ohlcv_20250130.csv
│   ├── ohlcv_20250131.csv
```

### PostgreSQL Storage (Coming Soon)

**Pros:**
- Fast queries with indexing
- Handle millions of rows efficiently
- SQL-based filtering and aggregation

**Cons:**
- Requires PostgreSQL server setup
- More complex configuration

**Usage (future):**
```bash
python scripts/record_market_data.py \
  --type l2 \
  --symbol BTCUSDT \
  --backend postgres \
  --db-url "postgresql://user:pass@localhost/market_data"
```

---

## Data Replay for Backtesting

Once you've recorded data, you can **replay** it to test strategies as if receiving live data:

### Replay L2 Snapshots at 10x Speed

```bash
python scripts/replay_market_data.py \
  --type l2 \
  --file data/l2_snapshots/l2_snapshots_20250130.csv \
  --speed 10
```

**Output:**
```
[2025-01-30 10:00:00] Symbol: BTCUSDT, Best bid: 42500.50, Best ask: 42501.00
[2025-01-30 10:00:01] Symbol: BTCUSDT, Best bid: 42500.75, Best ask: 42501.25
...
```

### Test L2 Imbalance Detection

```bash
python scripts/replay_market_data.py \
  --type l2 \
  --file data/l2_snapshots/l2_snapshots_20250130.csv \
  --speed 10 \
  --test-imbalance
```

**Output (signals only):**
```
[2025-01-30 10:15:23] BUY SIGNAL - Imbalance: 3.25x (bid pressure)
[2025-01-30 10:18:45] SELL SIGNAL - Imbalance: 0.28x (ask pressure)
[2025-01-30 10:22:10] BUY SIGNAL - Imbalance: 4.10x (bid pressure)
...
Total signals detected: 47
```

### Replay with Time Range Filter

```bash
python scripts/replay_market_data.py \
  --type l2 \
  --file data/l2_snapshots/l2_snapshots_20250130.csv \
  --start 1706572800000 \
  --end 1706659200000 \
  --speed 100
```

---

## Recommended Recording Strategy

### For L2 Imbalance Strategy Development

1. **Initial Testing (1 day)**
   ```bash
   python scripts/record_market_data.py \
     --type l2,ohlcv \
     --symbol BTCUSDT \
     --interval 1.0 \
     --duration 86400
   ```

2. **Extended Validation (1 week)**
   ```bash
   # Run continuously for 7 days
   python scripts/record_market_data.py \
     --type l2,trades \
     --symbol BTCUSDT \
     --interval 1.0
   # Stop with Ctrl+C after 1 week
   ```

3. **Multi-Instrument Dataset (24 hours each)**
   ```bash
   # BTC/USDT
   python scripts/record_market_data.py --type l2 --symbol BTCUSDT --duration 86400

   # ETH/USDT
   python scripts/record_market_data.py --type l2 --symbol ETHUSDT --duration 86400

   # SOL/USDT
   python scripts/record_market_data.py --type l2 --symbol SOLUSDT --duration 86400
   ```

---

## Integration with Test Suite

### Using Recorded Data in Tests

```python
import pandas as pd
from pathlib import Path
from decimal import Decimal

def load_l2_snapshot_fixture(csv_path: str) -> pd.DataFrame:
    """Load recorded L2 snapshots for testing."""
    df = pd.read_csv(csv_path)

    # Convert to Decimal
    for i in range(1, 6):
        df[f"bid_price_{i}"] = df[f"bid_price_{i}"].astype(str).apply(Decimal)
        df[f"bid_qty_{i}"] = df[f"bid_qty_{i}"].astype(str).apply(Decimal)
        df[f"ask_price_{i}"] = df[f"ask_price_{i}"].astype(str).apply(Decimal)
        df[f"ask_qty_{i}"] = df[f"ask_qty_{i}"].astype(str).apply(Decimal)

    return df

def test_l2_imbalance_with_real_data():
    """Test L2 imbalance strategy with real recorded data."""
    df = load_l2_snapshot_fixture("data/l2_snapshots/l2_snapshots_20250130.csv")

    strategy = L2ImbalanceStrategy(symbol="BTCUSDT")

    signals = []

    for idx, row in df.iterrows():
        # Reconstruct order book from snapshot
        bids = [(row[f"bid_price_{i}"], row[f"bid_qty_{i}"]) for i in range(1, 6)]
        asks = [(row[f"ask_price_{i}"], row[f"ask_qty_{i}"]) for i in range(1, 6)]

        # Calculate imbalance
        imbalance = strategy.calculate_imbalance(bids, asks)

        # Check for signals
        if imbalance > 3.0:
            signals.append(("buy", row["timestamp"], imbalance))
        elif imbalance < 0.33:
            signals.append(("sell", row["timestamp"], imbalance))

    # Validate signals
    assert len(signals) > 0
    assert all(s[2] > 3.0 for s in signals if s[0] == "buy")
    assert all(s[2] < 0.33 for s in signals if s[0] == "sell")
```

---

## Data Quality Checks

### Validate Recorded Data

```python
import pandas as pd

def validate_l2_snapshots(csv_path: str):
    """Check quality of recorded L2 snapshots."""
    df = pd.read_csv(csv_path)

    print(f"Total snapshots: {len(df)}")
    print(f"Time range: {df['timestamp'].min()} - {df['timestamp'].max()}")

    # Check for gaps
    df['timestamp_diff'] = df['timestamp'].diff()
    gaps = df[df['timestamp_diff'] > 2000]  # >2 second gaps

    if len(gaps) > 0:
        print(f"WARNING: {len(gaps)} gaps detected (>2 seconds)")
    else:
        print("✓ No significant gaps detected")

    # Check for zero prices (data errors)
    zero_bids = (df['bid_price_1'] == 0).sum()
    zero_asks = (df['ask_price_1'] == 0).sum()

    if zero_bids > 0 or zero_asks > 0:
        print(f"WARNING: {zero_bids} zero bids, {zero_asks} zero asks")
    else:
        print("✓ No zero prices detected")

validate_l2_snapshots("data/l2_snapshots/l2_snapshots_20250130.csv")
```

---

## Troubleshooting

### WebSocket Disconnections

**Symptom:** Recorder stops after a few hours with connection error

**Solution:** The recorder auto-reconnects, but for long recording sessions, monitor logs:
```bash
python scripts/record_market_data.py --type l2 --symbol BTCUSDT 2>&1 | tee recording.log
```

### Large CSV Files

**Symptom:** CSV files grow to GB sizes, slow to load

**Solution 1:** Split by day (default behavior)
```
l2_snapshots_20250130.csv  # Day 1
l2_snapshots_20250131.csv  # Day 2
```

**Solution 2:** Use PostgreSQL backend (coming soon)

### Missing Data Points

**Symptom:** Timestamp gaps in recorded data

**Possible causes:**
- Exchange WebSocket lag during high volatility
- Network interruptions
- High CPU usage (recording too many instruments)

**Solution:** Record fewer instruments simultaneously, or use a VPS closer to exchange servers

---

## Performance Considerations

### CPU Usage

| Data Type | CPU Usage (per instrument) |
|-----------|---------------------------|
| L2 snapshots (1s) | ~2-5% |
| Trades | ~5-10% |
| OHLCV (1m) | ~1-2% |
| **All 3 combined** | ~10-15% |

**Recommendation:** Can record 5-10 instruments on a modern laptop, 20+ on a VPS

### Disk Usage

| Data Type | Interval | Storage per day |
|-----------|----------|----------------|
| L2 snapshots | 1 second | ~5-10 MB |
| L2 snapshots | 0.5 second | ~10-20 MB |
| Trades | Tick-by-tick | ~10-50 MB |
| OHLCV | 1 minute | ~50-100 KB |

**Recommendation:** 100 GB disk can store 6-12 months of L2 data for 1 instrument

### Network Bandwidth

| Data Type | Bandwidth (sustained) |
|-----------|-----------------------|
| L2 snapshots | ~10-20 KB/s |
| Trades | ~5-15 KB/s |
| OHLCV | ~1-5 KB/s |

**Recommendation:** Any broadband connection sufficient

---

## Future Enhancements

### Planned Features

- [ ] PostgreSQL storage backend
- [ ] Automatic data compression (gzip CSV files)
- [ ] Multi-exchange support (Bybit, OKX, Coinbase)
- [ ] L3 order book data (individual orders)
- [ ] Funding rate + open interest recording
- [ ] Built-in data quality monitoring
- [ ] Cloud storage integration (S3, Google Cloud Storage)

---

## See Also

- `src/trade_engine/adapters/feeds/data_recorder.py` - Recording implementation
- `src/trade_engine/adapters/feeds/data_replay.py` - Replay utilities
- `scripts/record_market_data.py` - Recording script
- `scripts/replay_market_data.py` - Replay script
- `tests/fixtures/README_DERIVATIVES.md` - Using fixtures in tests
