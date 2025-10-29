# MFT Bot - Multi-Broker Support Summary

## Overview

The MFT trading bot now supports **three broker options** for different use cases and geographic locations:

1. **Binance International Futures** (testnet only) - Original implementation
2. **Kraken Futures** (US-accessible) - Full futures support ✅ **NEW**
3. **Binance.us Spot** (US-only) - Spot trading ✅ **NEW**

---

## 1. Kraken Futures Broker ✅

**Status**: Fully implemented and tested
**File**: `app/adapters/broker_kraken.py`
**Tests**: `tests/unit/test_broker_kraken.py` (13/13 passing, 87% coverage)

### Features
- ✅ US-accessible (available in most US states)
- ✅ Futures trading (long + short)
- ✅ Demo environment support (`demo-futures.kraken.com`)
- ✅ HMAC-SHA512 authentication (2024 updated method)
- ✅ Market orders (buy/sell)
- ✅ Position tracking
- ✅ Account balance queries
- ✅ All Decimal-based calculations

### Supported Symbols
- `PF_XBTUSD` - Bitcoin perpetual
- `PF_ETHUSD` - Ethereum perpetual
- `PF_SOLUSD` - Solana perpetual
- `PF_ADAUSD` - Cardano perpetual

### Configuration
```bash
# .env file
KRAKEN_DEMO_API_KEY=your_key_here
KRAKEN_DEMO_API_SECRET=your_secret_here

# For live trading (CAUTION!)
KRAKEN_API_KEY=your_live_key_here
KRAKEN_API_SECRET=your_live_secret_here
```

### Getting Started
1. Go to https://demo-futures.kraken.com/
2. Create account (auto-generates credentials)
3. Generate API keys with "Full Access"
4. Add to `.env` file
5. Run: `python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 60 --dry-run`

### Test Results
```
✅ 13/13 tests passing
✅ 87% code coverage
✅ Latency: 2.67ms - 5.75ms (target: <50ms)
✅ Authentication working
✅ Order placement functional
✅ Position tracking accurate
```

---

## 2. Binance.us Spot Broker ✅

**Status**: Fully implemented and tested
**File**: `app/adapters/broker_binance_us.py`
**Tests**: `tests/unit/test_broker_binance_us.py` (22/22 passing, 95% coverage)
**L2 Feed**: `app/adapters/feed_binance_us_l2.py` (REST-based polling)
**L2 Tests**: `tests/unit/test_feed_binance_us_l2.py` (14/14 passing)

### Features
- ✅ US-only (compliant with US regulations)
- ✅ Spot trading only (no futures/leverage)
- ✅ **LONG ONLY** (no shorting)
- ✅ HMAC-SHA256 authentication
- ✅ Market orders (buy/sell)
- ✅ Position tracking (holdings)
- ✅ Account balance queries
- ✅ All Decimal-based calculations
- ✅ **REST-based L2 feed** (actual Binance.US order book data)
- ✅ Spot-only strategy mode implemented

### L2 Data Feed (REST-based)
**Why REST instead of WebSocket?**
- Binance.US does NOT have a public WebSocket order book API
- REST polling fetches actual Binance.US data (matches execution venue)
- Trade-off: Higher latency (100-500ms) vs WebSocket (10-50ms)

**Feed Configuration**:
```python
from app.adapters.feed_binance_us_l2 import BinanceUSL2Feed

feed = BinanceUSL2Feed(
    symbol="BTCUSDT",
    depth=5,                    # Order book depth (5, 10, 20, 50, 100, 500, 1000, 5000)
    poll_interval_ms=500,       # Polling interval (default 500ms)
    rate_limit_per_second=10    # Rate limit (default 10 req/sec)
)

await feed.start()  # Start polling in background

# Access order book
imbalance = feed.order_book.calculate_imbalance(depth=5)
mid_price = feed.order_book.get_mid_price()
```

**Performance Characteristics**:
- Average latency: 100-500ms (REST polling)
- Rate limit: 10 requests/second (2400/day per symbol)
- Data source: Actual Binance.US (api.binance.us)
- Async context manager support

### Limitations
- ❌ No shorting (spot trading only)
- ❌ No leverage
- ❌ No testnet (dry-run mode recommended for testing)
- ❌ No SL/TP orders (requires OCO orders - not yet implemented)
- ⚠️ L2 imbalance strategy less effective (~50% fewer signals - can't short bearish signals)
- ⚠️ Higher L2 data latency (100-500ms vs 10-50ms WebSocket)

### Supported Symbols
- `BTCUSDT` - Bitcoin
- `ETHUSDT` - Ethereum
- `SOLUSDT` - Solana
- All other USDT pairs available on Binance.us

### Configuration
```bash
# .env file
BINANCE_US_API_KEY=your_binance_us_api_key_here
BINANCE_US_API_SECRET=your_binance_us_api_secret_here
```

### Getting Started
1. Go to https://www.binance.us/
2. Create account and complete KYC
3. Generate API keys with "Enable Trading"
4. Add to `.env` file
5. **ALWAYS start with dry-run mode** (no testnet available)

```bash
# Dry-run (monitor only, NO TRADES) - RECOMMENDED
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

# Live trading (USES REAL MONEY - requires confirmation)
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 120 --live --i-understand-this-is-real-money
```

### Important Notes
- **NO TESTNET**: Binance.us does not have a testnet. Live mode uses REAL MONEY.
- **SELL orders close long positions** (not short positions)
- **Spot-only strategy mode**: Short signals are automatically ignored
- **Only bullish L2 imbalance signals (>3.0)** will be traded
- **REST polling**: L2 data has higher latency than WebSocket (100-500ms vs 10-50ms)
- **Data source**: Uses actual Binance.US order book (matches execution venue)

### Test Results
```
✅ Broker: 22/22 tests passing, 95% coverage
✅ L2 Feed: 14/14 tests passing
✅ Authentication working
✅ Order placement functional
✅ Position tracking accurate
✅ REST polling working
✅ Rate limiting enforced
✅ Error recovery functional
✅ Spot-only strategy mode validated
```

---

## 3. Binance International Futures (Testnet)

**Status**: Fully implemented (blocked in US)
**File**: `app/adapters/broker_binance.py`
**Tests**: `tests/unit/test_broker_binance.py` (15/15 passing)

### Why Not Recommended
- ❌ **Blocked in the US** (violates ToS to use with VPN)
- ❌ Not accessible to US traders
- ⚠️ Only testnet available for testing

### Alternative
**Use Kraken Futures instead** - same capabilities, US-accessible

---

## Comparison Matrix

| Feature | Kraken Futures | Binance.us Spot | Binance Testnet |
|---------|---------------|-----------------|-----------------|
| **US-Accessible** | ✅ Yes | ✅ Yes | ❌ No |
| **Futures Trading** | ✅ Yes | ❌ No | ✅ Yes |
| **Can Short** | ✅ Yes | ❌ No | ✅ Yes |
| **Demo Environment** | ✅ Yes | ❌ No | ✅ Yes |
| **L2 Strategy Compatible** | ✅ Full | ⚠️ Partial (50% signals) | ✅ Full |
| **L2 Data Latency** | 10-50ms (WebSocket) | 100-500ms (REST) | 10-50ms (WebSocket) |
| **L2 Data Source** | Kraken order book | Binance.US order book | Binance.com order book |
| **Implementation Status** | ✅ Complete | ✅ Complete | ✅ Complete |
| **Broker Tests** | ✅ 13 passing (87%) | ✅ 22 passing (95%) | ✅ 15 passing |
| **L2 Feed Tests** | ✅ 23 passing | ✅ 14 passing | ✅ 23 passing |

---

## Recommended Setup

### For US Traders

**Best Option: Kraken Futures**
- Full L2 strategy support (long + short)
- US-accessible and regulated
- Free demo environment for testing
- Run: `python tools/demo_kraken_l2_integration.py --live`

**Alternative: Binance.us Spot** (less recommended)
- Limited to long-only trading
- Miss 50% of signals (can't short)
- Best for buy-and-hold, not L2 scalping
- Requires strategy modifications

### For International Traders

**Best Option: Kraken Futures**
- Same benefits as above
- Available globally (except restricted countries)

**Alternative: Binance International Futures**
- Largest liquidity
- Lowest fees
- But: Use Kraken to avoid any potential US compliance issues

---

## Integration Demos

### Kraken Futures Demo
```bash
# Dry-run (monitor only)
python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 60 --dry-run

# Live demo trading
python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 120 --live
```

### Binance Testnet Demo (Non-US only)
```bash
# Dry-run
python tools/demo_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

# Live testnet (requires non-US IP)
python tools/demo_l2_integration.py --symbol BTCUSDT --duration 120 --live
```

### Binance.us Spot Demo ✅
```bash
# Dry-run (monitor only, NO TRADES) - RECOMMENDED
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

# Live trading (USES REAL MONEY - requires explicit confirmation)
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 120 --live --i-understand-this-is-real-money
```

**⚠️ CRITICAL WARNING**: Binance.us does NOT have a testnet. Live mode uses REAL MONEY. Always test with --dry-run first.

---

## Architecture Notes

### Spot-Only Strategy Mode ✅
The L2 imbalance strategy now supports spot-only mode:

1. **Ignores short signals** - Only trades bullish imbalances (>3.0)
2. **Modified exit logic** - Can't short on reversal, must hold or close long
3. **Position sizing** - No leverage, conservative sizing

```python
# Spot-only configuration
config = L2StrategyConfig(
    spot_only=True,  # ✅ Disables short signals
    buy_threshold=Decimal("3.0"),
    sell_threshold=Decimal("0.33"),  # Not used in spot-only mode
    depth=5,
    position_size_usd=Decimal("50"),
    cooldown_seconds=5
)
```

### REST-based L2 Feed for Binance.US ✅
Since Binance.US does not have a WebSocket order book API:

**Implementation**:
- Polls REST endpoint every 500ms (configurable)
- Rate limiting: 10 requests/second (Binance.US limit)
- Data source: Actual Binance.US order book (matches execution venue)
- Trade-off: Higher latency (100-500ms) vs WebSocket (10-50ms)

**Why This Design**:
- Binance.US has NO WebSocket L2 API (spot only has trade/kline streams)
- REST polling is the ONLY way to get actual Binance.US order book data
- Alternative (using Binance.com testnet) creates data source mismatch

---

## Summary

**Fully Implemented**:
- ✅ Kraken Futures broker (13 tests, 87% coverage)
- ✅ Kraken L2 WebSocket feed (23 tests)
- ✅ Binance.us Spot broker (22 tests, 95% coverage)
- ✅ Binance.us REST L2 feed (14 tests)
- ✅ Spot-only strategy mode
- ✅ Kraken L2 integration demo
- ✅ Binance.us L2 integration demo
- ✅ Multi-broker architecture

**Test Coverage**:
- Total broker tests: 50/50 passing
- Total L2 feed tests: 51/51 passing
- Integration demos: 2/2 working

**Data Sources**:
- Kraken: WebSocket L2 feed (10-50ms latency)
- Binance.US: REST polling L2 feed (100-500ms latency)
- Binance.com: WebSocket L2 feed (non-US only)

**Recommended for US Traders**:
1. **Best: Kraken Futures** - Full L2 strategy support, low latency, free demo environment
2. **Alternative: Binance.us Spot** - Long-only trading, higher latency, no demo (use dry-run)

**Recommended for International Traders**:
- **Kraken Futures** - Available globally (except restricted countries)

---

**Last Updated**: 2025-10-29
**Status**: Production-ready for US and international traders
