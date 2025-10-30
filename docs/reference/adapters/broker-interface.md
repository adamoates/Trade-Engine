# Broker Adapter Interface Specification

**Last Updated**: 2025-10-30
**Status**: Official Specification
**Phase**: 0 → 1 Transition

---

## Overview

The **Broker Adapter** interface defines the contract for all broker implementations in the MFT trading system. This interface abstracts exchange-specific details and provides a consistent API for order execution and position management.

**Key Design Principles**:
1. **Type Safety**: All financial values use `Decimal` (NON-NEGOTIABLE)
2. **Error Handling**: All methods must handle failures gracefully
3. **Idempotency**: Order operations should be idempotent where possible
4. **Observability**: All operations must be logged for audit trail

---

## Interface Hierarchy

The system has **two broker interfaces** serving different purposes:

### 1. Core Broker Interface (`trade_engine.core.types.Broker`)
**Location**: `src/trade_engine/core/types.py`
**Purpose**: Synchronous interface for live trading engine
**Use Case**: Direct integration with trading strategies

**Required Methods**:
```python
def buy(symbol: str, qty: Decimal, sl: Decimal | None, tp: Decimal | None) -> str
def sell(symbol: str, qty: Decimal, sl: Decimal | None, tp: Decimal | None) -> str
def close_all(symbol: str) -> None
def positions() -> Dict[str, Position]
def balance() -> Decimal
```

### 2. Extended Broker Adapter (`trade_engine.adapters.brokers.base.BrokerAdapter`)
**Location**: `src/trade_engine/adapters/brokers/base.py`
**Purpose**: Async interface with advanced capabilities
**Use Case**: Full-featured exchange integration

**Required Methods**:
```python
async def place_order(...) -> Dict
async def cancel_order(order_id: str, symbol: str) -> Dict
async def get_order_status(order_id: str, symbol: str) -> Dict
async def get_balance(asset: Optional[str]) -> Dict
async def get_position(symbol: Optional[str]) -> Dict
async def get_ticker(symbol: str) -> Dict
def supports_shorting() -> bool
def get_min_order_size(symbol: str) -> Decimal
def validate_order(...) -> tuple[bool, Optional[str]]
```

---

## Method Specifications

### Core Interface Methods

#### `buy(symbol: str, qty: Decimal, sl: Decimal | None, tp: Decimal | None) -> str`

Place buy order (long entry or short exit).

**Arguments**:
- `symbol` (str): Trading pair in exchange-specific format (e.g., "BTCUSDT")
- `qty` (Decimal): Quantity in base currency (e.g., `Decimal("0.01")` BTC)
- `sl` (Decimal | None): Stop loss price (optional)
- `tp` (Decimal | None): Take profit price (optional)

**Returns**:
- `str`: Exchange order ID

**Raises**:
- `BrokerError`: On exchange errors, insufficient balance, rate limits, etc.

**Implementation Requirements**:
- ✅ Must use MARKET orders for immediate execution
- ✅ Must convert Decimal to string for API transmission
- ✅ Must log order placement with all parameters
- ✅ Must handle API rate limits gracefully
- ✅ SL/TP should be placed as separate conditional orders if supported
- ✅ Must return order ID immediately (don't wait for fill)

**Example**:
```python
order_id = broker.buy(
    symbol="BTCUSDT",
    qty=Decimal("0.001"),
    sl=Decimal("49500.00"),
    tp=Decimal("51000.00")
)
# Returns: "123456789"
```

---

#### `sell(symbol: str, qty: Decimal, sl: Decimal | None, tp: Decimal | None) -> str`

Place sell order (short entry or long exit).

**Specifications**: Same as `buy()`, but places SELL order.

---

#### `close_all(symbol: str) -> None`

Flatten all positions for a symbol (market order).

**Arguments**:
- `symbol` (str): Trading pair to close

**Implementation Requirements**:
- ✅ Must fetch current position first
- ✅ Must place opposite market order (long → sell, short → buy)
- ✅ Must handle "no position" case gracefully (log warning, don't error)
- ✅ Must cancel any open orders for symbol before closing
- ✅ Should complete in <500ms (critical for risk management)

**Example**:
```python
broker.close_all("BTCUSDT")
# Closes 0.001 BTC long position with market sell order
```

---

#### `positions() -> Dict[str, Position]`

Get current open positions.

**Returns**:
- `Dict[str, Position]`: Mapping of symbol → Position object
- Empty dict if no positions

**Position Object Fields**:
```python
@dataclass
class Position:
    symbol: str
    side: str              # "long" | "short"
    qty: Decimal           # Position size (absolute value)
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal           # Unrealized P&L (USD)
    pnl_pct: Decimal       # Unrealized P&L (%)
```

**Implementation Requirements**:
- ✅ Must return Decimal for all financial values
- ✅ `qty` must be absolute value (unsigned)
- ✅ `side` determines direction ("long" or "short")
- ✅ Must calculate `pnl_pct` correctly based on side
- ✅ Should cache results for 1-5 seconds to reduce API calls

**Example**:
```python
positions = broker.positions()
# Returns: {
#   "BTCUSDT": Position(
#       symbol="BTCUSDT",
#       side="long",
#       qty=Decimal("0.001"),
#       entry_price=Decimal("50000.00"),
#       current_price=Decimal("51000.00"),
#       pnl=Decimal("1.00"),
#       pnl_pct=Decimal("2.00")
#   )
# }
```

---

#### `balance() -> Decimal`

Get available trading balance (USDT or USD).

**Returns**:
- `Decimal`: Available balance for trading

**Implementation Requirements**:
- ✅ Must return Decimal (not float)
- ✅ Should return only available balance (not total or margin)
- ✅ Must handle multi-asset accounts (return USDT/USD balance specifically)

**Example**:
```python
balance = broker.balance()
# Returns: Decimal("9850.00")  # $9,850 available
```

---

## Extended Interface Methods

### `async def place_order(...) -> Dict`

More flexible order placement with support for limit orders, post-only, etc.

**Arguments**:
- `symbol` (str): Trading pair
- `side` (str): "buy" or "sell"
- `order_type` (str): "market", "limit", "stop_market", "stop_limit"
- `quantity` (Decimal): Order size
- `price` (Decimal | None): Limit price (required for limit orders)
- `**kwargs`: Exchange-specific parameters (e.g., `timeInForce`, `reduceOnly`)

**Returns**:
```python
{
    "order_id": "123456789",
    "status": "filled" | "open" | "cancelled",
    "filled_qty": Decimal("0.001"),
    "avg_price": Decimal("50000.00"),
    "timestamp": 1635724800000
}
```

---

### `async def cancel_order(order_id: str, symbol: str) -> Dict`

Cancel an open order.

**Implementation Requirements**:
- ✅ Must handle "order not found" gracefully (already filled/cancelled)
- ✅ Must return cancellation status
- ✅ Should complete in <200ms

---

### `async def get_order_status(order_id: str, symbol: str) -> Dict`

Get detailed order status.

**Returns**:
```python
{
    "order_id": "123456789",
    "status": "filled",
    "filled_qty": Decimal("0.001"),
    "remaining_qty": Decimal("0.000"),
    "avg_price": Decimal("50000.12"),
    "timestamp": 1635724800000
}
```

---

### `def supports_shorting() -> bool`

Check if broker supports short selling.

**Returns**:
- `True`: Futures/margin account (Binance Futures, Kraken Futures)
- `False`: Spot-only account (Binance.us, Coinbase)

**Usage**:
```python
if not broker.supports_shorting():
    # Skip bearish signals in spot-only mode
    strategy.config.spot_only = True
```

---

### `def get_min_order_size(symbol: str) -> Decimal`

Get minimum order size for symbol.

**Returns**:
- `Decimal`: Minimum order quantity in base currency

**Example**:
```python
min_size = broker.get_min_order_size("BTCUSDT")
# Returns: Decimal("0.001")  # 0.001 BTC minimum
```

---

### `def validate_order(...) -> tuple[bool, Optional[str]]`

Pre-validate order before submission.

**Returns**:
- `(True, None)`: Order is valid
- `(False, "error message")`: Order is invalid

**Validation Checks**:
1. Quantity >= minimum order size
2. Sufficient balance
3. Valid symbol
4. Price within tick size
5. Not exceeding position limits

**Usage**:
```python
is_valid, error = broker.validate_order(
    symbol="BTCUSDT",
    side="buy",
    quantity=Decimal("0.001"),
    price=Decimal("50000.00")
)

if not is_valid:
    logger.warning(f"Invalid order: {error}")
    return  # Skip order placement
```

---

## Current Implementations

### 1. BinanceFuturesBroker
**File**: `src/trade_engine/adapters/brokers/binance.py`
**Type**: Futures (supports long + short)
**Environment**: Testnet + Live
**Authentication**: HMAC-SHA256
**Status**: ✅ Production Ready (100% Decimal)

**Features**:
- Market order execution
- Position tracking via `/fapi/v2/positionRisk`
- Balance via `/fapi/v2/balance`
- Leverage + margin type configuration
- Cancel all orders

**Limitations**:
- SL/TP not yet implemented (TODO)
- No retry logic (single attempt)
- No rate limit handling

---

### 2. KrakenFuturesBroker
**File**: `src/trade_engine/adapters/brokers/kraken.py`
**Type**: Futures (supports long + short)
**Environment**: Demo + Live
**Authentication**: HMAC-SHA512 (2024 method)
**Status**: ✅ Tested in Demo (100% Decimal)

**Features**:
- Market order execution
- Demo environment support (US-accessible)
- HMAC-SHA512 authentication
- Position + balance queries

**Limitations**:
- No WebSocket support yet
- No cancel_order implementation
- No get_order_status implementation

---

### 3. BinanceUSBroker
**File**: `src/trade_engine/adapters/brokers/binance_us.py`
**Type**: Spot (long-only, no shorting)
**Environment**: Live only (no testnet)
**Authentication**: HMAC-SHA256
**Status**: ✅ Ready for Testing (100% Decimal)

**Features**:
- Spot market orders
- US-compliant (no futures)
- Compatible with spot-only strategy mode
- Balance tracking

**Limitations**:
- Cannot short (spot-only)
- No leverage
- No SL/TP orders

---

### 4. SimulatedBroker
**File**: `src/trade_engine/adapters/brokers/simulated.py`
**Type**: Mock (for testing)
**Environment**: Local only
**Status**: ✅ Test Ready

**Features**:
- Instant fills at market price
- Configurable balance
- Position tracking
- No API calls

---

## Error Handling Requirements

### Exception Hierarchy

```python
class BrokerError(Exception):
    """Base exception for all broker errors."""
    pass

class InsufficientBalanceError(BrokerError):
    """Raised when account balance is too low."""
    pass

class RateLimitError(BrokerError):
    """Raised when API rate limit exceeded."""
    pass

class OrderRejectedError(BrokerError):
    """Raised when exchange rejects order."""
    pass

class ConnectionError(BrokerError):
    """Raised when unable to connect to exchange."""
    pass
```

### Retry Logic

**Required for**:
- Network errors (3 retries, exponential backoff)
- Rate limit errors (wait + retry)
- 5xx server errors (2 retries)

**DO NOT retry**:
- 4xx client errors (invalid parameters)
- Insufficient balance errors
- Order rejection errors

**Example**:
```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def _request_with_retry(self, method, endpoint, **params):
    try:
        return self._request(method, endpoint, **params)
    except RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        time.sleep(1)
        raise  # Will retry
    except InsufficientBalanceError:
        raise  # Don't retry
```

---

## Logging Requirements

### Required Log Events

**Order Placement**:
```python
logger.info(
    "order_placed",
    symbol="BTCUSDT",
    side="BUY",
    qty=str(qty),
    order_id=order_id,
    timestamp=int(time.time())
)
```

**Order Rejection**:
```python
logger.error(
    "order_rejected",
    symbol="BTCUSDT",
    side="BUY",
    qty=str(qty),
    reason=error_message,
    timestamp=int(time.time())
)
```

**Position Update**:
```python
logger.debug(
    "position_updated",
    symbol="BTCUSDT",
    side="long",
    qty=str(position.qty),
    pnl=str(position.pnl),
    timestamp=int(time.time())
)
```

---

## Testing Requirements

### Unit Tests

**Required Test Coverage**:
1. ✅ Signature generation (HMAC correctness)
2. ✅ Order placement (buy, sell)
3. ✅ Position parsing (long, short, zero)
4. ✅ Balance retrieval
5. ✅ Close all positions
6. ✅ Error handling (insufficient balance, rate limits)
7. ✅ Decimal precision (no float usage)

**Example**:
```python
def test_buy_success():
    broker = BinanceFuturesBroker(testnet=True)
    broker._request = Mock(return_value={"orderId": 123456789})

    order_id = broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))

    assert order_id == "123456789"
    assert broker._request.called
```

### Integration Tests

**Required Tests**:
1. ✅ Place real order on testnet
2. ✅ Query position after order
3. ✅ Close position
4. ✅ Verify balance changes

---

## Health Check Methods

### Latency Monitoring

```python
def get_latency_ms(self) -> float:
    """Measure API latency (ping endpoint)."""
    start = time.time()
    self._request("GET", "/fapi/v1/ping")
    return (time.time() - start) * 1000
```

### Rate Limit Status

```python
def get_rate_limit_status(self) -> Dict[str, int]:
    """Get current rate limit status.

    Returns:
        {
            "used": 1200,      # Requests used
            "limit": 2400,     # Request limit
            "reset_at": 1635724860  # Unix timestamp
        }
    """
    pass
```

### Connection Health

```python
def is_healthy(self) -> tuple[bool, str]:
    """Check if broker connection is healthy.

    Returns:
        (True, "OK") if healthy
        (False, "reason") if unhealthy
    """
    try:
        latency = self.get_latency_ms()
        if latency > 500:
            return (False, f"High latency: {latency:.0f}ms")

        balance = self.balance()
        if balance == Decimal("0"):
            return (False, "Zero balance")

        return (True, "OK")
    except Exception as e:
        return (False, f"Connection error: {e}")
```

---

## Best Practices

### 1. Decimal Usage (NON-NEGOTIABLE)
```python
# ✅ CORRECT
qty = Decimal("0.001")
price = Decimal(str(api_response["price"]))

# ❌ WRONG
qty = 0.001  # float causes rounding errors
price = float(api_response["price"])
```

### 2. Symbol Format Normalization
```python
def normalize_symbol(self, symbol: str) -> str:
    """Convert standard format to exchange format.

    Standard: "BTC/USDT"
    Binance: "BTCUSDT"
    Kraken: "PF_XBTUSD"
    """
    pass
```

### 3. Order Size Rounding
```python
def round_quantity(self, symbol: str, qty: Decimal) -> Decimal:
    """Round quantity to exchange lot size.

    Example:
        Binance BTC lot size = 0.001
        Input: 0.00123 → Output: 0.001
    """
    lot_size = self.get_lot_size(symbol)
    return (qty // lot_size) * lot_size
```

### 4. Price Rounding
```python
def round_price(self, symbol: str, price: Decimal) -> Decimal:
    """Round price to exchange tick size.

    Example:
        Binance BTC tick size = 0.01
        Input: 50000.123 → Output: 50000.12
    """
    tick_size = self.get_tick_size(symbol)
    return (price // tick_size) * tick_size
```

---

## Next Steps

### For Implementing New Brokers

See [how-to-add-adapters.md](./how-to-add-adapters.md) for step-by-step guide.

### For Adding Health Checks

See [Item #8: Add adapter health check methods](../../docs/reports/action-plan.md) in action plan.

### For Integration Testing

See [test_broker_adapter_template.py](../../tests/integration/adapters/test_broker_adapter_template.py) (to be created).

---

**Document Version**: 1.0
**Last Review**: 2025-10-30
**Next Review**: Phase 1 completion
