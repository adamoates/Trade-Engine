# Trade Engine Refactoring Plan

## Executive Summary

Reorganize the codebase to follow best practices from CLAUDE.md, adapted for a **trading bot** (not a web app). The goal is clearer separation of concerns, better testability, and preparation for adding FastAPI later.

## Current State

```
src/trade_engine/
├── api/                    # Empty (planned for Phase 3)
├── core/
│   ├── constants.py       # Global constants
│   ├── config/            # YAML configs
│   └── engine/            # Trading engine (runner, risk, audit)
├── db/                     # Empty (planned for Phase 2)
├── models/                 # Empty (no database yet)
├── services/
│   ├── adapters/          # Broker & data feed implementations
│   ├── backtest/          # Backtesting engine
│   ├── data/              # Data sources & aggregation
│   └── strategies/        # Trading strategies
└── utils/                  # Empty
```

**Issues:**
1. `core/engine/` contains business logic (should be in `services/`)
2. Empty directories (`api/`, `db/`, `models/`, `utils/`)
3. Configuration mixed with engine code
4. No clear separation between domain logic and infrastructure

## Target State (Adapted from CLAUDE.md)

```
src/trade_engine/
├── core/                   # Core configuration & types
│   ├── __init__.py
│   ├── config.py          # Settings (Pydantic, env vars)
│   ├── constants.py       # Global constants
│   ├── exceptions.py      # Custom exceptions
│   └── types.py           # Shared type definitions
│
├── domain/                 # Business logic (pure Python, no I/O)
│   ├── __init__.py
│   ├── models/            # Domain models (Position, Order, Trade)
│   │   ├── __init__.py
│   │   ├── position.py
│   │   ├── order.py
│   │   ├── trade.py
│   │   └── market_data.py
│   ├── strategies/        # Trading strategies (pure logic)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── l2_imbalance.py
│   │   ├── ma_crossover.py
│   │   └── ...
│   └── risk/              # Risk management logic
│       ├── __init__.py
│       ├── position_sizer.py
│       ├── risk_manager.py
│       └── validators.py
│
├── services/               # Application services (orchestration)
│   ├── __init__.py
│   ├── trading/           # Trading engine services
│   │   ├── __init__.py
│   │   ├── engine.py      # Main trading engine
│   │   ├── executor.py    # Order execution
│   │   └── portfolio.py   # Portfolio management
│   ├── data/              # Data ingestion & processing
│   │   ├── __init__.py
│   │   ├── aggregator.py
│   │   ├── normalizer.py
│   │   └── validators.py
│   ├── backtest/          # Backtesting services
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── metrics.py
│   │   └── reporter.py
│   └── audit/             # Audit & logging services
│       ├── __init__.py
│       └── logger.py
│
├── adapters/               # External integrations (infrastructure)
│   ├── __init__.py
│   ├── brokers/           # Broker implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── binance.py
│   │   ├── binance_us.py
│   │   ├── kraken.py
│   │   └── simulated.py
│   ├── data_sources/      # Data source implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── binance.py
│   │   ├── alphavantage.py
│   │   ├── coingecko.py
│   │   └── ...
│   └── feeds/             # Real-time data feeds
│       ├── __init__.py
│       ├── base.py
│       └── binance_l2.py
│
├── api/                    # API layer (Phase 3)
│   ├── __init__.py
│   ├── main.py            # FastAPI app
│   ├── dependencies.py    # FastAPI dependencies
│   └── v1/
│       ├── __init__.py
│       ├── router.py
│       └── endpoints/
│           ├── engine.py  # Engine control
│           ├── positions.py
│           └── orders.py
│
├── db/                     # Database layer (Phase 2)
│   ├── __init__.py
│   ├── base.py            # SQLAlchemy base
│   ├── session.py         # Session management
│   └── models/            # SQLAlchemy models
│       ├── __init__.py
│       ├── trade.py
│       ├── position.py
│       └── audit.py
│
├── schemas/                # Pydantic schemas (validation & serialization)
│   ├── __init__.py
│   ├── position.py
│   ├── order.py
│   ├── trade.py
│   └── market_data.py
│
└── utils/                  # Utilities
    ├── __init__.py
    ├── datetime.py        # Date/time helpers
    ├── decimal.py         # Decimal helpers (financial math)
    └── validators.py      # Generic validators
```

## Refactoring Strategy

### Phase 1: Create New Structure (No Breaking Changes)

1. **Create new directories**
   ```bash
   mkdir -p src/trade_engine/{domain,adapters,schemas}
   mkdir -p src/trade_engine/domain/{models,strategies,risk}
   mkdir -p src/trade_engine/adapters/{brokers,data_sources,feeds}
   ```

2. **Move files to new locations (copy first, then delete)**
   - `core/engine/` → `services/trading/` & `domain/risk/`
   - `services/adapters/broker_*.py` → `adapters/brokers/`
   - `services/adapters/feed_*.py` → `adapters/feeds/`
   - `services/data/source_*.py` → `adapters/data_sources/`
   - `services/strategies/` → `domain/strategies/`

3. **Extract domain models from existing code**
   - Create `domain/models/position.py`, `order.py`, `trade.py`
   - Extract dataclasses/types from existing code

4. **Update imports (automated script)**
   ```python
   # Use AST to update all imports
   # Old: from trade_engine.services.adapters.broker_binance import BinanceBroker
   # New: from trade_engine.adapters.brokers.binance import BinanceBroker
   ```

### Phase 2: Improve Configuration

1. **Replace YAML configs with Pydantic Settings**
   ```python
   # core/config.py
   from pydantic_settings import BaseSettings

   class TradingSettings(BaseSettings):
       # Load from .env or environment
       binance_api_key: str
       binance_api_secret: str
       max_position_size: Decimal
       daily_loss_limit: Decimal

       class Config:
           env_file = ".env"
   ```

2. **Remove `core/config/*.yaml`, use `.env` files instead**
   - `.env.example` - Template
   - `.env.development` - Local development
   - `.env.production` - Production values

### Phase 3: Add Pydantic Schemas

1. **Create validation schemas for all data structures**
   ```python
   # schemas/position.py
   from pydantic import BaseModel, Field
   from decimal import Decimal

   class PositionCreate(BaseModel):
       symbol: str
       size: Decimal
       side: Literal["long", "short"]

   class PositionResponse(PositionCreate):
       id: int
       unrealized_pnl: Decimal
       entry_price: Decimal
   ```

### Phase 4: Separate Domain Logic from Infrastructure

1. **Domain layer = Pure business logic (no I/O, no external dependencies)**
   - Strategies calculate signals
   - Risk manager validates positions
   - Domain models represent core concepts

2. **Services layer = Orchestration & coordination**
   - Trading engine coordinates everything
   - Data aggregator combines sources
   - Backtest engine runs simulations

3. **Adapters layer = External integrations**
   - Broker implementations
   - Data source implementations
   - Feed implementations

**Benefits:**
- Domain logic is easily testable (no mocks needed)
- Can swap brokers without changing strategies
- Can test strategies without external APIs

### Phase 5: Update Tests

1. **Reorganize tests to match new structure**
   ```
   tests/
   ├── unit/
   │   ├── domain/          # Test pure logic (fast)
   │   │   ├── test_strategies/
   │   │   ├── test_risk/
   │   │   └── test_models/
   │   ├── services/        # Test orchestration (with mocks)
   │   └── adapters/        # Test with mocks/fixtures
   ├── integration/         # Test with real external systems
   │   ├── test_binance_broker.py
   │   └── test_data_aggregator.py
   └── e2e/                 # Full system tests
       └── test_trading_flow.py
   ```

2. **Update test imports**
3. **Ensure 100% test coverage for risk logic**

### Phase 6: Documentation

1. **Update CLAUDE.md to reflect trading bot structure**
2. **Add docstrings to all public APIs**
3. **Create architecture diagram**

## Migration Path

### Option A: Big Bang (1 day, risky)
- Do all changes at once
- High risk of breaking things
- Faster if successful

### Option B: Incremental (1 week, safer) ✅ RECOMMENDED
1. **Day 1:** Create new structure, copy files (both old & new exist)
2. **Day 2:** Update imports in new files
3. **Day 3:** Update tests
4. **Day 4:** Delete old files, verify everything works
5. **Day 5:** Update documentation

### Option C: Parallel (2 weeks, safest)
- Keep old structure fully functional
- Build new structure alongside
- Gradually migrate modules one at a time
- Delete old structure only when 100% migrated

## Breaking Changes

**Imports will change:**
```python
# Old
from trade_engine.services.adapters.broker_binance import BinanceBroker
from trade_engine.core.engine.risk_manager import RiskManager
from trade_engine.services.strategies.alpha_l2_imbalance import L2ImbalanceStrategy

# New
from trade_engine.adapters.brokers.binance import BinanceBroker
from trade_engine.domain.risk.risk_manager import RiskManager
from trade_engine.domain.strategies.l2_imbalance import L2ImbalanceStrategy
```

**Config will change:**
```python
# Old
config = yaml.load(open("core/config/paper.yaml"))

# New
from trade_engine.core.config import settings
# settings loaded from .env automatically
```

## Benefits

1. **Clearer separation of concerns**
   - Domain logic isolated (easy to test, easy to understand)
   - Infrastructure code separate (easy to swap implementations)

2. **Better testability**
   - Domain tests don't need mocks
   - Can test strategies without external APIs

3. **Easier to add FastAPI later**
   - API layer already has dedicated space
   - Services already separated from HTTP layer

4. **Follows industry best practices**
   - Hexagonal/Clean Architecture principles
   - Dependency inversion (domain doesn't depend on adapters)

5. **Preparation for scaling**
   - Easy to add new brokers
   - Easy to add new strategies
   - Easy to add new data sources

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing scripts | High | Run full test suite after each change |
| Import errors everywhere | High | Use automated refactoring script |
| Losing git history | Medium | Use `git mv` to preserve history |
| Tests failing | High | Fix tests incrementally, don't move on until green |
| Merge conflicts if others working | High | Coordinate timing, do in one PR |

## Decision Required

**Which migration path do you prefer?**

- [ ] **Option A (Big Bang)** - Fast but risky, 1 day
- [ ] **Option B (Incremental)** - Balanced, 1 week ✅ RECOMMENDED
- [ ] **Option C (Parallel)** - Safest, 2 weeks

**What to prioritize?**

- [ ] Speed (get it done fast)
- [ ] Safety (minimize risk of breaking things) ✅ RECOMMENDED
- [ ] Learning (understand each change deeply)

---

**Next Steps:**

1. Review this plan
2. Choose migration path
3. I'll create automated refactoring scripts
4. Execute refactoring
5. Update tests
6. Update documentation
