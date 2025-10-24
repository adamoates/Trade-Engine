# Live Trading Evolution Architecture

**Last Updated**: 2025-10-23
**Category**: Architecture
**Status**: Proposed
**Decision**: Pending stakeholder approval

---

## Executive Summary

Evolution plan from research platform → production trading bot while preserving all existing infrastructure.

**Current State**: Research-grade backtesting platform
**Target State**: Live trading bot with paper trading → small live → scale
**Timeline**: 4 phases, ~6-8 weeks
**Capital Requirements**: Testnet (free) → $500 (small live) → $2-5k (scale)

---

## The Path: Research Tool → Trading Bot

### Phase 0 — Freeze What Works (✅ COMPLETE)

**Status**: DONE
**What We Have**:
- ✅ Data pipeline: fetch → validate → detect → backtest
- ✅ Fee-aware backtesting
- ✅ Regime detection system
- ✅ Strategy implementation (trending_v3)
- ✅ Makefile workflows
- ✅ Comprehensive documentation

**Infrastructure Value**: ~$15k equivalent
**Next**: Harden for live trading

---

### Phase 1 — Hardening for Live (2-3 weeks)

**Goal**: Make backtest match live trading behavior exactly

**Tasks**:

1. **Deterministic Configs** (1-2 days)
   ```yaml
   # config/live.yaml
   symbols:
     - BTCUSDT

   timeframe: 5m

   strategy:
     name: trending_v3
     params:
       tp_atr: 1.25
       sl_atr: 0.9
       min_atr_pct: 0.0015
       cooldown_bars: 3

   risk:
     max_position_usd: 500
     max_daily_loss_usd: 100
     max_trades_per_day: 10
     trading_hours:
       start: "00:00"
       end: "23:59"

   costs:
     fee_bps: 4          # Futures: 0.04%
     spread_bps: 2
     slippage_bps: 1
   ```

2. **Risk Limits** (2-3 days)
   - Max position size (per symbol)
   - Max daily loss (kill switch trigger)
   - Trading hours enforcement
   - Cooldown between trades
   - Max concurrent positions

3. **Latency Realism** (1-2 days)
   - Enforce bar-close execution in backtest
   - Add order fill delay simulation (50-200ms)
   - Slippage modeling (bid-ask spread)
   - Reject stale bars (>5s old)

4. **Audit Logging** (1 day)
   ```json
   {"ts": "2025-10-23T14:30:00Z", "event": "signal", "side": "buy", "symbol": "BTCUSDT", "price": 67450, "atr": 450}
   {"ts": "2025-10-23T14:30:01Z", "event": "order_intent", "order_id": "abc123", "qty": 0.01}
   {"ts": "2025-10-23T14:30:02Z", "event": "fill", "order_id": "abc123", "fill_price": 67455}
   ```

**Deliverables**:
- `config/live.yaml`, `config/paper.yaml`
- `app/engine/risk.py` - Risk management
- `app/engine/portfolio.py` - Position tracking
- Updated backtest with bar-close enforcement
- Audit log system (JSON lines)

**Success Criteria**:
- Backtest P&L matches paper trading P&L (within 2%)
- Risk limits trigger correctly
- All trades logged with full audit trail

---

### Phase 2 — Paper Trading (2-3 weeks)

**Goal**: Run strategy live (no real money), prove it matches backtest

**Tasks**:

1. **Broker Adapter** (3-4 days)
   ```python
   # app/adapters/broker_binance.py
   class BinanceFuturesBroker:
       def buy(self, symbol, qty, sl=None, tp=None) -> str:
           """Place buy order. Returns order ID."""
           pass

       def sell(self, symbol, qty, sl=None, tp=None) -> str:
           """Place sell order. Returns order ID."""
           pass

       def close_all(self, symbol):
           """Flatten position."""
           pass

       def positions(self) -> dict:
           """Get current positions."""
           pass
   ```

2. **Live Data Feed** (2-3 days)
   ```python
   # app/adapters/data_binance_ws.py
   class BinanceFuturesDataFeed:
       def candles(self):
           """Yield completed bars, validated."""
           while True:
               bar = self._fetch_latest_bar()
               if self._validate_bar(bar):
                   yield bar
               time.sleep(poll_interval)
   ```

3. **Live Runner** (2-3 days)
   ```python
   # app/engine/runner_live.py
   def run(strategy, data, broker, risk, config):
       for bar in data.candles():
           # Update strategy state
           state = strategy.on_bar(bar)

           # Risk checks
           if risk.block_trading():
               continue

           # Execute signals
           for sig in state.signals:
               if sig.side == "buy":
                   broker.buy(sig.symbol, sig.qty, sig.sl, sig.tp)

           # Update risk metrics
           risk.update(broker.positions(), bar)
   ```

4. **Paper Trading** (1-2 weeks live testing)
   - Run on Binance Futures testnet
   - Compare live paper P&L vs backtest P&L
   - Fix any discrepancies
   - Run for 7-14 days minimum

**Deliverables**:
- `app/adapters/broker_binance.py` - Binance Futures adapter
- `app/adapters/data_binance_ws.py` - Live bar feed
- `app/engine/runner_live.py` - Live execution engine
- `app/engine/runner_paper.py` - Paper trading mode
- Paper trading results (7-14 day comparison)

**Success Criteria**:
- Live paper P&L matches backtest within 5%
- All risk limits enforced correctly
- No missed bars or execution errors
- Clean audit logs for all decisions

---

### Phase 3 — Small Live Trading (2-3 weeks)

**Goal**: Real money, tiny size, strict limits

**Tasks**:

1. **Production Infrastructure** (3-5 days)
   - VPS deployment (already have)
   - Secrets management (environment vars)
   - Monitoring (Prometheus/Grafana or simple)
   - Alerting (Telegram/email on errors)
   - Daily reports (P&L, trades, errors)

2. **Kill Switch** (1 day)
   ```python
   # Check file flag every bar
   if Path("/tmp/mft_halt.flag").exists():
       logger.critical("KILL SWITCH ACTIVATED")
       broker.close_all()
       sys.exit(0)

   # Or check daily loss
   if risk.daily_loss > config.max_daily_loss:
       logger.critical("MAX DAILY LOSS HIT")
       broker.close_all()
       sys.exit(0)
   ```

3. **Small Live Run** (1-2 weeks)
   - Start with $500 capital
   - Max position: $100 (tiny)
   - Max daily loss: $20 (4% of capital)
   - Run for 1-2 weeks
   - Monitor closely (check 3x daily)

**Deliverables**:
- Production deployment scripts
- Kill switch implementation
- Monitoring dashboard (simple)
- Alert system (Telegram bot)
- Daily report generator

**Success Criteria**:
- No catastrophic losses (max loss = $20/day)
- Strategy executes as expected
- All alerts work correctly
- Daily reports accurate
- Clean shutdown on errors

---

### Phase 4 — Reliability & Scale (ongoing)

**Goal**: Scale capital, improve reliability

**Tasks**:

1. **Observability** (1 week)
   - Prometheus metrics (fills, errors, latency)
   - Grafana dashboard (P&L, positions, regimes)
   - Log aggregation (structured logs)
   - On-call alerts (PagerDuty or similar)

2. **Reliability** (1-2 weeks)
   - Heartbeat monitoring (detect hung processes)
   - Graceful shutdown (finish pending orders)
   - State persistence (survive restarts)
   - Error recovery (retry logic)

3. **Scale Capital** (gradual)
   - Week 1-2: $500 capital
   - Week 3-4: $1k capital (if profitable)
   - Week 5-8: $2-5k capital (if consistent)

**Deliverables**:
- Prometheus metrics
- Grafana dashboard
- On-call playbook
- State persistence
- Scaling plan

**Success Criteria**:
- 99.9% uptime
- <5s bar processing latency
- Zero missed trades (network permitting)
- Profitable over 4+ weeks

---

## Minimal Architecture (Drop-In Friendly)

### Directory Structure

```
MFT/
├── app/                          # NEW: Live trading application
│   ├── __init__.py
│   ├── adapters/                 # External integrations
│   │   ├── __init__.py
│   │   ├── broker_binance.py    # Binance Futures API
│   │   └── data_binance.py      # Live candle feed
│   ├── engine/                   # Core execution
│   │   ├── __init__.py
│   │   ├── types.py             # Interfaces (ABC)
│   │   ├── runner_live.py       # Live bar-close loop
│   │   ├── runner_paper.py      # Paper trading mode
│   │   ├── portfolio.py         # P&L, positions, exposure
│   │   └── risk.py              # Risk limits, kill switch
│   ├── strategies/               # Strategy wrappers
│   │   ├── __init__.py
│   │   └── trending.py          # Wrap existing trending_v3
│   └── config/                   # Configuration
│       ├── live.yaml
│       └── paper.yaml
├── tools/                        # EXISTING: Keep as-is
│   ├── fetch_binance_ohlcv.py
│   └── validate_clean_ohlcv.py
├── strategies/                   # EXISTING: Keep as-is
│   └── implementations/
│       └── trending_strategy_v3.py
├── scripts/                      # EXISTING: Keep as-is
└── Makefile                      # EXISTING: Add live targets
```

---

## Core Interfaces (Simple, Testable)

### Abstract Interfaces

```python
# app/engine/types.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator

class Bar:
    """Single OHLCV bar."""
    timestamp: int       # UTC timestamp (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float

class Signal:
    """Trading signal."""
    symbol: str
    side: str           # "buy" | "sell" | "close"
    qty: float
    sl: float | None
    tp: float | None

class DataFeed(ABC):
    """Live data source."""

    @abstractmethod
    def candles(self) -> Iterator[Bar]:
        """Yield validated bars (bar-close only)."""
        pass

class Broker(ABC):
    """Execution interface."""

    @abstractmethod
    def buy(self, symbol: str, qty: float, sl: float|None=None, tp: float|None=None) -> str:
        """Place buy order. Returns order ID."""
        pass

    @abstractmethod
    def sell(self, symbol: str, qty: float, sl: float|None=None, tp: float|None=None) -> str:
        """Place sell order. Returns order ID."""
        pass

    @abstractmethod
    def close_all(self, symbol: str):
        """Flatten position."""
        pass

    @abstractmethod
    def positions(self) -> Dict[str, Any]:
        """Get current positions."""
        pass

class Strategy(ABC):
    """Strategy interface."""

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[Signal]:
        """Process bar, return signals."""
        pass
```

---

## What to Reuse (No Rework)

### 1. Data & Validation
```python
# EXISTING: tools/fetch_binance_ohlcv.py
# EXISTING: tools/validate_clean_ohlcv.py

# NEW: Use in live bar validation
from tools.validate_clean_ohlcv import _detect_issues, _enforce_dtypes

def validate_live_bar(bar):
    # Reuse existing validation logic
    # Check for gaps, zero volume, dtype issues
    pass
```

### 2. Strategy Logic
```python
# EXISTING: strategies/implementations/trending_strategy_v3.py
# Contains: TrendingStrategyV3 class

# NEW: Thin wrapper
# app/strategies/trending.py
from strategies.implementations.trending_strategy_v3 import TrendingStrategyV3

class TrendingLiveStrategy(Strategy):
    def __init__(self, config):
        self.strategy = TrendingStrategyV3(config.params)

    def on_bar(self, bar: Bar) -> list[Signal]:
        # Convert bar to strategy format
        # Call existing strategy
        # Convert signals back
        return signals
```

### 3. Cost Assumptions
```yaml
# config/live.yaml
costs:
  fee_bps: 4           # Same as backtest
  spread_bps: 2        # Same as backtest
  slippage_bps: 1      # Same as backtest

# Enforce in live routing
if signal.tp - signal.entry < costs.roundtrip_bps:
    logger.warn("TP too tight, skipping")
    continue
```

---

## Risk & Control Checklist (Non-Negotiable)

### Position Caps
```python
# app/engine/risk.py
class RiskManager:
    def check_position_size(self, symbol, qty, price):
        notional = qty * price
        if notional > self.config.max_position_usd:
            raise RiskViolation(f"Position too large: {notional}")

        total_exposure = sum(p.notional for p in self.positions.values())
        if total_exposure + notional > self.config.max_total_exposure:
            raise RiskViolation(f"Total exposure too high: {total_exposure}")
```

### Max Daily Loss
```python
def check_daily_loss(self):
    daily_pnl = sum(p.pnl for p in self.positions.values())
    if daily_pnl < -self.config.max_daily_loss_usd:
        logger.critical(f"MAX DAILY LOSS HIT: {daily_pnl}")
        self.broker.close_all()
        self.halt()
        raise DailyLossExceeded()
```

### Throttle
```python
def check_trade_throttle(self):
    trades_today = len([t for t in self.trades if t.date == today()])
    if trades_today >= self.config.max_trades_per_day:
        raise ThrottleExceeded(f"Max trades/day: {trades_today}")
```

### Kill Switch
```python
def check_kill_switch(self):
    # File flag
    if Path("/tmp/mft_halt.flag").exists():
        logger.critical("KILL SWITCH: File flag detected")
        self.broker.close_all()
        sys.exit(0)

    # Config reload (for remote kill)
    if self.reload_config_if_changed():
        if self.config.halt:
            logger.critical("KILL SWITCH: Config halt=true")
            self.broker.close_all()
            sys.exit(0)
```

### Audit Log
```python
def log_decision(self, event_type, **kwargs):
    log = {
        "ts": datetime.utcnow().isoformat(),
        "event": event_type,
        **kwargs
    }
    # Append to JSON lines file
    with open(f"logs/audit_{today()}.jsonl", "a") as f:
        f.write(json.dumps(log) + "\n")

# Usage
self.log_decision("signal", side="buy", symbol="BTCUSDT", price=67450, atr=450)
self.log_decision("order_intent", order_id="abc123", qty=0.01)
self.log_decision("fill", order_id="abc123", fill_price=67455)
self.log_decision("risk_block", reason="max_daily_loss")
```

---

## Naming for Investors/Partners

**Current**:
"MFT Trading Bot - Phase 0 POC"

**Evolution**:
"A quantitative cryptocurrency trading platform with research-grade backtesting and a live paper-trading engine, designed to move safely from research to production with strict risk controls."

**Positioning**:
- Research platform first (proven infrastructure)
- Production-ready components (audit logging, risk management)
- Gradual capital scaling (testnet → $500 → $5k)
- Institutional-grade controls (kill switch, daily loss limits)

---

## Next Steps (Concrete, Actionable)

### Immediate (This Week)

1. **Create directory structure**:
   ```bash
   mkdir -p app/{adapters,engine,strategies,config}
   touch app/__init__.py
   touch app/{adapters,engine,strategies}/__init__.py
   ```

2. **Implement core interfaces** (`app/engine/types.py`)
   - DataFeed ABC
   - Broker ABC
   - Strategy ABC
   - Bar, Signal dataclasses

3. **Paper broker stub** (Binance Futures testnet)
   - API key management (env vars)
   - buy/sell/close_all/positions methods
   - Error handling, retry logic

4. **Bar-close live runner** (`app/engine/runner_live.py`)
   - Poll /fapi/v1/klines at bar close
   - Validate bars (reuse existing validator)
   - Call strategy.on_bar()
   - Execute signals via broker

5. **Create configs**:
   ```yaml
   # config/paper.yaml
   mode: paper
   binance:
     api_key: ${BINANCE_TESTNET_API_KEY}
     api_secret: ${BINANCE_TESTNET_API_SECRET}
     testnet: true
   symbols:
     - BTCUSDT
   timeframe: 5m
   strategy:
     name: trending_v3
     params:
       tp_atr: 1.25
       sl_atr: 0.9
   risk:
     max_position_usd: 100
     max_daily_loss_usd: 20
   ```

### Week 2-3

1. Implement risk management (`app/engine/risk.py`)
2. Add audit logging
3. Run paper trading for 7 days
4. Compare paper P&L vs backtest P&L
5. Fix discrepancies

### Week 4-6

1. Deploy to VPS
2. Add monitoring (simple dashboard)
3. Implement kill switch
4. Small live run ($500 capital)
5. Daily manual checks

---

## Decision Required

**Stakeholder approval needed for**:
1. Proceed with Phase 1 (hardening) - 2-3 weeks effort
2. Capital allocation for Phase 3 (small live: $500)
3. Timeline approval (6-8 weeks total)

**Alternative**: Archive project and document learnings

---

## Files to Generate Next

If approved, I will create:

1. **`app/engine/types.py`** - Core interfaces (ABC)
2. **`app/adapters/broker_binance.py`** - Binance Futures paper broker (~150 lines)
3. **`app/engine/runner_live.py`** - Bar-close live runner (~120 lines)
4. **`app/engine/risk.py`** - Risk management (~200 lines)
5. **`config/paper.yaml`** - Paper trading config
6. **`config/live.yaml`** - Live trading config template

**Ready to proceed when stakeholder approves.**

---

**Credit**: Evolution plan based on user-provided roadmap (Phase 0-4 structure).
**Status**: Architecture designed, awaiting approval to implement.
