# Data Pipeline

This directory contains documentation for market data collection, validation, and testing infrastructure.

## =Ê Overview

The Trade Engine's data pipeline handles real-time market data streaming, historical data recording, and test fixture generation for backtesting.

## =Ë Available Documentation

- [Pipeline Overview](pipeline-overview.md) - Complete data workflow from collection to analysis
- [Data Validation](validation.md) - Quality checks and data cleaning procedures
- [Test Fixtures](fixtures.md) - Historical test data for strategy validation
- [Web3 Signals](web3-signals.md) - On-chain data integration (future)
- [Pipeline One-Liners](pipeline-one-liners.md) - Quick command reference

### Coming Soon
- Data Sources Guide - API integration details for each provider

## = Data Flow

### Real-Time Data
1. **Collection**: WebSocket L2 order book streams
2. **Processing**: Order book maintenance and imbalance calculation
3. **Signal Generation**: Strategy evaluation on live data
4. **Execution**: Order placement via broker adapters

### Historical Data
1. **Recording**: Capture live data to PostgreSQL
2. **Validation**: Quality checks and gap detection
3. **Replay**: Feed historical data to strategies for backtesting
4. **Analysis**: Performance metrics and optimization

## =á Data Sources

### Level 2 Order Book (Primary)
- **Binance Futures**: 100ms depth updates via WebSocket
- **Binance.us**: Spot market depth data
- **Kraken Futures**: Derivatives depth feed

### OHLCV Data (Secondary)
- **Yahoo Finance**: Free daily stock data
- **Exchange REST APIs**: Historical candles

### Derivatives Data (Advanced)
- **Funding Rates**: 8-hour perpetual futures funding
- **Open Interest**: Total outstanding contracts
- **Liquidations**: Force-close events

## >ê Test Infrastructure

### Fixture Generation
Historical data captured in CSV format for deterministic testing:
- `tests/fixtures/binance_futures_btcusdt_derivatives.csv`
- `tests/fixtures/kraken_futures_xbtusd_derivatives.csv`
- `tests/fixtures/binanceus_btcusdt_1h.csv`

### Data Replay
Feed historical data to strategies as if live:
```python
from trade_engine.adapters.feeds.data_replay import DataReplayFeed

replay = DataReplayFeed("tests/fixtures/my_data.csv")
strategy.evaluate(replay.get_next_snapshot())
```

## = Related Documentation

- [Feed Interface](../reference/adapters/feed-interface.md) - WebSocket feed adapter specification
- [Data Source Interface](../reference/adapters/data-source-interface.md) - REST API adapter spec
- [PostgreSQL Setup](../operations/data-recording.md) - Database configuration

## =È Data Quality

### Validation Checks
-  Timestamp continuity (no gaps)
-  Price sanity (no outliers)
-  Volume validation (non-negative)
-  Order book integrity (bid < ask)

### Recording Guidelines
- Record at least 24 hours before live trading
- Verify WebSocket stability (< 3 disconnects/day)
- Monitor data loss (0 tolerance for trades)

---

**Last Updated**: 2025-10-31
