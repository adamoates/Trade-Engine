# How to Add New Adapters

**Last Updated**: 2025-10-30
**Audience**: Developers adding new exchange/data source integrations
**Prerequisites**: Familiarity with async Python, exchange APIs, testing

---

## Overview

This guide walks through adding new adapters to the MFT trading system. Adapters abstract exchange-specific details and provide a consistent interface for the trading engine.

**Three Types of Adapters**:
1. **Broker Adapters**: Order execution and position management
2. **Feed Adapters**: Real-time WebSocket streaming (order books, trades)
3. **Data Source Adapters**: Historical/snapshot data via REST API

---

## Before You Start

### 1. Read the Interface Specifications

- [Broker Interface Specification](./broker-interface.md)
- [Feed Interface Specification](./feed-interface.md)
- [Data Source Interface Specification](./data-source-interface.md)

### 2. Research the Exchange API

**Required Documentation**:
- API authentication method (HMAC-SHA256, API key, OAuth)
- REST API endpoints (order placement, position query, balance)
- WebSocket endpoints (order book depth, trades stream)
- Rate limits (requests per minute/second)
- Lot sizes and tick sizes per symbol
- Error codes and responses

**Example** (Binance Futures):
- REST: `https://fapi.binance.com`
- WebSocket: `wss://fstream.binance.com`
- Auth: HMAC-SHA256
- Rate limit: 2400 req/min with API key
- Lot size (BTC): 0.001
- Tick size (BTC): 0.01

### 3. Get API Credentials

**Testnet First** (if available):
- Always start with paper trading / testnet
- Verify all functionality before touching live API
- Binance testnet: https://testnet.binancefuture.com
- Kraken demo: https://demo-futures.kraken.com

**Environment Variables**:
```bash
# For testnet
export EXCHANGE_TESTNET_API_KEY="your_testnet_key"
export EXCHANGE_TESTNET_API_SECRET="your_testnet_secret"

# For live (Phase 6+)
export EXCHANGE_API_KEY="your_live_key"
export EXCHANGE_API_SECRET="your_live_secret"
```

---

## Part 1: Adding a Broker Adapter

### Step 1: Create the File

```bash
touch src/trade_engine/adapters/brokers/exchange_name.py
```

**Naming Convention**:
- `binance.py` for Binance Futures
- `kraken.py` for Kraken Futures
- `coinbase.py` for Coinbase
- `exchange_name_spot.py` for spot-only versions

### Step 2: Implement the Interface

```python
"""
Exchange Name broker adapter (paper & live).

Implements Broker interface for Exchange Name.
Supports both testnet (paper trading) and production.

CRITICAL: All price/quantity conversions use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

import os
import time
import hmac
import hashlib
from decimal import Decimal
from typing import Dict, Optional
import requests
from loguru import logger

from trade_engine.core.types import Broker, Position


class ExchangeError(Exception):
    """Exchange API errors."""
    pass


class ExchangeBroker(Broker):
    """
    Exchange Name broker (testnet or live).

    Usage:
        # Testnet (paper trading)
        broker = ExchangeBroker(testnet=True)

        # Live (real money)
        broker = ExchangeBroker(testnet=False)

    Environment variables required:
        EXCHANGE_API_KEY       (or EXCHANGE_TESTNET_API_KEY for testnet)
        EXCHANGE_API_SECRET    (or EXCHANGE_TESTNET_API_SECRET for testnet)
    """

    TESTNET_BASE = "https://testnet.exchange.com"
    LIVE_BASE = "https://api.exchange.com"

    def __init__(self, testnet: bool = True):
        """Initialize broker."""
        self.testnet = testnet
        self.base_url = self.TESTNET_BASE if testnet else self.LIVE_BASE

        # Load API credentials
        env_prefix = "EXCHANGE_TESTNET" if testnet else "EXCHANGE"
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ExchangeError(
                f"Missing API credentials. Set {env_prefix}_API_KEY and {env_prefix}_API_SECRET"
            )

        logger.info(
            f"ExchangeBroker initialized ({'TESTNET' if testnet else '⚠️ LIVE'})"
        )

    def _sign(self, params: dict) -> str:
        """Generate HMAC SHA256 signature (adjust for exchange)."""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, signed: bool = False, **params):
        """Make API request with error handling."""
        url = self.base_url + endpoint
        headers = {"X-API-KEY": self.api_key}  # Adjust header name

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                r = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                r = requests.post(url, headers=headers, params=params, timeout=10)
            elif method == "DELETE":
                r = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            r.raise_for_status()
            return r.json()

        except requests.HTTPError as e:
            logger.error(f"Exchange API error: {e.response.text}")
            raise ExchangeError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise ExchangeError(f"Request failed: {e}")

    # ========== Broker Interface Implementation ==========

    def buy(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """Place buy order (long entry or short exit)."""
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": str(qty)  # Convert Decimal to string for API
        }

        result = self._request("POST", "/v1/order", signed=True, **params)
        order_id = str(result["orderId"])

        logger.info(f"BUY {qty} {symbol} | Order ID: {order_id}")
        return order_id

    def sell(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """Place sell order (short entry or long exit)."""
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(qty)
        }

        result = self._request("POST", "/v1/order", signed=True, **params)
        order_id = str(result["orderId"])

        logger.info(f"SELL {qty} {symbol} | Order ID: {order_id}")
        return order_id

    def close_all(self, symbol: str):
        """Flatten position (close all open positions for symbol)."""
        positions = self.positions()

        if symbol not in positions:
            logger.warning(f"No position to close for {symbol}")
            return

        pos = positions[symbol]

        if pos.side == "long":
            logger.info(f"Closing LONG position: {pos}")
            self.sell(symbol, pos.qty)
        else:
            logger.info(f"Closing SHORT position: {pos}")
            self.buy(symbol, pos.qty)

    def positions(self) -> Dict[str, Position]:
        """Get current positions."""
        result = self._request("GET", "/v1/positions", signed=True)

        positions = {}
        for pos_data in result:
            symbol = pos_data["symbol"]
            qty = abs(Decimal(pos_data["size"]))

            if qty == 0:
                continue

            entry_price = Decimal(pos_data["entryPrice"])
            mark_price = Decimal(pos_data["markPrice"])
            unrealized_pnl = Decimal(pos_data["unrealizedPnl"])

            side = "long" if Decimal(pos_data["size"]) > 0 else "short"

            # Calculate PnL %
            if entry_price > 0:
                if side == "long":
                    pnl_pct = ((mark_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - mark_price) / entry_price) * 100
            else:
                pnl_pct = Decimal("0.0")

            positions[symbol] = Position(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry_price,
                current_price=mark_price,
                pnl=unrealized_pnl,
                pnl_pct=pnl_pct
            )

        return positions

    def balance(self) -> Decimal:
        """Get available balance (USDT or USD)."""
        result = self._request("GET", "/v1/balance", signed=True)

        for asset in result:
            if asset["asset"] == "USDT":
                return Decimal(str(asset["available"]))

        return Decimal("0.0")
```

### Step 3: Add Error Handling

**Common Errors to Handle**:
1. Insufficient balance
2. Rate limit exceeded
3. Invalid symbol
4. Network timeout
5. Order rejected (size too small, etc.)

```python
class InsufficientBalanceError(ExchangeError):
    """Raised when balance is too low."""
    pass

class RateLimitError(ExchangeError):
    """Raised when rate limit exceeded."""
    pass

def _request(self, method, endpoint, signed=False, **params):
    try:
        r = requests.request(method, url, ...)
        r.raise_for_status()
        return r.json()

    except requests.HTTPError as e:
        error_code = e.response.json().get("code")

        # Handle specific error codes
        if error_code == -2010:
            raise InsufficientBalanceError("Insufficient balance")
        elif error_code == -1003:
            raise RateLimitError("Rate limit exceeded")
        else:
            raise ExchangeError(f"HTTP {e.response.status_code}: {e.response.text}")
```

### Step 4: Write Unit Tests

Create `tests/unit/test_broker_exchange_name.py`:

```python
"""Unit tests for ExchangeBroker."""
import os
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from trade_engine.adapters.brokers.exchange_name import ExchangeBroker, ExchangeError


class TestBrokerInitialization:
    def test_testnet_initialization_success(self):
        with patch.dict(os.environ, {
            "EXCHANGE_TESTNET_API_KEY": "a" * 64,
            "EXCHANGE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = ExchangeBroker(testnet=True)

        assert broker.testnet is True
        assert broker.base_url == ExchangeBroker.TESTNET_BASE

    def test_missing_api_key_raises_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ExchangeError, match="Missing API credentials"):
                ExchangeBroker(testnet=True)


class TestBrokerOrderOperations:
    def test_buy_success(self):
        with patch.dict(os.environ, {
            "EXCHANGE_TESTNET_API_KEY": "a" * 64,
            "EXCHANGE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = ExchangeBroker(testnet=True)
            broker._request = Mock(return_value={"orderId": 123456789})

            order_id = broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))

            assert order_id == "123456789"
            broker._request.assert_called_once()

    def test_positions_with_open_long(self):
        with patch.dict(os.environ, {
            "EXCHANGE_TESTNET_API_KEY": "a" * 64,
            "EXCHANGE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = ExchangeBroker(testnet=True)
            broker._request = Mock(return_value=[
                {
                    "symbol": "BTCUSDT",
                    "size": "0.001",  # Positive = long
                    "entryPrice": "50000.0",
                    "markPrice": "51000.0",
                    "unrealizedPnl": "1.0"
                }
            ])

            positions = broker.positions()

            assert "BTCUSDT" in positions
            pos = positions["BTCUSDT"]
            assert pos.side == "long"
            assert pos.qty == Decimal("0.001")
            assert isinstance(pos.entry_price, Decimal)
```

### Step 5: Integration Testing

Test with real testnet/demo API:

```python
# tests/integration/test_exchange_broker_integration.py
import pytest
from decimal import Decimal
from trade_engine.adapters.brokers.exchange_name import ExchangeBroker


@pytest.mark.integration
def test_broker_can_query_balance():
    """Test real API call to testnet."""
    broker = ExchangeBroker(testnet=True)
    balance = broker.balance()

    assert isinstance(balance, Decimal)
    assert balance >= 0


@pytest.mark.integration
def test_broker_can_place_and_close_order():
    """Test full order lifecycle on testnet."""
    broker = ExchangeBroker(testnet=True)

    # Place buy order
    order_id = broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))
    assert order_id is not None

    # Verify position exists
    positions = broker.positions()
    assert "BTCUSDT" in positions

    # Close position
    broker.close_all("BTCUSDT")

    # Verify position closed
    positions = broker.positions()
    assert "BTCUSDT" not in positions
```

---

## Part 2: Adding a Feed Adapter

### Step 1: Create the File

```bash
touch src/trade_engine/adapters/feeds/exchange_name_l2.py
```

### Step 2: Implement WebSocket Feed

```python
"""
Exchange Name L2 Order Book Data Feed

Real-time Level 2 order book depth streaming via WebSocket.
"""

import asyncio
import json
import time
from decimal import Decimal
from typing import AsyncIterator, Dict
from sortedcontainers import SortedDict
import websockets
from loguru import logger

from trade_engine.core.types import DataFeed, Bar


class ExchangeL2Error(Exception):
    """Feed errors."""
    pass


class OrderBook:
    """Efficient order book with sorted bids/asks."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: SortedDict[Decimal, Decimal] = SortedDict()
        self.asks: SortedDict[Decimal, Decimal] = SortedDict()
        self.last_update_id = 0
        self.last_update_time = 0.0

    def apply_snapshot(self, data: dict):
        """Initialize from full snapshot."""
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

    def apply_delta(self, data: dict):
        """Apply incremental update."""
        for price_str, qty_str in data.get('b', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)

            if qty == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty

        for price_str, qty_str in data.get('a', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)

            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        self.last_update_id = data['u']
        self.last_update_time = time.time()

    def calculate_imbalance(self, depth: int = 5) -> Decimal:
        """Calculate bid/ask volume ratio."""
        top_bids = list(self.bids.items())[-depth:]
        bid_volume = sum(qty for price, qty in top_bids)

        top_asks = list(self.asks.items())[:depth]
        ask_volume = sum(qty for price, qty in top_asks)

        if ask_volume == 0:
            return Decimal("999.0")

        return bid_volume / ask_volume

    def is_valid(self) -> bool:
        """Check if order book is valid."""
        if len(self.bids) == 0 or len(self.asks) == 0:
            return False

        if time.time() - self.last_update_time > 5.0:
            return False

        return True


class ExchangeL2Feed(DataFeed):
    """
    Real-time L2 order book feed via WebSocket.
    """

    SNAPSHOT_URL = "https://api.exchange.com/v1/depth"
    WS_URL = "wss://stream.exchange.com/ws"

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.order_book = OrderBook(symbol)
        self._ws = None
        self._connected = False

    async def connect(self):
        """Establish WebSocket connection."""
        # Step 1: Get snapshot via REST
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.SNAPSHOT_URL,
                params={"symbol": self.symbol, "limit": 1000}
            ) as response:
                snapshot = await response.json()
                self.order_book.apply_snapshot(snapshot)

        # Step 2: Connect to WebSocket
        ws_url = f"{self.WS_URL}/{self.symbol.lower()}@depth@100ms"
        self._ws = await websockets.connect(ws_url)
        self._connected = True

        logger.info(f"Connected to {ws_url}")

    async def stream(self) -> AsyncIterator[Dict]:
        """Stream order book updates."""
        async for message in self._ws:
            data = json.loads(message)

            # Apply delta
            self.order_book.apply_delta(data)

            yield {
                "type": "orderbook_update",
                "symbol": self.symbol,
                "timestamp": data['E'],
                "data": data
            }

    async def disconnect(self):
        """Close connection."""
        if self._ws:
            await self._ws.close()
        self._connected = False

    def candles(self):
        """Not implemented for L2 feed (WebSocket only)."""
        raise NotImplementedError("Use async stream() instead")
```

### Step 3: Write Tests

```python
# tests/unit/test_exchange_l2_feed.py
import pytest
from decimal import Decimal
from trade_engine.adapters.feeds.exchange_name_l2 import OrderBook


def test_order_book_snapshot():
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


def test_imbalance_calculation():
    ob = OrderBook("BTCUSDT")
    ob.bids[Decimal("50000")] = Decimal("1.0")
    ob.bids[Decimal("49999")] = Decimal("2.0")
    ob.asks[Decimal("50001")] = Decimal("0.5")
    ob.asks[Decimal("50002")] = Decimal("0.5")

    imbalance = ob.calculate_imbalance(depth=2)

    assert imbalance == Decimal("3.0")  # (1.0 + 2.0) / (0.5 + 0.5) = 3.0
```

---

## Part 3: Adding a Data Source Adapter

### Step 1: Create the File

```bash
touch src/trade_engine/adapters/data_sources/exchange_name.py
```

### Step 2: Implement REST API Client

```python
"""Exchange Name data source adapter for historical data."""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd
import aiohttp
from loguru import logger

from trade_engine.adapters.data_sources.base import DataSourceAdapter


class ExchangeDataSource(DataSourceAdapter):
    """Fetch OHLCV and ticker data from Exchange Name."""

    BASE_URL = "https://api.exchange.com"

    def __init__(self):
        self._rate_limit = 1200  # requests per minute
        self._request_times = []

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch OHLCV data."""
        # Normalize symbol
        symbol_normalized = self.normalize_symbol(symbol)

        # Convert timeframe to exchange format
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
        interval = interval_map.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Build request
        params = {
            "symbol": symbol_normalized,
            "interval": interval,
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(end.timestamp() * 1000)
        }

        if limit:
            params["limit"] = limit

        # Make request
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/v1/klines",
                params=params
            ) as response:
                data = await response.json()

        # Parse to DataFrame
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        # Convert to Decimal
        df["open"] = df["open"].apply(lambda x: Decimal(str(x)))
        df["high"] = df["high"].apply(lambda x: Decimal(str(x)))
        df["low"] = df["low"].apply(lambda x: Decimal(str(x)))
        df["close"] = df["close"].apply(lambda x: Decimal(str(x)))
        df["volume"] = df["volume"].apply(lambda x: Decimal(str(x)))

        # Keep only required columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

        return df

    async def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch current ticker."""
        symbol_normalized = self.normalize_symbol(symbol)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/v1/ticker",
                params={"symbol": symbol_normalized}
            ) as response:
                data = await response.json()

        return {
            "symbol": symbol,
            "bid": Decimal(str(data["bidPrice"])),
            "ask": Decimal(str(data["askPrice"])),
            "last": Decimal(str(data["lastPrice"])),
            "volume_24h": Decimal(str(data["volume"])),
            "timestamp": data["timestamp"]
        }

    def supports_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is supported."""
        return timeframe in ["1m", "5m", "15m", "1h", "4h", "1d"]

    def get_supported_symbols(self) -> List[str]:
        """Get list of supported symbols."""
        # TODO: Implement by fetching from exchange API
        return ["BTC/USDT", "ETH/USDT", "BNB/USDT"]

    def normalize_symbol(self, symbol: str) -> str:
        """Convert 'BTC/USDT' to 'BTCUSDT'."""
        return symbol.replace("/", "")

    def get_rate_limit(self) -> int:
        """Get API rate limit."""
        return self._rate_limit
```

---

## Checklist: Before Merging

### Documentation
- [ ] Docstrings for all public methods
- [ ] Usage examples in docstring
- [ ] Error handling documented

### Testing
- [ ] Unit tests (100% coverage for critical methods)
- [ ] Integration tests (real API calls to testnet)
- [ ] Decimal precision verified (no float usage)
- [ ] Error handling tested (rate limits, invalid symbols)

### Code Quality
- [ ] Black formatting applied
- [ ] Ruff linting passes
- [ ] mypy type checking passes (if enabled)
- [ ] No hardcoded credentials

### Performance
- [ ] Latency measured (<100ms for critical operations)
- [ ] Rate limit enforcement tested
- [ ] Memory usage acceptable (<100MB per adapter)

### Security
- [ ] API keys loaded from environment variables
- [ ] No credentials in logs
- [ ] HTTPS used for all API calls
- [ ] Input validation (symbol, timeframe, quantity)

---

## Common Pitfalls

### 1. Float Instead of Decimal ❌
```python
# ❌ WRONG
price = float(api_response["price"])

# ✅ CORRECT
price = Decimal(str(api_response["price"]))
```

### 2. No Rate Limit Handling ❌
```python
# ❌ WRONG
for symbol in symbols:
    df = await source.fetch_ohlcv(symbol, ...)

# ✅ CORRECT
for symbol in symbols:
    await self._enforce_rate_limit()
    df = await source.fetch_ohlcv(symbol, ...)
```

### 3. Hardcoded Credentials ❌
```python
# ❌ WRONG
api_key = "my_secret_key_123"

# ✅ CORRECT
api_key = os.getenv("EXCHANGE_API_KEY")
if not api_key:
    raise ValueError("Missing API credentials")
```

### 4. No Error Handling ❌
```python
# ❌ WRONG
response = requests.get(url)
return response.json()

# ✅ CORRECT
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
except requests.HTTPError as e:
    logger.error(f"API error: {e}")
    raise ExchangeError(...)
```

---

## Next Steps

After implementing an adapter:

1. **Add to README** (`docs/adapters/README.md`)
2. **Update action plan** (mark adapter as implemented)
3. **Create integration test** (run against testnet)
4. **Document in BROKER_SUMMARY** (if broker adapter)
5. **Add to CI** (ensure tests run on every PR)

---

## Getting Help

- **Interface Questions**: See specification docs in `docs/adapters/`
- **Exchange API Questions**: Read exchange API documentation
- **Testing Questions**: See existing test files in `tests/unit/` and `tests/integration/`
- **Code Review**: Create PR and request review from maintainers

---

**Document Version**: 1.0
**Last Review**: 2025-10-30
**Next Review**: When adding new adapter types
