# Data Feed Adapter Interface Specification

**Last Updated**: 2025-10-30
**Status**: Official Specification
**Phase**: 0 → 1 Transition

---

## Overview

The **Data Feed Adapter** interface defines the contract for all real-time market data feeds in the MFT trading system. This interface abstracts exchange-specific WebSocket protocols and provides a consistent API for streaming order books, trades, and tickers.

**Key Design Principles**:
1. **Low Latency**: Target <10ms processing time per message
2. **Type Safety**: All price/quantity values use `Decimal` (NON-NEGOTIABLE)
3. **Reliability**: Auto-reconnect on disconnection, handle staleness
4. **Efficiency**: Use sorted data structures (SortedDict) for O(log n) operations

---

## Interface Hierarchy

The system has **two feed interfaces** serving different purposes:

### 1. Core DataFeed Interface (`trade_engine.core.types.DataFeed`)
**Location**: `src/trade_engine.core/types.py`
**Purpose**: Synchronous iterator for bar-based strategies
**Use Case**: Simple candlestick-based strategies

**Required Methods**:
```python
def candles() -> Iterator[Bar]:
    """Yield completed, validated OHLCV bars."""
    pass
```

### 2. Extended DataFeed Adapter (`trade_engine.adapters.feeds.base.DataFeedAdapter`)
**Location**: `src/trade_engine/adapters/feeds/base.py`
**Purpose**: Async WebSocket streaming with pub/sub
**Use Case**: Real-time L2 order book, tick data, trade streams

**Required Methods**:
```python
async def connect() -> None
async def disconnect() -> None
async def subscribe(symbol: str, channel: str, callback: Optional[Callable]) -> None
async def unsubscribe(symbol: str, channel: str) -> None
async def stream() -> AsyncIterator[Dict]
def is_connected() -> bool
def get_subscriptions() -> List[tuple[str, str]]
async def ping() -> bool
```

---

## Method Specifications

### Core Interface Method

#### `candles() -> Iterator[Bar]`

Yield validated OHLCV bars (bar-close only).

**Returns**:
- `Iterator[Bar]`: Generator yielding completed bars

**Bar Object**:
```python
@dataclass
class Bar:
    timestamp: int       # UTC timestamp (milliseconds)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    gap_flag: bool       # True if bar was filled/imputed
    zero_vol_flag: bool  # True if zero volume (should skip)
```

**Implementation Requirements**:
- ✅ Only yield completed bars (not partial)
- ✅ Validate bar quality (no gaps, no zero volume)
- ✅ Set `gap_flag`, `zero_vol_flag` appropriately
- ✅ Sleep until next bar close
- ✅ Use Decimal for OHLCV values

**Example**:
```python
feed = BinanceFuturesDataFeed(symbol="BTCUSDT", timeframe="1m")

for bar in feed.candles():
    if bar.zero_vol_flag:
        continue  # Skip zero-volume bars

    if bar.gap_flag:
        logger.warning(f"Data gap detected: {bar}")

    print(f"Close: {bar.close}, Volume: {bar.volume}")
```

---

## Extended Interface Methods

### `async def connect() -> None`

Establish WebSocket connection to exchange.

**Implementation Requirements**:
- ✅ Must establish WebSocket connection
- ✅ Must handle connection timeout (<5 seconds)
- ✅ Must log connection success/failure
- ✅ Must set `self._connected = True` on success

**Raises**:
- `ConnectionError`: If connection fails after retries

**Example**:
```python
feed = BinanceFuturesL2Feed(symbol="BTCUSDT")
await feed.connect()
# WebSocket connected to wss://fstream.binance.com
```

---

### `async def disconnect() -> None`

Close WebSocket connection gracefully.

**Implementation Requirements**:
- ✅ Must close WebSocket connection
- ✅ Must clean up resources (clear buffers, cancel tasks)
- ✅ Must set `self._connected = False`
- ✅ Must not raise exceptions (idempotent)

**Example**:
```python
await feed.disconnect()
# Connection closed, resources cleaned up
```

---

### `async def subscribe(symbol: str, channel: str, callback: Optional[Callable]) -> None`

Subscribe to a data channel (order book, trades, ticker).

**Arguments**:
- `symbol` (str): Trading pair (e.g., "BTCUSDT")
- `channel` (str): Channel type ("orderbook", "trades", "ticker", "kline")
- `callback` (Optional[Callable]): Optional callback function for each message

**Implementation Requirements**:
- ✅ Must send subscription message to exchange
- ✅ Must store subscription in `self._subscriptions`
- ✅ Must handle "already subscribed" case gracefully
- ✅ Must log subscription success

**Example**:
```python
def handle_orderbook_update(data: dict):
    print(f"Best bid: {data['bids'][0][0]}")

await feed.subscribe(
    symbol="BTCUSDT",
    channel="orderbook",
    callback=handle_orderbook_update
)
```

---

### `async def unsubscribe(symbol: str, channel: str) -> None`

Unsubscribe from a data channel.

**Implementation Requirements**:
- ✅ Must send unsubscribe message to exchange
- ✅ Must remove subscription from `self._subscriptions`
- ✅ Must handle "not subscribed" case gracefully

---

### `async def stream() -> AsyncIterator[Dict]`

Stream incoming data messages.

**Yields**:
- `Dict`: Normalized data message

**Message Format**:
```python
{
    "type": "orderbook_update" | "trade" | "ticker",
    "symbol": "BTCUSDT",
    "timestamp": 1635724800123,  # Unix timestamp (ms)
    "data": {
        # Type-specific data (see below)
    }
}
```

**Implementation Requirements**:
- ✅ Must normalize exchange-specific formats to standard format
- ✅ Must yield messages in order received
- ✅ Must handle reconnection gracefully (resume from last update)
- ✅ Must filter out heartbeat/ping messages

**Example**:
```python
async for message in feed.stream():
    if message["type"] == "orderbook_update":
        update_order_book(message["data"])
    elif message["type"] == "trade":
        process_trade(message["data"])
```

---

### `def is_connected() -> bool`

Check if feed is currently connected.

**Returns**:
- `True`: WebSocket connected and receiving messages
- `False`: Disconnected or connection lost

**Implementation**:
```python
def is_connected(self) -> bool:
    if not self._connected:
        return False

    # Check if last message was recent (<10 seconds)
    if time.time() - self._last_message_time > 10:
        return False

    return True
```

---

### `def get_subscriptions() -> List[tuple[str, str]]`

Get list of active subscriptions.

**Returns**:
- `List[tuple[str, str]]`: List of (symbol, channel) pairs

**Example**:
```python
subscriptions = feed.get_subscriptions()
# Returns: [("BTCUSDT", "orderbook"), ("ETHUSDT", "trades")]
```

---

### `async def ping() -> bool`

Send ping to keep connection alive.

**Returns**:
- `True`: Ping successful (pong received)
- `False`: Ping failed (connection may be dead)

**Implementation Requirements**:
- ✅ Must send exchange-specific ping message
- ✅ Must wait for pong response (timeout 5 seconds)
- ✅ Should be called every 30-60 seconds

**Example**:
```python
# Background task to keep connection alive
async def keepalive():
    while True:
        await asyncio.sleep(30)
        is_alive = await feed.ping()
        if not is_alive:
            logger.warning("Ping failed, reconnecting...")
            await feed.reconnect()
```

---

## Order Book Data Structure

### OrderBook Class

**Location**: Included in L2 feed implementations
**Purpose**: Efficient bid/ask level tracking with sorted access

**Required Methods**:
```python
def apply_snapshot(data: dict) -> None
def apply_delta(data: dict) -> None
def calculate_imbalance(depth: int) -> Decimal
def get_mid_price() -> Decimal
def get_spread_bps() -> Decimal
def is_valid() -> bool
def get_best_bid() -> tuple[Decimal, Decimal]
def get_best_ask() -> tuple[Decimal, Decimal]
def get_top_n_levels(depth: int) -> dict
```

**Implementation Requirements**:
- ✅ Must use `SortedDict` for O(log n) operations
- ✅ Must handle both snapshots and deltas
- ✅ Must remove zero-quantity levels
- ✅ All prices/quantities must be Decimal
- ✅ Must track last update time for staleness detection

**Data Structure**:
```python
from sortedcontainers import SortedDict

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: SortedDict[Decimal, Decimal] = SortedDict()  # price → qty
        self.asks: SortedDict[Decimal, Decimal] = SortedDict()  # price → qty
        self.last_update_id = 0
        self.last_update_time = 0.0
```

---

### `apply_snapshot(data: dict) -> None`

Initialize order book from full snapshot.

**Arguments**:
- `data` (dict): Snapshot data from exchange

**Binance Format**:
```python
{
    "lastUpdateId": 1234567890,
    "bids": [["50000.00", "0.123"], ["49999.00", "0.456"], ...],
    "asks": [["50001.00", "0.789"], ["50002.00", "0.234"], ...]
}
```

**Implementation**:
```python
def apply_snapshot(self, data: dict):
    self.bids.clear()
    self.asks.clear()

    for price_str, qty_str in data['bids']:
        price = Decimal(price_str)
        qty = Decimal(qty_str)
        if qty > 0:
            self.bids[price] = qty

    for price_str, qty_str in data['asks']:
        price = Decimal(price_str)
        qty = Decimal(qty_str)
        if qty > 0:
            self.asks[price] = qty

    self.last_update_id = data['lastUpdateId']
    self.last_update_time = time.time()
```

---

### `apply_delta(data: dict) -> None`

Apply incremental delta update.

**Binance WebSocket Format**:
```python
{
    "e": "depthUpdate",
    "E": 1635724800123,  # Event time
    "s": "BTCUSDT",
    "U": 1234567891,     # First update ID
    "u": 1234567895,     # Final update ID
    "b": [["50000.00", "0.500"], ["49999.00", "0.000"]],  # Bid updates
    "a": [["50001.00", "1.200"]]  # Ask updates
}
```

**Implementation**:
```python
def apply_delta(self, data: dict):
    # Update bids
    for price_str, qty_str in data.get('b', []):
        price = Decimal(price_str)
        qty = Decimal(qty_str)

        if qty == 0:
            self.bids.pop(price, None)  # Remove level
        else:
            self.bids[price] = qty  # Update level

    # Update asks
    for price_str, qty_str in data.get('a', []):
        price = Decimal(price_str)
        qty = Decimal(qty_str)

        if qty == 0:
            self.asks.pop(price, None)
        else:
            self.asks[price] = qty

    self.last_update_id = data['u']
    self.last_update_time = time.time()
```

---

### `calculate_imbalance(depth: int) -> Decimal`

Calculate bid/ask volume ratio from top N levels.

**Arguments**:
- `depth` (int): Number of levels to include (default 5)

**Returns**:
- `Decimal`: Bid volume / Ask volume ratio
  - > 1.0: More bid pressure (bullish)
  - < 1.0: More ask pressure (bearish)
  - = 1.0: Balanced

**Implementation**:
```python
def calculate_imbalance(self, depth: int = 5) -> Decimal:
    # Get top N bids (highest prices)
    top_bids = list(self.bids.items())[-depth:]
    bid_volume = sum(qty for price, qty in top_bids)

    # Get top N asks (lowest prices)
    top_asks = list(self.asks.items())[:depth]
    ask_volume = sum(qty for price, qty in top_asks)

    if ask_volume == 0:
        return Decimal("999.0")  # Infinite imbalance (all bids)

    return bid_volume / ask_volume
```

**Example**:
```python
imbalance = order_book.calculate_imbalance(depth=5)
# Returns: Decimal("3.2")  # 3.2x more bid volume (strong buy pressure)
```

---

### `get_mid_price() -> Decimal`

Get mid-market price (average of best bid and ask).

**Returns**:
- `Decimal`: (best_bid + best_ask) / 2

**Implementation**:
```python
def get_mid_price(self) -> Decimal:
    best_bid = list(self.bids.keys())[-1]
    best_ask = list(self.asks.keys())[0]
    return (best_bid + best_ask) / Decimal("2")
```

---

### `get_spread_bps() -> Decimal`

Get bid-ask spread in basis points.

**Returns**:
- `Decimal`: Spread in basis points (1 bps = 0.01%)

**Implementation**:
```python
def get_spread_bps(self) -> Decimal:
    best_bid = list(self.bids.keys())[-1]
    best_ask = list(self.asks.keys())[0]
    mid = (best_bid + best_ask) / Decimal("2")
    spread = best_ask - best_bid
    return (spread / mid) * Decimal("10000")
```

**Example**:
```python
spread_bps = order_book.get_spread_bps()
# Returns: Decimal("5.2")  # 5.2 basis points spread
```

---

### `is_valid() -> bool`

Check if order book is valid (not stale, has data).

**Returns**:
- `True`: Order book is valid
- `False`: Order book is stale or empty

**Implementation**:
```python
def is_valid(self) -> bool:
    # Check if empty
    if len(self.bids) == 0 or len(self.asks) == 0:
        return False

    # Check if stale (no update in last 5 seconds)
    if time.time() - self.last_update_time > 5.0:
        return False

    # Check if crossed (bid > ask)
    best_bid = list(self.bids.keys())[-1]
    best_ask = list(self.asks.keys())[0]
    if best_bid >= best_ask:
        logger.error(f"Crossed book: bid={best_bid}, ask={best_ask}")
        return False

    return True
```

---

## Current Implementations

### 1. BinanceFuturesL2Feed
**File**: `src/trade_engine/adapters/feeds/binance_l2.py`
**Type**: WebSocket L2 order book depth stream
**Update Frequency**: 100ms
**Status**: ✅ Production Ready (100% Decimal)

**Features**:
- Real-time order book depth updates
- Snapshot initialization via REST
- Delta updates via WebSocket
- Imbalance calculation
- SortedDict for O(log n) top-N access

**Performance**:
- Processing latency: <5ms per update
- Memory usage: ~1MB per symbol (5000 levels)
- Update rate: ~10/second (100ms interval)

**WebSocket Endpoint**:
```
wss://fstream.binance.com/ws/{symbol}@depth@100ms
```

---

### 2. BinanceUSL2Feed
**File**: `src/trade_engine/adapters/feeds/binance_us_l2.py`
**Type**: WebSocket L2 order book depth stream (spot)
**Update Frequency**: 100ms
**Status**: ✅ Ready for Testing (100% Decimal)

**Differences from Futures**:
- Spot market (no leverage)
- Different WebSocket endpoint
- Lower liquidity (wider spreads)

**WebSocket Endpoint**:
```
wss://stream.binance.us:9443/ws/{symbol}@depth@100ms
```

---

## Error Handling Requirements

### Exception Hierarchy

```python
class FeedError(Exception):
    """Base exception for all feed errors."""
    pass

class ConnectionError(FeedError):
    """Raised when unable to connect to feed."""
    pass

class SubscriptionError(FeedError):
    """Raised when subscription fails."""
    pass

class DataStaleError(FeedError):
    """Raised when data is too old."""
    pass

class InvalidDataError(FeedError):
    """Raised when data validation fails."""
    pass
```

### Auto-Reconnect Logic

**Required for**:
- Connection drops
- Stale data (no updates for 10 seconds)
- WebSocket errors

**Implementation**:
```python
async def reconnect(self, max_attempts: int = 5):
    """Reconnect with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            logger.info(f"Reconnect attempt {attempt + 1}/{max_attempts}")
            await self.disconnect()
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            await self.connect()

            # Re-subscribe to all channels
            for symbol, channel in self._subscriptions:
                await self.subscribe(symbol, channel)

            logger.info("Reconnect successful")
            return

        except Exception as e:
            logger.error(f"Reconnect attempt {attempt + 1} failed: {e}")

    raise ConnectionError(f"Failed to reconnect after {max_attempts} attempts")
```

---

## Logging Requirements

### Required Log Events

**Connection Established**:
```python
logger.info(
    "feed_connected",
    feed_type="BinanceFuturesL2",
    symbol="BTCUSDT",
    endpoint="wss://fstream.binance.com/...",
    timestamp=int(time.time())
)
```

**Order Book Update**:
```python
logger.debug(
    "orderbook_updated",
    symbol="BTCUSDT",
    bids=len(order_book.bids),
    asks=len(order_book.asks),
    mid_price=str(order_book.get_mid_price()),
    spread_bps=str(order_book.get_spread_bps()),
    timestamp=int(time.time())
)
```

**Connection Lost**:
```python
logger.warning(
    "feed_disconnected",
    symbol="BTCUSDT",
    reason="WebSocket closed",
    reconnecting=True,
    timestamp=int(time.time())
)
```

**Stale Data Detected**:
```python
logger.error(
    "data_stale",
    symbol="BTCUSDT",
    last_update_time=last_update_time,
    age_seconds=age,
    timestamp=int(time.time())
)
```

---

## Testing Requirements

### Unit Tests

**Required Test Coverage**:
1. ✅ Order book snapshot initialization
2. ✅ Delta update application
3. ✅ Imbalance calculation (various scenarios)
4. ✅ Mid price calculation
5. ✅ Spread calculation
6. ✅ Staleness detection
7. ✅ Crossed book detection
8. ✅ Decimal precision (no float usage)

**Example**:
```python
def test_apply_snapshot():
    ob = OrderBook("BTCUSDT")
    snapshot = {
        "lastUpdateId": 123,
        "bids": [["50000.00", "0.1"], ["49999.00", "0.2"]],
        "asks": [["50001.00", "0.3"], ["50002.00", "0.4"]]
    }

    ob.apply_snapshot(snapshot)

    assert len(ob.bids) == 2
    assert len(ob.asks) == 2
    assert ob.bids[Decimal("50000.00")] == Decimal("0.1")
```

### Integration Tests

**Required Tests**:
1. ✅ Connect to WebSocket
2. ✅ Subscribe to channel
3. ✅ Receive and process 100 updates
4. ✅ Calculate imbalance from live data
5. ✅ Handle disconnection and reconnect

---

## Performance Requirements

### Latency Targets

| Operation | Target | Critical |
|-----------|--------|----------|
| WebSocket message processing | <5ms | <10ms |
| Order book update (delta) | <2ms | <5ms |
| Imbalance calculation | <1ms | <3ms |
| Top N levels access | <0.5ms | <1ms |

### Memory Constraints

| Data Structure | Max Size | Typical |
|----------------|----------|---------|
| Order book (per symbol) | 5MB | 1MB |
| Message buffer | 10MB | 2MB |
| Subscription list | 1MB | 100KB |

---

## Health Check Methods

### Latency Monitoring

```python
def get_message_latency_ms(self) -> float:
    """Measure time between exchange timestamp and processing time."""
    return (self._last_process_time - self._last_exchange_time) * 1000
```

### Data Freshness

```python
def get_data_age_seconds(self) -> float:
    """Get age of last update."""
    return time.time() - self.order_book.last_update_time
```

### Health Check

```python
def is_healthy(self) -> tuple[bool, str]:
    """Check if feed is healthy.

    Returns:
        (True, "OK") if healthy
        (False, "reason") if unhealthy
    """
    if not self.is_connected():
        return (False, "Disconnected")

    age = self.get_data_age_seconds()
    if age > 5.0:
        return (False, f"Stale data: {age:.1f}s old")

    latency = self.get_message_latency_ms()
    if latency > 100:
        return (False, f"High latency: {latency:.0f}ms")

    if not self.order_book.is_valid():
        return (False, "Invalid order book")

    return (True, "OK")
```

---

## Best Practices

### 1. Decimal Usage (NON-NEGOTIABLE)
```python
# ✅ CORRECT
price = Decimal(ws_message["bids"][0][0])
qty = Decimal(ws_message["bids"][0][1])

# ❌ WRONG
price = float(ws_message["bids"][0][0])
qty = float(ws_message["bids"][0][1])
```

### 2. SortedDict for Performance
```python
from sortedcontainers import SortedDict

# ✅ CORRECT - O(log n) access to top N
bids = SortedDict()
top_5_bids = list(bids.items())[-5:]

# ❌ WRONG - O(n log n) sorting every time
bids = {}
top_5_bids = sorted(bids.items(), reverse=True)[:5]
```

### 3. Snapshot Before Stream
```python
# ✅ CORRECT - Always initialize with snapshot first
ob = OrderBook("BTCUSDT")
snapshot = await fetch_snapshot()
ob.apply_snapshot(snapshot)

# Then start WebSocket stream
async for message in stream():
    ob.apply_delta(message)

# ❌ WRONG - Starting stream without snapshot
async for message in stream():
    ob.apply_delta(message)  # Incomplete book!
```

### 4. Staleness Detection
```python
def is_valid(self) -> bool:
    # ✅ CORRECT - Check age
    age = time.time() - self.last_update_time
    if age > 5.0:
        logger.error(f"Stale data: {age:.1f}s old")
        return False

    # ❌ WRONG - No staleness check
    return len(self.bids) > 0 and len(self.asks) > 0
```

---

## Next Steps

### For Implementing New Feeds

See [how-to-add-adapters.md](./how-to-add-adapters.md) for step-by-step guide.

### For Adding Health Checks

See [Item #8: Add adapter health check methods](../../reports/action-plan.md) in action plan.

### For Integration Testing

See [test_feed_adapter_template.py](../../tests/integration/adapters/test_feed_adapter_template.py) (to be created).

---

**Document Version**: 1.0
**Last Review**: 2025-10-30
**Next Review**: Phase 1 completion
