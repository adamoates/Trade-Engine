# Data Validation & Cleaning Guide

**Tool**: `tools/validate_clean_ohlcv.py`
**Purpose**: Production-grade OHLCV data validation and cleaning for backtesting
**Status**: ✅ Production-ready

---

## Why Data Validation Matters

**Garbage in, garbage out.** Backtests are only as good as the data they run on. Common data quality issues that corrupt results:

1. **Zero-volume bars** (market closed, exchange downtime)
   - Artificially inflates candle count
   - Creates unrealistic price holds
   - Found in **13% of our 5m data, 3% of 15m data**

2. **Duplicate timestamps** (API errors, collection bugs)
   - Double-counts same price action
   - Skews indicators (wrong lookback periods)

3. **Missing bars / gaps** (API limits, network issues)
   - Breaks indicator calculations (ATR, MA)
   - Wrong bar counts for strategies
   - Misaligns regime detection

4. **Timezone inconsistencies** (local vs UTC)
   - Wrong candle alignment
   - Incorrect session detection
   - Cross-market correlation errors

5. **Numeric errors** (null values, string data)
   - Crashes indicator calculations
   - Silent NaN propagation
   - Wrong P&L math

---

## Features

### Core Validation

- ✅ **UTC standardization** - Converts all timestamps to UTC
- ✅ **Duplicate detection** - Finds and removes duplicate timestamps
- ✅ **Zero-volume detection** - Identifies market-closed periods
- ✅ **Gap detection** - Compares actual bars to expected grid
- ✅ **Dtype enforcement** - Ensures numeric price/volume columns

### Cleaning Options

- **drop** - Remove incomplete bars (research purity)
- **ffill** - Forward-fill missing bars (marks with `gap_flag=True`)
- **nan** - Leave gaps as NaN (for manual inspection)

### Cost Modeling

Adds realistic transaction cost columns for backtesting:

- `assumed_fee_bps` - Exchange fees (default: 12 bps = 0.12%)
- `assumed_spread_bps` - Bid-ask spread (default: 3 bps)
- `assumed_slippage_bps` - Market impact (default: 2 bps)
- `assumed_roundtrip_bps` - Total (17 bps = 0.17%)
- `assumed_roundtrip_frac` - As fraction (0.0017)

### Quality Reporting

Generates JSON report with:
- Rows in/out
- Duplicates found
- Zero-volume bars detected
- Gaps detected
- Frequency inferred
- Fill method used
- Cost assumptions

---

## Basic Usage

### 1. Simple Validation (No Filling)

```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_5m_7d.csv \
  --out data/clean/btc_usd_5m_7d_clean.csv
```

**Output**: Cleaned CSV + quality report to stdout

---

### 2. Strict Mode (Drop Incomplete Bars)

**Recommended for research/backtesting**

```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_5m_7d.csv \
  --out data/clean/btc_usd_5m_7d_clean.csv \
  --report data/clean/btc_usd_5m_7d_report.json \
  --fill drop
```

**Use when**: You need pristine data for accurate backtests

**Trade-off**: Loses some bars, but ensures no synthetic data

---

### 3. Forward-Fill Mode (Preserve Bar Count)

```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_5m_7d.csv \
  --out data/clean/btc_usd_5m_7d_clean.csv \
  --report data/clean/btc_usd_5m_7d_report.json \
  --fill ffill
```

**Use when**: Strategy needs continuous bar grid (e.g., ML features)

**Trade-off**: Imputed bars (check `gap_flag` column)

**⚠️ Warning**: Can introduce lookahead bias if not handled carefully

---

### 4. Time Window Filtering

```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_15m_full.csv \
  --drop-before 2025-07-01 \
  --drop-after 2025-10-23 \
  --out data/clean/btc_usd_15m_q3_clean.csv \
  --fill drop
```

**Use when**: Need specific date range for backtest

---

### 5. Custom Cost Assumptions

```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_5m_7d.csv \
  --out data/clean/btc_usd_5m_7d_clean.csv \
  --fee-bps 4 \         # Futures fees (0.04%)
  --spread-bps 1 \      # Tight spread
  --slip-bps 1          # Low slippage
```

**Use when**: Testing futures strategy or different exchange

**Futures**: `--fee-bps 4` (0.02% maker + 0.02% taker)
**Spot**: `--fee-bps 12` (0.06% × 2)

---

## Real-World Results

### Our 5m BTC/USD Data (Oct 16-23)

**Before validation:**
```
Rows: 2016
Issues: Unknown
```

**After validation (drop mode):**
```json
{
  "rows_in": 2016,
  "rows_out": 1756,
  "dupes_detected": 0,
  "zero_volume_detected": 260,
  "gaps_detected": 0,
  "freq_inferred_seconds": 300,
  "zero_vol_rows_dropped": 260
}
```

**Impact**: Removed 260 zero-volume bars (13% of data)
- These would have corrupted ATR calculations
- Would have generated false entry signals
- Would have shown unrealistic "holds" during market-closed periods

---

### Our 15m BTC/USD Data (Oct 16-23)

**After validation:**
```json
{
  "rows_in": 672,
  "rows_out": 651,
  "zero_volume_detected": 21,
  "zero_vol_rows_dropped": 21
}
```

**Impact**: Removed 21 zero-volume bars (3% of data)

---

## Integration with Existing Workflow

### Before (Risky)

```bash
# Collect data
python3 scripts/collect_ohlcv.py --timeframe 5m --duration 168

# Detect regimes DIRECTLY on raw data ❌
python3 scripts/detect_regimes.py data/ohlcv/btc_usd_5m_7d.csv

# Backtest on dirty data ❌
python3 scripts/backtest_trending_v3.py data/regimes/btc_usd_5m_regimes.jsonl
```

**Problem**: Zero-volume bars corrupt ATR → wrong regime labels → bad signals

---

### After (Correct)

```bash
# 1. Collect data
python3 scripts/collect_ohlcv.py \
  --timeframe 5m \
  --duration 168 \
  --output data/ohlcv/btc_usd_5m_7d_raw.csv

# 2. Validate & clean ✅
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/btc_usd_5m_7d_raw.csv \
  --out data/ohlcv/btc_usd_5m_7d.csv \
  --report data/clean/report.json \
  --fill drop

# 3. Detect regimes on CLEAN data ✅
python3 scripts/detect_regimes.py data/ohlcv/btc_usd_5m_7d.csv

# 4. Backtest on clean data ✅
python3 scripts/backtest_trending_v3.py data/regimes/btc_usd_5m_regimes.jsonl
```

**Benefit**: All indicators calculated on pristine data

---

## Best Practices

### 1. Always Validate Before Regime Detection

**Why**: Regime detection uses ATR, ADX, RSI - all sensitive to data quality

**Bad**:
```bash
collect_ohlcv.py → detect_regimes.py  # ATR calculated on dirty data ❌
```

**Good**:
```bash
collect_ohlcv.py → validate_clean_ohlcv.py → detect_regimes.py  # ✅
```

---

### 2. Prefer `--fill drop` for Research

**Forward-fill introduces synthetic bars** that can:
- Artificially smooth volatility
- Create lookahead bias (if not careful)
- Hide data quality issues

**Use drop mode for**:
- Initial research
- Strategy backtesting
- Performance validation

**Use ffill mode for**:
- ML feature engineering (needs continuous grid)
- Production systems (can't have gaps)
- **But**: Always check `gap_flag` column and handle accordingly

---

### 3. Always Generate Quality Reports

```bash
# Save report for audit trail
python3 tools/validate_clean_ohlcv.py input.csv \
  --out clean.csv \
  --report reports/quality_$(date +%Y%m%d).json \
  --fill drop
```

**Benefits**:
- Audit trail for data quality
- Track data deterioration over time
- Debug backtest discrepancies

---

### 4. Adjust Costs for Exchange/Market

**Binance.US Spot** (our current):
```bash
--fee-bps 12 --spread-bps 3 --slip-bps 2  # Total: 17 bps
```

**Binance.US Futures** (Option 1):
```bash
--fee-bps 4 --spread-bps 2 --slip-bps 1   # Total: 7 bps
```

**Binance Spot** (non-US, with BNB discount):
```bash
--fee-bps 8 --spread-bps 2 --slip-bps 2   # Total: 12 bps
```

**Market Making** (earning rebates):
```bash
--fee-bps -2 --spread-bps 0 --slip-bps 1  # Total: -1 bps (profit!)
```

---

## Output Schema

### Cleaned CSV Columns

**Original:**
```
open_time, open, high, low, close, volume
```

**After validation:**
```
open_time,              # UTC timestamp (index)
open,                   # Numeric
high,                   # Numeric
low,                    # Numeric
close,                  # Numeric
volume,                 # Numeric
gap_flag,               # bool (True if bar was filled)
assumed_fee_bps,        # float
assumed_spread_bps,     # float
assumed_slippage_bps,   # float
assumed_roundtrip_bps,  # float
assumed_roundtrip_frac  # float (for P&L calcs)
```

---

### Quality Report JSON

```json
{
  "input": "data/ohlcv/btc_usd_5m_7d.csv",
  "out": "data/clean/btc_usd_5m_7d_clean.csv",
  "rows_in": 2016,
  "rows_out": 1756,
  "dupes_detected": 0,
  "zero_volume_detected": 260,
  "gaps_detected": 0,
  "freq_inferred_seconds": 300,
  "filled_method": "drop",
  "gap_rows_flagged": 0,
  "zero_vol_rows_dropped": 260,
  "assumptions_bps": {
    "fee": 12.0,
    "spread": 3.0,
    "slippage": 2.0,
    "roundtrip": 17.0
  }
}
```

---

## Validation Checks Performed

### 1. Timestamp Standardization

**Issue**: Mixed timezones (local, UTC, exchange-specific)

**Solution**: All timestamps converted to UTC

**Example**:
```python
# Before
"2025-10-23 14:30:00-04:00"  # EDT

# After
"2025-10-23 18:30:00+00:00"  # UTC
```

---

### 2. Duplicate Detection

**Issue**: Same timestamp appears multiple times

**Detection**: `pd.Index.duplicated()`

**Resolution**: Keep first occurrence, drop rest

**Example**:
```
# Before
2025-10-23 10:00:00, 100, 101, 99, 100.5, 1000
2025-10-23 10:00:00, 100, 101, 99, 100.5, 1000  # ← Duplicate

# After
2025-10-23 10:00:00, 100, 101, 99, 100.5, 1000  # Kept first
```

---

### 3. Zero-Volume Detection

**Issue**: Market closed, exchange downtime, API errors

**Detection**: `volume <= 0`

**Resolution**: Drop rows (can't trade with no volume)

**Example**:
```
# Before
2025-10-23 10:00:00, 100, 100, 100, 100, 0    # ← No volume
2025-10-23 10:05:00, 100, 101, 99, 100.5, 1000

# After
2025-10-23 10:05:00, 100, 101, 99, 100.5, 1000  # Dropped zero-vol
```

---

### 4. Gap Detection

**Issue**: Missing bars in time series

**Detection**: Compare actual bars to expected grid

**Example (5m data)**:
```
Expected: 10:00, 10:05, 10:10, 10:15
Actual:   10:00,       10:10, 10:15  # ← Missing 10:05

Gaps detected: 1
```

**Resolution**:
- `--fill drop`: Remove entire gap region
- `--fill ffill`: Copy previous bar (marks `gap_flag=True`)
- `--fill nan`: Leave as NaN

---

### 5. Dtype Enforcement

**Issue**: String data in numeric columns

**Detection**: `pd.to_numeric(..., errors='coerce')`

**Resolution**: Convert or NaN

**Example**:
```python
# Before
"100.5", "N/A", "101.2"

# After
100.5, NaN, 101.2  # "N/A" → NaN
```

---

## Common Issues & Solutions

### Issue: "No timestamp column found"

**Cause**: CSV doesn't have recognized timestamp column

**Solution**: Rename your column to one of:
- `time`
- `timestamp`
- `date`
- `datetime`
- `open_time`

---

### Issue: "Missing required columns"

**Cause**: CSV lacks OHLCV data

**Solution**: Ensure columns named:
- `open` (or `o`)
- `high` (or `h`)
- `low` (or `l`)
- `close` (or `c`, `adjclose`, `adj_close`)
- `volume` (or `v`, `vol`)

---

### Issue: Cleaned file smaller than expected

**Cause**: Many zero-volume bars or gaps dropped

**Check**: Review quality report:
```json
{
  "zero_volume_detected": 260,  # ← High number
  "zero_vol_rows_dropped": 260
}
```

**Action**: If >10% dropped, investigate data source

---

### Issue: Negative P&L on backtest after validation

**Cause**: Cost assumptions too high (or strategy actually bad)

**Check**: Review `assumptions_bps` in report

**Adjust**:
```bash
# Lower costs (if moving to futures)
--fee-bps 4 --spread-bps 1 --slip-bps 1
```

---

## Advanced Usage

### Batch Processing

```bash
#!/bin/bash
# Validate all raw OHLCV files

for file in data/ohlcv/raw/*.csv; do
  base=$(basename "$file" .csv)
  python3 tools/validate_clean_ohlcv.py \
    "$file" \
    --out "data/ohlcv/clean/${base}_clean.csv" \
    --report "data/clean/reports/${base}_report.json" \
    --fill drop
done
```

---

### Quality Monitoring

```bash
# Track data quality over time
python3 tools/validate_clean_ohlcv.py input.csv \
  --out clean.csv \
  --report "reports/quality_$(date +%Y%m%d_%H%M%S).json"

# Check for degradation
jq '.zero_volume_detected' reports/*.json
```

---

## FAQ

**Q: Should I always use `--fill drop`?**

A: For backtesting, yes. For live trading or ML, consider `ffill` but check `gap_flag`.

---

**Q: What if I have custom fee structure?**

A: Use `--fee-bps`, `--spread-bps`, `--slip-bps` to match your exchange.

---

**Q: Can I run this on live/streaming data?**

A: No, this is for historical CSVs. For live data, build real-time validator.

---

**Q: Does this work with other assets (stocks, forex)?**

A: Yes! Works with any OHLCV CSV format. Adjust cost assumptions accordingly.

---

**Q: What's the performance?**

A: ~10k rows/sec on modern laptop. 7-day 5m data (~2k rows) processes in <1 second.

---

## Next Steps

1. **Validate existing data**:
   ```bash
   python3 tools/validate_clean_ohlcv.py \
     data/ohlcv/btc_usd_5m_7d.csv \
     --out data/ohlcv/btc_usd_5m_7d_clean.csv \
     --report data/clean/report.json \
     --fill drop
   ```

2. **Re-run regime detection** on clean data:
   ```bash
   python3 scripts/detect_regimes.py \
     data/ohlcv/btc_usd_5m_7d_clean.csv
   ```

3. **Re-run backtests** and compare results

4. **Integrate into workflow**: Add validation step to all data collection

---

## Related Documentation

- **Data Collection**: [`docs/guides/data-collection-guide.md`](./data-collection-guide.md)
- **Regime Detection**: [`docs/guides/regime-detection-guide.md`](./regime-detection-guide.md)
- **Backtesting**: [`docs/guides/backtest-guide.md`](./backtest-guide.md)

---

**Status**: ✅ Production-ready
**Contributor**: User (stakeholder)
**Integrated**: 2025-10-23

🎯
