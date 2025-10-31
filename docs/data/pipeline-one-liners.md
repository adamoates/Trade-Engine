# Data Pipeline One-Liners

**Last Updated**: 2025-10-23
**Category**: Guide
**Status**: Active

Quick copy-paste commands for common data pipeline workflows.

---

## Makefile Shortcuts

### Complete Pipelines (Recommended)

**Option 1 Testing (Futures 5m & 15m):**
```bash
make option1-test
```

**Futures BTC 5m, last 7 days:**
```bash
make full M=futures S=BTCUSDT I=5m D=7 FEE_BPS=4
```

**Futures ETH 15m, specific dates:**
```bash
make full M=futures S=ETHUSDT I=15m START=2025-07-01 END=2025-10-23 FEE_BPS=4
```

**Spot BTC 5m, last 30 days (piped, no raw file):**
```bash
make pipe M=spot S=BTCUSDT I=5m D=30 FEE_BPS=12
```

---

## Pure Python One-Liners (No Makefile)

### Spot → Validate → Clean CSV

**BTC spot 5m, last 30 days:**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market spot --symbol BTCUSDT --interval 5m --days 30 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_spot_btcusdt_5m_30d_clean.csv \
  --report data/clean/binance_spot_btcusdt_5m_30d_report.json \
  --fill drop --fee-bps 12
```

**ETH spot 15m, specific dates:**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market spot --symbol ETHUSDT --interval 15m \
  --start 2025-07-01 --end 2025-10-23 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_spot_ethusdt_15m_q3_clean.csv \
  --fill drop --fee-bps 12
```

---

### Futures → Validate → Clean CSV

**BTC futures 5m, last 7 days:**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market futures --symbol BTCUSDT --interval 5m --days 7 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_futures_btcusdt_5m_7d_clean.csv \
  --report data/clean/binance_futures_btcusdt_5m_7d_report.json \
  --fill drop --fee-bps 4
```

**BTC futures 15m, specific dates:**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market futures --symbol BTCUSDT --interval 15m \
  --start 2025-07-01 --end 2025-10-23 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_futures_btcusdt_15m_q3_clean.csv \
  --fill drop --fee-bps 4
```

---

### Complete Pipeline (Fetch → Validate → Detect → Backtest)

**Futures 5m:**
```bash
# Fetch & validate
python3 tools/fetch_binance_ohlcv.py \
  --market futures --symbol BTCUSDT --interval 5m --days 7 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_futures_btcusdt_5m_7d_clean.csv \
  --fill drop --fee-bps 4 \
&& \
# Detect regimes
python3 scripts/detect_regimes.py \
  data/clean/binance_futures_btcusdt_5m_7d_clean.csv \
  --output data/regimes/btcusdt_5m_7d_regimes.jsonl \
&& \
# Backtest
python3 scripts/backtest_trending_v3.py \
  data/regimes/btcusdt_5m_7d_regimes.jsonl \
  --timeframe 5m \
  --export data/backtest/btcusdt_5m_7d_results.json
```

**Spot 15m:**
```bash
# Fetch & validate
python3 tools/fetch_binance_ohlcv.py \
  --market spot --symbol BTCUSDT --interval 15m --days 30 --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_spot_btcusdt_15m_30d_clean.csv \
  --fill drop --fee-bps 12 \
&& \
# Detect regimes
python3 scripts/detect_regimes.py \
  data/clean/binance_spot_btcusdt_15m_30d_clean.csv \
  --output data/regimes/btcusdt_15m_30d_regimes.jsonl \
&& \
# Backtest
python3 scripts/backtest_trending_v3.py \
  data/regimes/btcusdt_15m_30d_regimes.jsonl \
  --timeframe 15m \
  --export data/backtest/btcusdt_15m_30d_results.json
```

---

## Binance.US (Domain Override)

**Spot BTCUSD 1m, last 48 hours:**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market spot --symbol BTCUSD --interval 1m --days 2 \
  --domain https://api.binance.us --stdout \
| python3 tools/validate_clean_ohlcv.py /dev/stdin \
  --out data/clean/binance_us_spot_btcusd_1m_2d_clean.csv \
  --fill drop --fee-bps 12
```

---

## Resumable Fetch (Save Raw File)

**Fetch to file (resumable if interrupted):**
```bash
python3 tools/fetch_binance_ohlcv.py \
  --market futures --symbol BTCUSDT --interval 5m --days 7 \
  --out data/ohlcv/binance_futures_btcusdt_5m_7d_raw.csv \
  --resume --progress
```

**Then validate separately:**
```bash
python3 tools/validate_clean_ohlcv.py \
  data/ohlcv/binance_futures_btcusdt_5m_7d_raw.csv \
  --out data/clean/binance_futures_btcusdt_5m_7d_clean.csv \
  --report data/clean/binance_futures_btcusdt_5m_7d_report.json \
  --fill drop --fee-bps 4
```

---

## Custom Cost Assumptions

**Futures with tighter spreads:**
```bash
make full M=futures S=BTCUSDT I=5m D=7 FEE_BPS=4 SPREAD_BPS=1 SLIP_BPS=1
```

**Spot with BNB discount (international Binance):**
```bash
make pipe M=spot S=BTCUSDT I=15m D=30 FEE_BPS=8 SPREAD_BPS=2 SLIP_BPS=2
```

**Market making (earning rebates):**
```bash
python3 tools/validate_clean_ohlcv.py input.csv \
  --out clean.csv --fill drop \
  --fee-bps -2 --spread-bps 0 --slip-bps 1
```

---

## Quality Reports

**Show all validation reports:**
```bash
make show-report
```

**Or manually:**
```bash
find data/clean -name "*_report.json" -exec cat {} \;
```

**Parse specific metrics:**
```bash
jq '{rows_in, rows_out, zero_volume_detected, gaps_detected}' \
  data/clean/binance_futures_btcusdt_5m_7d_report.json
```

---

## Backtest Summary

**Show backtest results:**
```bash
jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd, sharpe_ratio}' \
  data/backtest/btcusdt_5m_results.json
```

**Compare futures vs spot:**
```bash
make option1-compare
```

---

## Utilities

**Create data directories:**
```bash
make dirs
```

**Clean all data:**
```bash
make clean-data
```

**Quick 2-day test:**
```bash
make test-pipeline
```

---

## Tips

1. **Piped workflows** (using `--stdout`) are faster for one-time analysis (no raw file on disk)
2. **Resumable fetch** (using `--out` + `--resume`) is better for large date ranges that might fail
3. **Always validate** before regime detection (found 13% corrupt bars in 5m data)
4. **Adjust fee assumptions** for your exchange (futures: 4 bps, spot: 12 bps, Binance.US: varies)
5. **Check quality reports** after validation to see how many bars were dropped

---

## Related Documentation

- [Data Pipeline Guide](./data-pipeline-guide.md) - Complete workflows
- [Data Validation Guide](./data-validation-guide.md) - Validation details
- [Backtest Guide](./backtest-guide.md) - Backtesting strategies

---

**Credit:** One-liners contributed by user, integrated with existing infrastructure.
