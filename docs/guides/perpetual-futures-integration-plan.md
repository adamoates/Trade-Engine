# Perpetual Futures Integration Plan

**Status**: Implementation Plan
**Priority**: High
**Complexity**: Medium (extends existing architecture)

## Executive Summary

This document provides a step-by-step plan to enhance the Trade-Engine with perpetual futures capabilities, funding rate tracking, and enhanced analytics while preserving the existing working codebase.

**Key Finding**: 80% of required infrastructure already exists. We need to add:
- Funding rate service
- Futures-specific risk logic
- Enhanced database schema
- Position manager service

## Current Architecture Assessment

### ✅ Already Implemented

#### 1. Binance Futures Broker (`adapters/brokers/binance.py`)
**Status**: PRODUCTION-READY

```python
class BinanceFuturesBroker(Broker):
    """Existing implementation with full futures support"""

    # Already implemented:
    - buy() / sell() with SL/TP
    - close_all()
    - positions() - Returns Dict[str, Position]
    - balance() - Returns Decimal
    - set_leverage(symbol, leverage)
    - set_margin_type(symbol, "ISOLATED" | "CROSSED")
    - get_ticker_price(symbol)
    - cancel_all_orders(symbol)
```

**Location**: `src/trade_engine/adapters/brokers/binance.py` (345 lines)

**Features**:
- ✅ Testnet and live mode
- ✅ HMAC-SHA256 authentication
- ✅ Position tracking
- ✅ Leverage control (1-125x)
- ✅ Margin mode selection
- ✅ Decimal precision throughout

**No changes needed** - This is exactly what your master prompt requires.

#### 2. PostgreSQL Database (`db/postgres_adapter.py`)
**Status**: PRODUCTION-READY

```python
class PostgresDatabase:
    """Existing implementation with comprehensive logging"""

    # Already implemented:
    - init_schema() - Auto-creates tables
    - log_trade(trade_id, symbol, side, price, qty, commission)
    - open_position(symbol, side, entry_price, qty, broker, strategy)
    - close_position(symbol, broker, exit_price, exit_reason)
    - log_risk_event(event_type, reason, metric_value, limit_value)
    - get_positions(broker, status) - Returns List[Dict]
    - get_position(symbol, broker) - Returns Dict | None
    - get_daily_pnl(days) - Returns Decimal
```

**Location**: `src/trade_engine/db/postgres_adapter.py` (824 lines)

**Tables**:
- `positions` - Position lifecycle with P&L
- `trades` - Complete execution audit trail
- `risk_events` - Risk management events

**Schema includes**:
- NUMERIC(20, 8) for crypto precision
- Partial unique indexes
- ACID compliance
- Thread-safe operations

**Missing**: Funding events, PnL snapshots (need to add)

#### 3. Risk Manager (`domain/risk/risk_manager.py`)
**Status**: PRODUCTION-READY (needs futures extension)

```python
class RiskManager:
    """Existing spot trading risk logic"""

    # Already implemented:
    - validate_position_size(size, price, max_position)
    - check_daily_loss(current_pnl, limit)
    - check_drawdown(current_equity, peak_equity, max_dd)
    - trigger_kill_switch(reason)
```

**Hard Limits** (NON-NEGOTIABLE per CLAUDE.md):
- Max Position Size: $10,000
- Daily Loss Limit: -$500 (triggers kill switch)
- Max Drawdown: -$1,000 (triggers kill switch)

**Needs**: Leverage validation, margin monitoring, liquidation buffer

## 🔨 Implementation Plan

### Phase 1: Funding Rate Service (2-3 hours)
**Priority**: High
**Complexity**: Low

Create new service to track funding rates and costs.

**File**: `src/trade_engine/services/data/funding_rate_service.py`

```python
"""
Funding Rate Service for Perpetual Futures.

Tracks 8-hourly funding payments and cumulative costs.
"""

import requests
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict
from loguru import logger


class FundingRateService:
    """
    Fetch and track perpetual futures funding rates.

    Funding rates are paid every 8 hours on most exchanges:
    - 00:00 UTC
    - 08:00 UTC
    - 16:00 UTC

    Positive rate = longs pay shorts
    Negative rate = shorts pay longs
    """

    BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

    def __init__(self, database=None):
        """
        Initialize funding rate service.

        Args:
            database: Optional PostgresDatabase instance for logging
        """
        self.db = database

    def get_current_funding_rate(self, symbol: str) -> Decimal:
        """
        Get the current funding rate for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current funding rate as Decimal (e.g., 0.0001 = 0.01%)

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            params = {"symbol": symbol, "limit": 1}
            response = requests.get(
                self.BINANCE_FUNDING_URL,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.warning(f"No funding data for {symbol}")
                return Decimal("0")

            rate = Decimal(str(data[0]["fundingRate"]))
            logger.debug(f"Funding rate for {symbol}: {rate} ({rate * 100}%)")

            # Log to database if available
            if self.db:
                self._log_funding_event(symbol, rate, data[0]["fundingTime"])

            return rate

        except requests.RequestException as e:
            logger.error(f"Failed to fetch funding rate for {symbol}: {e}")
            raise

    def get_historical_funding(
        self,
        symbol: str,
        start_time: int = None,
        limit: int = 100
    ) -> List[Dict[str, any]]:
        """
        Get historical funding rates.

        Args:
            symbol: Trading pair
            start_time: Start timestamp (milliseconds)
            limit: Number of records (max 1000)

        Returns:
            List of funding rate records with timestamps
        """
        params = {"symbol": symbol, "limit": min(limit, 1000)}
        if start_time:
            params["startTime"] = start_time

        response = requests.get(
            self.BINANCE_FUNDING_URL,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def calculate_funding_cost(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        funding_rate: Decimal,
        periods: int = 1
    ) -> Decimal:
        """
        Calculate funding payment for a position.

        Formula: cost = position_notional * funding_rate * periods

        Args:
            position_size: Position size in base currency (e.g., 0.5 BTC)
            entry_price: Entry price in quote currency (e.g., 50000 USDT)
            funding_rate: Funding rate (e.g., 0.0001)
            periods: Number of funding periods (default 1 = 8 hours)

        Returns:
            Funding cost in quote currency (positive = cost, negative = income)

        Example:
            >>> calculate_funding_cost(
            ...     Decimal("0.5"),      # 0.5 BTC
            ...     Decimal("50000"),    # at $50k
            ...     Decimal("0.0001"),   # 0.01% rate
            ...     periods=3            # 24 hours (3x 8hr periods)
            ... )
            Decimal("7.50")  # $7.50 cost
        """
        notional = position_size * entry_price
        cost = notional * funding_rate * Decimal(str(periods))

        logger.debug(
            f"Funding cost: {cost} USDT "
            f"(size={position_size}, price={entry_price}, "
            f"rate={funding_rate}, periods={periods})"
        )

        return cost.quantize(Decimal("0.01"))

    def estimate_daily_funding(
        self,
        symbol: str,
        position_size: Decimal,
        entry_price: Decimal
    ) -> Decimal:
        """
        Estimate 24-hour funding cost based on current rate.

        Args:
            symbol: Trading pair
            position_size: Position size
            entry_price: Entry price

        Returns:
            Estimated daily funding cost
        """
        current_rate = self.get_current_funding_rate(symbol)
        return self.calculate_funding_cost(
            position_size,
            entry_price,
            current_rate,
            periods=3  # 3x 8-hour periods = 24 hours
        )

    def _log_funding_event(self, symbol: str, rate: Decimal, timestamp: int):
        """
        Log funding event to database.

        Args:
            symbol: Trading pair
            rate: Funding rate
            timestamp: Unix timestamp (milliseconds)
        """
        if not self.db:
            return

        try:
            # Convert milliseconds to datetime
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)

            # TODO: Add funding_events table to database schema
            # For now, log as audit event
            logger.info(
                "funding_event",
                symbol=symbol,
                rate=str(rate),
                timestamp=dt.isoformat()
            )
        except Exception as e:
            logger.error(f"Failed to log funding event: {e}")
```

**Testing**: `tests/unit/test_funding_rate_service.py`

```python
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from trade_engine.services.data.funding_rate_service import FundingRateService


class TestFundingRateService:
    """Test funding rate service functionality."""

    def test_calculate_funding_cost(self):
        """Test funding cost calculation."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("0.5"),
            entry_price=Decimal("50000"),
            funding_rate=Decimal("0.0001"),
            periods=1
        )

        assert cost == Decimal("2.50")  # 0.5 * 50000 * 0.0001 = 2.50

    def test_calculate_funding_cost_negative_rate(self):
        """Test funding income with negative rate."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("1.0"),
            entry_price=Decimal("30000"),
            funding_rate=Decimal("-0.0001"),
            periods=1
        )

        assert cost == Decimal("-3.00")  # Negative = income

    def test_calculate_funding_cost_multiple_periods(self):
        """Test 24-hour funding cost (3 periods)."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("0.1"),
            entry_price=Decimal("60000"),
            funding_rate=Decimal("0.0001"),
            periods=3  # 24 hours
        )

        assert cost == Decimal("1.80")  # 0.1 * 60000 * 0.0001 * 3 = 1.80

    @patch('requests.get')
    def test_get_current_funding_rate(self, mock_get):
        """Test fetching current funding rate."""
        mock_response = Mock()
        mock_response.json.return_value = [{
            "symbol": "BTCUSDT",
            "fundingRate": "0.00010000",
            "fundingTime": 1635724800000
        }]
        mock_get.return_value = mock_response

        service = FundingRateService()
        rate = service.get_current_funding_rate("BTCUSDT")

        assert rate == Decimal("0.0001")

    def test_estimate_daily_funding(self):
        """Test daily funding estimation."""
        service = FundingRateService()

        # Mock the API call
        service.get_current_funding_rate = Mock(return_value=Decimal("0.0001"))

        daily_cost = service.estimate_daily_funding(
            symbol="BTCUSDT",
            position_size=Decimal("1.0"),
            entry_price=Decimal("50000")
        )

        # 1 BTC * 50k * 0.0001 * 3 periods = 15 USDT
        assert daily_cost == Decimal("15.00")
```

**Integration**:
```python
# In trading engine initialization:
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.db.postgres_adapter import PostgresDatabase

db = PostgresDatabase()
funding_service = FundingRateService(database=db)

# Check funding before opening position:
current_rate = funding_service.get_current_funding_rate("BTCUSDT")
daily_cost = funding_service.estimate_daily_funding(
    "BTCUSDT",
    position_size=Decimal("0.5"),
    entry_price=Decimal("50000")
)

if daily_cost > Decimal("10.00"):  # Max $10/day funding
    logger.warning(f"High funding cost: {daily_cost} USDT/day")
```

---

### Phase 2: Futures Risk Manager (3-4 hours)
**Priority**: High
**Complexity**: Medium

Extend existing risk manager with futures-specific logic.

**File**: `src/trade_engine/domain/risk/futures_risk_manager.py`

```python
"""
Futures Risk Manager.

Adds leverage, margin, and liquidation monitoring to base risk management.
"""

from decimal import Decimal
from typing import Dict, Optional
from loguru import logger

from trade_engine.domain.risk.risk_manager import RiskManager


class FuturesRiskManager(RiskManager):
    """
    Risk management for leveraged futures trading.

    Extends base RiskManager with:
    - Leverage limits
    - Margin ratio monitoring
    - Liquidation buffer
    - Position-specific risk
    """

    def __init__(
        self,
        max_leverage: int = 5,
        liquidation_buffer: Decimal = Decimal("0.15"),  # 15% safety margin
        max_position_size: Decimal = Decimal("10000"),
        daily_loss_limit: Decimal = Decimal("500"),
        max_drawdown: Decimal = Decimal("1000"),
    ):
        """
        Initialize futures risk manager.

        Args:
            max_leverage: Maximum allowed leverage (1-125)
            liquidation_buffer: Minimum margin ratio before forced close
            max_position_size: Maximum notional position size (inherited)
            daily_loss_limit: Daily loss trigger (inherited)
            max_drawdown: Max drawdown trigger (inherited)
        """
        super().__init__(
            max_position_size=max_position_size,
            daily_loss_limit=daily_loss_limit,
            max_drawdown=max_drawdown
        )

        self.max_leverage = max_leverage
        self.liquidation_buffer = liquidation_buffer

        logger.info(
            "Futures risk manager initialized",
            max_leverage=max_leverage,
            liquidation_buffer=str(liquidation_buffer),
            max_position=str(max_position_size),
            daily_loss=str(daily_loss_limit),
            max_dd=str(max_drawdown)
        )

    def validate_leverage(self, leverage: int) -> bool:
        """
        Validate leverage is within limits.

        Args:
            leverage: Requested leverage

        Returns:
            True if valid, raises ValueError if not

        Raises:
            ValueError: If leverage exceeds maximum
        """
        if not isinstance(leverage, int) or leverage < 1:
            raise ValueError(f"Leverage must be integer >= 1, got: {leverage}")

        if leverage > self.max_leverage:
            raise ValueError(
                f"Leverage {leverage}x exceeds maximum {self.max_leverage}x"
            )

        return True

    def calculate_liquidation_price(
        self,
        entry_price: Decimal,
        leverage: int,
        side: str,
        maintenance_margin_rate: Decimal = Decimal("0.004")  # 0.4% for BTC
    ) -> Decimal:
        """
        Calculate liquidation price for a leveraged position.

        Formula (long):
            liq_price = entry * (1 - (1/leverage) + mmr)

        Formula (short):
            liq_price = entry * (1 + (1/leverage) - mmr)

        Args:
            entry_price: Entry price
            leverage: Position leverage
            side: "long" or "short"
            maintenance_margin_rate: Exchange MMR (varies by pair)

        Returns:
            Liquidation price

        Example:
            >>> calculate_liquidation_price(
            ...     entry_price=Decimal("50000"),
            ...     leverage=5,
            ...     side="long"
            ... )
            Decimal("40200.00")  # -19.6% from entry
        """
        leverage_factor = Decimal("1") / Decimal(str(leverage))

        if side.lower() == "long":
            # Long liquidation: entry * (1 - 1/leverage + mmr)
            liq_price = entry_price * (
                Decimal("1") - leverage_factor + maintenance_margin_rate
            )
        else:
            # Short liquidation: entry * (1 + 1/leverage - mmr)
            liq_price = entry_price * (
                Decimal("1") + leverage_factor - maintenance_margin_rate
            )

        return liq_price.quantize(Decimal("0.01"))

    def check_margin_health(
        self,
        account_balance: Decimal,
        maintenance_margin: Decimal,
        unrealized_pnl: Decimal
    ) -> Dict[str, any]:
        """
        Check margin health and determine action.

        Margin ratio = (balance + unrealized_pnl) / maintenance_margin

        Actions:
        - margin_ratio > buffer: OK
        - margin_ratio < buffer: WARNING
        - margin_ratio < 1.0: LIQUIDATION IMMINENT

        Args:
            account_balance: Account balance
            maintenance_margin: Required maintenance margin
            unrealized_pnl: Current unrealized P&L

        Returns:
            Dict with action, margin_ratio, and reason
        """
        if maintenance_margin == 0:
            return {
                "action": "ok",
                "margin_ratio": None,
                "reason": "No open positions"
            }

        equity = account_balance + unrealized_pnl
        margin_ratio = equity / maintenance_margin

        logger.debug(
            "Margin check",
            balance=str(account_balance),
            unrealized_pnl=str(unrealized_pnl),
            equity=str(equity),
            maintenance=str(maintenance_margin),
            ratio=str(margin_ratio)
        )

        if margin_ratio < Decimal("1.0"):
            # Critical: Liquidation imminent
            logger.critical(
                "LIQUIDATION IMMINENT",
                margin_ratio=str(margin_ratio),
                equity=str(equity),
                maintenance=str(maintenance_margin)
            )
            return {
                "action": "liquidate_all",
                "margin_ratio": margin_ratio,
                "reason": "Margin ratio below 1.0 - liquidation imminent"
            }

        elif margin_ratio < (Decimal("1.0") + self.liquidation_buffer):
            # Warning: Too close to liquidation
            logger.warning(
                "Low margin ratio",
                margin_ratio=str(margin_ratio),
                buffer=str(self.liquidation_buffer)
            )
            return {
                "action": "reduce_position",
                "margin_ratio": margin_ratio,
                "reason": f"Margin ratio below safe buffer ({self.liquidation_buffer})"
            }

        else:
            # Healthy margin
            return {
                "action": "ok",
                "margin_ratio": margin_ratio,
                "reason": "Margin healthy"
            }

    def validate_position_with_leverage(
        self,
        balance: Decimal,
        price: Decimal,
        size: Decimal,
        leverage: int
    ) -> bool:
        """
        Validate position size considering leverage.

        With leverage, notional value can exceed balance:
        - notional = price * size
        - required_margin = notional / leverage
        - max_allowed = balance * leverage

        Args:
            balance: Account balance
            price: Entry price
            size: Position size
            leverage: Leverage multiplier

        Returns:
            True if valid

        Raises:
            ValueError: If position too large
        """
        notional = price * size
        required_margin = notional / Decimal(str(leverage))
        max_allowed_notional = balance * Decimal(str(leverage))

        logger.debug(
            "Position validation",
            notional=str(notional),
            required_margin=str(required_margin),
            balance=str(balance),
            leverage=leverage,
            max_allowed=str(max_allowed_notional)
        )

        # Check against absolute position limit (NON-NEGOTIABLE)
        if notional > self.max_position_size:
            raise ValueError(
                f"Position size ${notional} exceeds hard limit "
                f"${self.max_position_size} (NON-NEGOTIABLE)"
            )

        # Check if we have enough margin
        if required_margin > balance:
            raise ValueError(
                f"Insufficient margin: need ${required_margin}, "
                f"have ${balance}"
            )

        # Check leverage doesn't push us too far
        if notional > max_allowed_notional:
            raise ValueError(
                f"Position ${notional} exceeds {leverage}x leverage limit "
                f"of ${max_allowed_notional}"
            )

        return True

    def can_open_position(
        self,
        balance: Decimal,
        price: Decimal,
        size: Decimal,
        leverage: int,
        current_pnl: Optional[Decimal] = None,
        peak_equity: Optional[Decimal] = None
    ) -> Dict[str, any]:
        """
        Comprehensive pre-trade risk check.

        Checks:
        1. Leverage within limits
        2. Position size valid
        3. Daily loss limit not breached
        4. Drawdown limit not breached
        5. Kill switch not active

        Args:
            balance: Account balance
            price: Entry price
            size: Position size
            leverage: Leverage
            current_pnl: Daily P&L (optional)
            peak_equity: Peak equity for DD calc (optional)

        Returns:
            Dict with 'allowed' bool and 'reason' string
        """
        # Check kill switch
        if self.kill_switch_active:
            return {
                "allowed": False,
                "reason": "Kill switch active - all trading disabled"
            }

        # Validate leverage
        try:
            self.validate_leverage(leverage)
        except ValueError as e:
            return {"allowed": False, "reason": str(e)}

        # Validate position size
        try:
            self.validate_position_with_leverage(balance, price, size, leverage)
        except ValueError as e:
            return {"allowed": False, "reason": str(e)}

        # Check daily loss limit
        if current_pnl is not None:
            if current_pnl < -self.daily_loss_limit:
                self.trigger_kill_switch("Daily loss limit breached")
                return {
                    "allowed": False,
                    "reason": f"Daily loss ${abs(current_pnl)} exceeds limit ${self.daily_loss_limit}"
                }

        # Check drawdown limit
        if peak_equity is not None and balance is not None:
            current_equity = balance + (current_pnl or Decimal("0"))
            drawdown = peak_equity - current_equity

            if drawdown > self.max_drawdown:
                self.trigger_kill_switch("Max drawdown breached")
                return {
                    "allowed": False,
                    "reason": f"Drawdown ${drawdown} exceeds limit ${self.max_drawdown}"
                }

        # All checks passed
        return {"allowed": True, "reason": "All risk checks passed"}
```

**Testing**: `tests/unit/test_futures_risk_manager.py` (100+ lines of comprehensive tests)

---

### Phase 3: Database Schema Enhancement (1-2 hours)
**Priority**: Medium
**Complexity**: Low

Add two new tables to existing `postgres_adapter.py`:

```python
# Add to init_schema() method in PostgresDatabase class:

def init_schema(self) -> None:
    """Enhanced with funding_events and pnl_snapshots tables."""

    with self._get_connection() as conn:
        with conn.cursor() as cur:
            # ... existing table creation code ...

            # NEW: Funding events table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS funding_events (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    broker VARCHAR(50) NOT NULL,
                    funding_rate NUMERIC(10, 8) NOT NULL,
                    position_size NUMERIC(20, 8) NOT NULL,
                    notional_value NUMERIC(20, 2) NOT NULL,
                    funding_payment NUMERIC(20, 2) NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    notes TEXT
                );
            """)

            # Index for time-series queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_timestamp
                ON funding_events(timestamp DESC);
            """)

            # NEW: PnL snapshots table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pnl_snapshots (
                    id SERIAL PRIMARY KEY,
                    broker VARCHAR(50) NOT NULL,
                    strategy VARCHAR(100),
                    balance NUMERIC(20, 2) NOT NULL,
                    unrealized_pnl NUMERIC(20, 2) DEFAULT 0,
                    realized_pnl NUMERIC(20, 2) DEFAULT 0,
                    total_pnl NUMERIC(20, 2) NOT NULL,
                    equity NUMERIC(20, 2) NOT NULL,
                    margin_ratio NUMERIC(10, 4),
                    open_positions INTEGER DEFAULT 0,
                    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    notes TEXT
                );
            """)

            # Index for equity curve queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_pnl_time
                ON pnl_snapshots(snapshot_time DESC);
            """)

            logger.info("Database schema enhanced with funding and PnL tracking")

# NEW: Helper methods to add to PostgresDatabase class:

def log_funding_event(
    self,
    symbol: str,
    broker: str,
    funding_rate: Decimal,
    position_size: Decimal,
    notional_value: Decimal,
    funding_payment: Decimal,
    notes: str = None
):
    """Log a funding payment event."""
    with self._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO funding_events
                (symbol, broker, funding_rate, position_size,
                 notional_value, funding_payment, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (symbol, broker, str(funding_rate), str(position_size),
                 str(notional_value), str(funding_payment), notes)
            )

    logger.info(
        "Funding event logged",
        symbol=symbol,
        rate=str(funding_rate),
        payment=str(funding_payment)
    )

def log_pnl_snapshot(
    self,
    broker: str,
    balance: Decimal,
    unrealized_pnl: Decimal,
    realized_pnl: Decimal,
    margin_ratio: Decimal = None,
    open_positions: int = 0,
    strategy: str = None,
    notes: str = None
):
    """Log a P&L snapshot for analytics."""
    total_pnl = realized_pnl + unrealized_pnl
    equity = balance + unrealized_pnl

    with self._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pnl_snapshots
                (broker, strategy, balance, unrealized_pnl, realized_pnl,
                 total_pnl, equity, margin_ratio, open_positions, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (broker, strategy, str(balance), str(unrealized_pnl),
                 str(realized_pnl), str(total_pnl), str(equity),
                 str(margin_ratio) if margin_ratio else None,
                 open_positions, notes)
            )

    logger.debug(
        "PnL snapshot logged",
        equity=str(equity),
        pnl=str(total_pnl),
        positions=open_positions
    )

def get_funding_history(
    self,
    symbol: str = None,
    broker: str = None,
    days: int = 7
) -> List[Dict]:
    """Get funding payment history."""
    with self._get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT * FROM funding_events
                WHERE timestamp >= NOW() - INTERVAL '1 day' * %s
            """
            params = [days]

            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)

            if broker:
                query += " AND broker = %s"
                params.append(broker)

            query += " ORDER BY timestamp DESC"

            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

def get_equity_curve(
    self,
    broker: str = None,
    days: int = 30
) -> List[Dict]:
    """Get equity curve data for charting."""
    with self._get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT * FROM pnl_snapshots
                WHERE snapshot_time >= NOW() - INTERVAL '1 day' * %s
            """
            params = [days]

            if broker:
                query += " AND broker = %s"
                params.append(broker)

            query += " ORDER BY snapshot_time ASC"

            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
```

---

### Phase 4: Position Manager Service (2-3 hours)
**Priority**: Medium
**Complexity**: Medium

Create centralized position management service.

**File**: `src/trade_engine/services/trading/position_manager.py`

```python
"""
Position Manager Service.

Centralizes position lifecycle management for futures trading.
"""

from decimal import Decimal
from typing import Dict, Optional
from loguru import logger

from trade_engine.adapters.brokers.base import Broker
from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.db.postgres_adapter import PostgresDatabase


class PositionManager:
    """
    Manage position lifecycle for futures trading.

    Responsibilities:
    - Pre-trade risk validation
    - Position opening with leverage
    - Position monitoring (margin, funding)
    - Position closing
    - Database logging
    """

    def __init__(
        self,
        broker: Broker,
        risk_manager: FuturesRiskManager,
        funding_service: FundingRateService,
        database: PostgresDatabase
    ):
        """
        Initialize position manager.

        Args:
            broker: Broker adapter (e.g., BinanceFuturesBroker)
            risk_manager: Futures risk manager
            funding_service: Funding rate service
            database: Database adapter
        """
        self.broker = broker
        self.risk = risk_manager
        self.funding = funding_service
        self.db = database

        logger.info("Position manager initialized")

    def open_position(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        leverage: int = 3,
        sl: Decimal = None,
        tp: Decimal = None,
        strategy: str = None
    ) -> Dict[str, any]:
        """
        Open a new leveraged position with full risk checks.

        Steps:
        1. Get account balance
        2. Get current price
        3. Check funding rate
        4. Validate with risk manager
        5. Set leverage on exchange
        6. Execute order
        7. Log to database

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "long" or "short" (or "buy"/"sell")
            size: Position size in base currency
            leverage: Leverage multiplier (1-125)
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            strategy: Strategy name for tracking

        Returns:
            Dict with order details and success status

        Raises:
            ValueError: If risk checks fail
        """
        logger.info(
            "Opening position",
            symbol=symbol,
            side=side,
            size=str(size),
            leverage=leverage
        )

        try:
            # 1. Get account state
            balance = self.broker.balance()
            price = self.broker.get_ticker_price(symbol)

            logger.debug(
                "Account state",
                balance=str(balance),
                price=str(price)
            )

            # 2. Check funding rate
            funding_rate = self.funding.get_current_funding_rate(symbol)
            daily_funding = self.funding.estimate_daily_funding(symbol, size, price)

            if daily_funding > Decimal("10.00"):
                logger.warning(
                    "High funding cost",
                    daily_cost=str(daily_funding),
                    rate=str(funding_rate)
                )

            # 3. Risk validation
            risk_check = self.risk.can_open_position(
                balance=balance,
                price=price,
                size=size,
                leverage=leverage
            )

            if not risk_check["allowed"]:
                logger.error("Risk check failed", reason=risk_check["reason"])
                return {
                    "success": False,
                    "reason": risk_check["reason"]
                }

            # 4. Set leverage
            self.broker.set_leverage(symbol, leverage)
            logger.info(f"Leverage set to {leverage}x for {symbol}")

            # 5. Execute order
            if side.lower() in ("long", "buy"):
                order_id = self.broker.buy(symbol, size, sl=sl, tp=tp)
            else:
                order_id = self.broker.sell(symbol, size, sl=sl, tp=tp)

            logger.info("Order executed", order_id=order_id)

            # 6. Log to database
            self.db.open_position(
                symbol=symbol,
                side=side,
                entry_price=price,
                qty=size,
                broker=self.broker.__class__.__name__,
                strategy=strategy,
                notes=f"Leverage: {leverage}x, Funding: {funding_rate}"
            )

            # 7. Calculate liquidation price
            liq_price = self.risk.calculate_liquidation_price(
                entry_price=price,
                leverage=leverage,
                side=side
            )

            logger.info(
                "Position opened",
                symbol=symbol,
                entry=str(price),
                liquidation=str(liq_price),
                leverage=leverage
            )

            return {
                "success": True,
                "order_id": order_id,
                "entry_price": price,
                "liquidation_price": liq_price,
                "funding_rate": funding_rate,
                "estimated_daily_funding": daily_funding
            }

        except Exception as e:
            logger.error(f"Failed to open position: {e}", exc_info=True)
            return {
                "success": False,
                "reason": str(e)
            }

    def monitor_positions(self):
        """
        Monitor all open positions for margin health.

        Checks:
        - Margin ratio
        - Unrealized P&L
        - Liquidation distance

        Takes action if needed:
        - Close position if margin too low
        - Log warnings
        - Update database
        """
        try:
            # Get all positions from broker
            positions = self.broker.positions()

            if not positions:
                logger.debug("No open positions to monitor")
                return

            balance = self.broker.balance()

            # Calculate total maintenance margin and unrealized P&L
            total_maintenance = Decimal("0")
            total_unrealized = Decimal("0")

            for symbol, pos in positions.items():
                total_maintenance += pos.maintenance_margin or Decimal("0")
                total_unrealized += pos.unrealized_pnl or Decimal("0")

                logger.debug(
                    "Position status",
                    symbol=symbol,
                    size=str(pos.size),
                    entry=str(pos.entry_price),
                    current=str(pos.current_price),
                    pnl=str(pos.unrealized_pnl)
                )

            # Check overall margin health
            margin_check = self.risk.check_margin_health(
                account_balance=balance,
                maintenance_margin=total_maintenance,
                unrealized_pnl=total_unrealized
            )

            logger.info(
                "Margin health check",
                action=margin_check["action"],
                ratio=str(margin_check.get("margin_ratio")),
                reason=margin_check["reason"]
            )

            # Take action if needed
            if margin_check["action"] == "liquidate_all":
                logger.critical("EMERGENCY: Closing all positions to avoid liquidation")
                self._emergency_close_all()

            elif margin_check["action"] == "reduce_position":
                logger.warning("Reducing positions due to low margin")
                self._reduce_largest_position()

            # Log PnL snapshot
            self.db.log_pnl_snapshot(
                broker=self.broker.__class__.__name__,
                balance=balance,
                unrealized_pnl=total_unrealized,
                realized_pnl=Decimal("0"),  # TODO: Track realized P&L
                margin_ratio=margin_check.get("margin_ratio"),
                open_positions=len(positions)
            )

        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)

    def close_position(
        self,
        symbol: str,
        reason: str = "Manual close"
    ) -> Dict[str, any]:
        """
        Close an open position.

        Args:
            symbol: Trading pair
            reason: Reason for closing

        Returns:
            Dict with close details and success status
        """
        logger.info("Closing position", symbol=symbol, reason=reason)

        try:
            # Get position from broker
            positions = self.broker.positions()

            if symbol not in positions:
                logger.warning(f"No open position for {symbol}")
                return {
                    "success": False,
                    "reason": f"No open position for {symbol}"
                }

            pos = positions[symbol]
            exit_price = self.broker.get_ticker_price(symbol)

            # Close on exchange
            self.broker.close_all(symbol)

            # Log to database
            self.db.close_position(
                symbol=symbol,
                broker=self.broker.__class__.__name__,
                exit_price=exit_price,
                exit_reason=reason
            )

            logger.info(
                "Position closed",
                symbol=symbol,
                pnl=str(pos.unrealized_pnl)
            )

            return {
                "success": True,
                "exit_price": exit_price,
                "pnl": pos.unrealized_pnl
            }

        except Exception as e:
            logger.error(f"Failed to close position: {e}", exc_info=True)
            return {
                "success": False,
                "reason": str(e)
            }

    def _emergency_close_all(self):
        """Emergency close all positions."""
        try:
            positions = self.broker.positions()

            for symbol in positions.keys():
                self.close_position(symbol, reason="Emergency margin call")

            # Trigger kill switch
            self.risk.trigger_kill_switch("Margin call - all positions closed")

            # Log critical risk event
            self.db.log_risk_event(
                event_type="kill_switch",
                reason="Emergency margin call triggered",
                symbol=None,
                broker=self.broker.__class__.__name__
            )

        except Exception as e:
            logger.critical(f"FAILED TO CLOSE POSITIONS: {e}", exc_info=True)

    def _reduce_largest_position(self):
        """Reduce the largest position by 50%."""
        try:
            positions = self.broker.positions()

            if not positions:
                return

            # Find largest position by notional value
            largest = max(
                positions.items(),
                key=lambda x: abs(x[1].size * x[1].current_price)
            )

            symbol = largest[0]
            pos = largest[1]
            reduce_size = abs(pos.size) * Decimal("0.5")

            logger.warning(
                "Reducing position",
                symbol=symbol,
                current_size=str(pos.size),
                reduce_by=str(reduce_size)
            )

            # Execute reduction
            side = "sell" if pos.size > 0 else "buy"

            if side == "sell":
                self.broker.sell(symbol, reduce_size)
            else:
                self.broker.buy(symbol, reduce_size)

            logger.info(f"Position reduced for {symbol}")

        except Exception as e:
            logger.error(f"Failed to reduce position: {e}", exc_info=True)
```

---

## Integration Example

**File**: `examples/perpetual_futures_demo.py`

```python
"""
Demo: Perpetual Futures Trading with Full Risk Management.

Shows complete integration of all components.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv
from loguru import logger

from trade_engine.adapters.brokers.binance import BinanceFuturesBroker
from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.services.trading.position_manager import PositionManager
from trade_engine.db.postgres_adapter import PostgresDatabase


def main():
    """Run perpetual futures demo."""

    # Load environment variables
    load_dotenv()

    # Initialize components
    logger.info("Initializing trading system...")

    # 1. Database
    db = PostgresDatabase(
        database_url=os.getenv("DATABASE_URL")
    )

    # 2. Broker (testnet mode)
    broker = BinanceFuturesBroker(testnet=True)

    # 3. Funding service
    funding = FundingRateService(database=db)

    # 4. Risk manager
    risk = FuturesRiskManager(
        max_leverage=5,
        liquidation_buffer=Decimal("0.15"),
        max_position_size=Decimal("10000"),
        daily_loss_limit=Decimal("500"),
        max_drawdown=Decimal("1000")
    )

    # 5. Position manager
    pm = PositionManager(
        broker=broker,
        risk_manager=risk,
        funding_service=funding,
        database=db
    )

    # Demo: Open a position
    logger.info("Opening long position on BTCUSDT...")

    result = pm.open_position(
        symbol="BTCUSDT",
        side="long",
        size=Decimal("0.001"),
        leverage=3,
        strategy="demo"
    )

    if result["success"]:
        logger.info(
            "Position opened successfully",
            entry=str(result["entry_price"]),
            liquidation=str(result["liquidation_price"]),
            funding=str(result["funding_rate"])
        )
    else:
        logger.error(f"Failed to open position: {result['reason']}")
        return

    # Monitor position
    logger.info("Monitoring position...")
    pm.monitor_positions()

    # Check funding costs
    funding_rate = funding.get_current_funding_rate("BTCUSDT")
    daily_cost = funding.estimate_daily_funding(
        "BTCUSDT",
        Decimal("0.001"),
        result["entry_price"]
    )

    logger.info(
        "Funding analysis",
        rate=str(funding_rate),
        daily_cost=str(daily_cost)
    )

    # Close position (for demo)
    logger.info("Closing position...")
    close_result = pm.close_position("BTCUSDT", reason="Demo completed")

    if close_result["success"]:
        logger.info(
            "Position closed",
            pnl=str(close_result["pnl"])
        )

    logger.info("Demo complete!")


if __name__ == "__main__":
    main()
```

---

## Testing Strategy

### Unit Tests (Priority: High)
```bash
pytest tests/unit/test_funding_rate_service.py -v
pytest tests/unit/test_futures_risk_manager.py -v
pytest tests/unit/test_position_manager.py -v
```

### Integration Tests (Priority: Medium)
```bash
pytest tests/integration/test_futures_trading_flow.py -v
```

### Simulation Tests (Priority: Low)
```bash
python scripts/simulate_perpetual_trading.py --duration 24h
```

---

## Deployment Checklist

- [ ] Phase 1: Funding service implemented and tested
- [ ] Phase 2: Futures risk manager implemented and tested
- [ ] Phase 3: Database schema enhanced
- [ ] Phase 4: Position manager implemented and tested
- [ ] Integration example working on testnet
- [ ] 24-hour simulation completed successfully
- [ ] Documentation updated
- [ ] CI/CD tests passing

---

## Next Steps (Beyond This Plan)

### Dashboard Integration (Phase 5)
- Streamlit dashboard reading from `pnl_snapshots` and `funding_events`
- FastAPI endpoints: `/api/pnl`, `/api/risk`, `/api/funding`
- React frontend for visualization

### Advanced Features (Phase 6+)
- Multi-symbol position management
- Auto-deleveraging logic
- Funding rate arbitrage strategies
- Cross-margin optimization

---

## Risk Acknowledgment

**CRITICAL REMINDERS** (NON-NEGOTIABLE):
- Paper trade for 60 days minimum before live trading
- Start with micro-capital ($100-500) for 30 days
- Never exceed hard risk limits
- Test kill switch functionality thoroughly
- Monitor margin health continuously
- Account for funding costs in P&L calculations

---

**Document Status**: Ready for implementation
**Estimated Implementation Time**: 10-15 hours
**Risk Level**: Medium (extends proven architecture)
**Testing Required**: Comprehensive (unit + integration + simulation)
