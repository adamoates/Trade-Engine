# Adapter Interface Documentation

**Last Updated**: 2025-10-30
**Status**: Official Documentation
**Phase**: 0 → 1 Transition

---

## Overview

This directory contains complete specifications for all adapter interfaces in the MFT trading system. Adapters abstract exchange-specific details and provide consistent APIs for order execution, real-time data streaming, and historical data access.

---

## Documents

### Interface Specifications

1. **[Broker Interface](./broker-interface.md)**
   - Order execution and position management
   - Synchronous and async interfaces
   - Current implementations: Binance Futures, Kraken Futures, Binance.us Spot
   - Error handling, health checks, testing requirements

2. **[Feed Interface](./feed-interface.md)**
   - Real-time WebSocket data streaming
   - L2 order book depth updates
   - Current implementations: Binance Futures L2, Binance.us L2
   - Performance requirements, auto-reconnect logic

3. **[Data Source Interface](./data-source-interface.md)**
   - Historical OHLCV data via REST API
   - Ticker snapshots, trades, funding rates
   - No implementations yet (Phase 1)
   - Rate limiting, caching strategies

### Implementation Guides

4. **[How to Add New Adapters](./how-to-add-adapters.md)**
   - Step-by-step guide for adding broker, feed, and data source adapters
   - Code templates and examples
   - Testing checklist
   - Common pitfalls and solutions

---

## Quick Start

### For Using Existing Adapters

```python
# Broker (order execution)
from trade_engine.adapters.brokers.binance import BinanceFuturesBroker

broker = BinanceFuturesBroker(testnet=True)
order_id = broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))
positions = broker.positions()
```

```python
# Feed (real-time L2 order book)
from trade_engine.adapters.feeds.binance_l2 import BinanceFuturesL2Feed

feed = BinanceFuturesL2Feed(symbol="BTCUSDT")
await feed.connect()

async for message in feed.stream():
    order_book = feed.order_book
    imbalance = order_book.calculate_imbalance(depth=5)
    print(f"Imbalance: {imbalance}")
```

### For Adding New Adapters

1. Read the interface specification for your adapter type
2. Follow the step-by-step guide in [How to Add New Adapters](./how-to-add-adapters.md)
3. Implement required methods with Decimal precision
4. Write comprehensive unit and integration tests
5. Create PR for review

---

## Current Implementations

### Broker Adapters (Order Execution)

| Adapter | Type | Status | Shorting | Testnet | File |
|---------|------|--------|----------|---------|------|
| **BinanceFuturesBroker** | Futures | ✅ Production Ready | Yes | Yes | `binance.py` |
| **KrakenFuturesBroker** | Futures | ✅ Demo Tested | Yes | Yes (Demo) | `kraken.py` |
| **BinanceUSBroker** | Spot | ✅ Ready for Testing | No | No | `binance_us.py` |
| **SimulatedBroker** | Mock | ✅ Test Ready | Yes | N/A | `simulated.py` |

### Feed Adapters (Real-Time Data)

| Adapter | Type | Status | Update Interval | File |
|---------|------|--------|-----------------|------|
| **BinanceFuturesL2Feed** | WebSocket L2 | ✅ Production Ready | 100ms | `binance_l2.py` |
| **BinanceUSL2Feed** | WebSocket L2 | ✅ Ready for Testing | 100ms | `binance_us_l2.py` |

### Data Source Adapters (Historical Data)

| Adapter | Type | Status | Target Phase |
|---------|------|--------|--------------|
| **BinanceFuturesDataSource** | REST API | ⏳ Not Implemented | Phase 1 |
| **BinanceUSDataSource** | REST API | ⏳ Not Implemented | Phase 1 |
| **KrakenDataSource** | REST API | ⏳ Not Implemented | Phase 2 |

---

## Design Principles

### 1. Decimal Precision (NON-NEGOTIABLE)
All financial values (prices, quantities, P&L) **MUST** use `Decimal` type. Python floats cause rounding errors in financial calculations.

```python
# ✅ CORRECT
qty = Decimal("0.001")
price = Decimal(str(api_response["price"]))

# ❌ WRONG
qty = 0.001  # float causes rounding errors
price = float(api_response["price"])
```

### 2. Error Handling
All adapters must handle errors gracefully:
- Network timeouts → retry with exponential backoff
- Rate limits → wait and retry
- Invalid parameters → raise descriptive exceptions
- Connection loss → auto-reconnect

### 3. Observability
All operations must be logged for audit trail:
- Order placement (symbol, side, qty, order_id)
- Order rejection (reason, parameters)
- Position updates (symbol, side, qty, P&L)
- Feed connection events (connected, disconnected, reconnecting)

### 4. Testing
All adapters must have:
- Unit tests (100% coverage for critical methods)
- Integration tests (real API calls to testnet/demo)
- Decimal precision verification (no float usage)
- Error handling tests (rate limits, invalid symbols)

---

## Key Requirements

### For Broker Adapters

1. ✅ Implement `Broker` interface from `trade_engine.core.types`
2. ✅ Use Decimal for all prices, quantities, P&L
3. ✅ Support testnet/demo environment
4. ✅ Handle rate limits gracefully
5. ✅ Log all order operations
6. ✅ Provide health check methods

### For Feed Adapters

1. ✅ Implement `DataFeed` or `DataFeedAdapter` interface
2. ✅ Use SortedDict for order book (O(log n) operations)
3. ✅ Use Decimal for all prices, quantities
4. ✅ Auto-reconnect on disconnection
5. ✅ Handle stale data (no updates for >5 seconds)
6. ✅ Target <10ms processing latency

### For Data Source Adapters

1. ✅ Implement `DataSourceAdapter` interface
2. ✅ Use Decimal for OHLCV values
3. ✅ Return pandas DataFrame with standard columns
4. ✅ Enforce rate limits (requests per minute)
5. ✅ Cache immutable data (completed candles)
6. ✅ Handle pagination for large queries

---

## Performance Targets

### Broker Adapters
- Order placement: <100ms
- Position query: <200ms
- Balance query: <200ms
- Close all positions: <500ms

### Feed Adapters
- WebSocket message processing: <5ms
- Order book update (delta): <2ms
- Imbalance calculation: <1ms
- Total system latency: <50ms sustained

### Data Source Adapters
- Ticker fetch: <100ms
- OHLCV fetch (100 candles): <500ms
- OHLCV fetch (1000 candles): <2s
- Symbol list (cached): <1ms

---

## Testing Strategy

### Unit Tests
- Mock all external API calls
- Test all interface methods
- Verify Decimal usage (no float)
- Test error handling (rate limits, invalid params)
- Test signature generation (HMAC)

### Integration Tests
- Use testnet/demo environment
- Place real orders and verify fills
- Query positions and balances
- Test reconnection logic (feeds)
- Measure latency

### Manual Testing Checklist
- [ ] Place buy order on testnet
- [ ] Place sell order on testnet
- [ ] Close position
- [ ] Query balance
- [ ] Query positions
- [ ] Test with invalid symbol (expect error)
- [ ] Test with insufficient balance (expect error)
- [ ] Connect to WebSocket feed (feeds only)
- [ ] Verify order book updates (feeds only)
- [ ] Disconnect and reconnect (feeds only)

---

## Common Patterns

### Authentication (Broker & Data Source)
```python
def _sign(self, params: dict) -> str:
    """Generate HMAC SHA256 signature."""
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    signature = hmac.new(
        self.api_secret.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### Rate Limiting (All Adapters)
```python
async def _enforce_rate_limit(self):
    """Ensure we don't exceed rate limit."""
    now = time.time()
    self._request_times = [t for t in self._request_times if now - t < 60]

    if len(self._request_times) >= self._rate_limit:
        sleep_time = 60 - (now - self._request_times[0])
        await asyncio.sleep(sleep_time)
        self._request_times.clear()

    self._request_times.append(now)
```

### Order Book Maintenance (Feeds)
```python
def apply_delta(self, data: dict):
    """Apply incremental order book update."""
    for price_str, qty_str in data.get('b', []):
        price = Decimal(price_str)
        qty = Decimal(qty_str)

        if qty == 0:
            self.bids.pop(price, None)  # Remove level
        else:
            self.bids[price] = qty  # Update level
```

---

## Security Best Practices

### 1. API Credentials
```python
# ✅ CORRECT - Load from environment
api_key = os.getenv("EXCHANGE_API_KEY")
if not api_key:
    raise ValueError("Missing API credentials")

# ❌ WRONG - Hardcoded
api_key = "my_secret_key_123"
```

### 2. Logging
```python
# ✅ CORRECT - Mask sensitive data
logger.info(f"API key: {api_key[:8]}...")

# ❌ WRONG - Log full credentials
logger.info(f"API key: {api_key}")
```

### 3. Input Validation
```python
# ✅ CORRECT - Validate inputs
if not self.supports_timeframe(timeframe):
    raise ValueError(f"Unsupported timeframe: {timeframe}")

# ❌ WRONG - Pass directly to API
response = requests.get(f"{self.base_url}/klines?interval={timeframe}")
```

---

## Related Documentation

- **[CLAUDE.md](../../.claude/CLAUDE.md)**: Project coding standards and patterns
- **[Architecture](../architecture/)**: System design and component relationships
- **[Guides](../guides/)**: User guides for various features
- **[Action Plan](../reports/action-plan.md)**: Infrastructure improvement roadmap

---

## Questions?

- **Interface questions**: Read the specification docs in this directory
- **Implementation questions**: See [How to Add New Adapters](./how-to-add-adapters.md)
- **Exchange API questions**: Consult exchange API documentation
- **Code review**: Create PR and request review from maintainers

---

**Document Version**: 1.0
**Last Review**: 2025-10-30
**Next Review**: Phase 1 completion
