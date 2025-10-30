# Action Plan: Infrastructure Improvements

**Date**: 2025-10-29
**Phase**: 0 → 1 Transition
**Priority**: Address critical gaps before Phase 1

This document tracks improvements based on comprehensive code review feedback.

---

## ✅ What's Already Working

### Infrastructure
- ✅ **CI/CD Pipeline**: Comprehensive GitHub Actions workflow
  - Backend: Black, Ruff, mypy, pytest (465 tests, 100% passing)
  - Frontend: Lint & test
  - Security: Dependency audit
  - Risk Manager: Extra validation
  - Quality gates enforced on all PRs

- ✅ **Structured Logging**: JSON Lines format, event-based, daily rotation
  - Three log files: `trade_engine_*.log`, `trades_*.log`, `errors_*.log`
  - Decimal precision enforced (NON-NEGOTIABLE)
  - TradingLogger with 8 standardized events
  - See: `docs/guides/logging-guide.md`

- ✅ **Clean Architecture**: Three-layer separation
  - Domain: Strategies, business logic
  - Services: Orchestration, backtesting
  - Adapters: Brokers, feeds, data sources

- ✅ **Base Interfaces Defined**:
  - `adapters/brokers/base.py`
  - `adapters/feeds/base.py`
  - `adapters/data_sources/base.py`

---

## 🔴 Critical Priorities (Do Now)

### 1. Float Usage Enforcement ⚠️ **CRITICAL**
**Status**: ✅ **COMPLETED** (PR #23 + follow-up fixes - 2025-10-30)
**Why Critical**: Float rounding errors can cause financial losses

**Completed Actions**:
- ✅ Audit script created (`scripts/audit_float_usage.sh`) with 8 detection patterns
- ✅ **Critical trading path 100% clean** (core/, brokers/, alpha_l2_imbalance):
  - Core types (Position, Signal, Order) use Decimal
  - All broker adapters (Binance, Kraken, Binance.us) use Decimal
  - L2 imbalance strategy: prices use Decimal, timestamps use int
  - Binance.get_ticker_price() returns Decimal (not float)
- ✅ CI check added: detects float in critical financial code
- ✅ Audit verification: `grep` reports no float in critical path

**Remaining Work** (non-critical, acceptable for now):
- [ ] Services layer has float usage (signal_normalizer, data aggregator, backtest metrics)
  - *Rationale*: Derived metrics (Sharpe ratio, z-scores) don't require Decimal precision
  - *Tracked*: Will revisit if precision issues arise in Phase 2+ (backtest validation)
- [ ] Alpha strategies (MACD, RSI, Bollinger) use float for indicators
  - *Rationale*: Technical indicators are not in critical execution path
  - *Tracked*: Acceptable unless used in live signal generation
- [ ] Add pre-commit hook (recommended but not blocking)
  - *Tracked*: Item #12 (future optimization)

**Note**: CI enforces Decimal in **critical trading path only** (core, brokers, L2 strategy). Non-critical code allowed to use float for performance/convenience.

**Owner**: Completed
**Completed**: 2025-10-30 (PR #23 + commit 93d8ddf)

---

### 2. Secrets Management 🔒
**Status**: ✅ **MOSTLY COMPLETE** (PR #23 - 2025-10-30)

**Completed Actions**:
- ✅ `.env.example` exists with template
- ✅ `.env` in `.gitignore`
- ✅ CI check: detects `.env` files in commits
- ✅ CI check: detects API keys in logging code
- ✅ Secret detection tool: TruffleHog added to CI

**Remaining Work**:
- [ ] Document secrets policy in `docs/security.md`
- [ ] Plan for production: AWS Secrets Manager or Vault (Phase 3+)
- [ ] Optional: Add pre-commit hook for local enforcement

**Owner**: TBD
**Target**: Phase 0 (documentation), Phase 3 (production secrets manager)

---

### 3. Risk Management Rules as Code 📋
**Status**: ✅ **COMPLETED** (PR #23 - 2025-10-30)

**Completed Actions**:
- ✅ Created `src/trade_engine/core/risk_rules.py` with frozen RiskLimits dataclass
- ✅ All hard limits defined as constants with Decimal precision
  ```python
  @dataclass(frozen=True)
  class RiskLimits:
      MAX_POSITION_SIZE_USD: Final[Decimal] = Decimal("10000")
      DAILY_LOSS_LIMIT_USD: Final[Decimal] = Decimal("-500")
      MAX_DRAWDOWN_USD: Final[Decimal] = Decimal("-1000")
      MAX_INSTRUMENT_EXPOSURE_PCT: Final[Decimal] = Decimal("0.25")
      MAX_HOLD_TIME_SECONDS: Final[int] = 60
      # ... 12 total limits defined
  ```
- ✅ Validation functions for all limits
- ✅ 60 comprehensive tests (100% coverage, 480 lines)
- ✅ CI check verifies risk rules use correct types (Decimal/int)
- ✅ Documentation in docstrings

**Owner**: Completed
**Completed**: 2025-10-30 (PR #23)

---

## 🟡 High Priority (Phase 0→1 Transition)

### 4. Postgres/TimescaleDB Schema Design 🗄️
**Status**: Not started
**Why Important**: Phase 2 needs DB, schema changes are expensive

**Design Decisions Needed**:
1. **Time-series data storage**:
   - L2 order book snapshots (5 levels @ 1/sec = 432K rows/day/symbol)
   - Should we store snapshots or deltas?
   - Compression strategy?
   - Retention policy? (90 days? 1 year?)

2. **Tables**:
   ```sql
   -- Core trading tables
   trades (id, timestamp, symbol, side, size, price, pnl, strategy_id, ...)
   positions (id, symbol, entry_time, exit_time, entry_price, exit_price, pnl, ...)
   orders (id, timestamp, symbol, side, size, price, status, fill_time, ...)

   -- Time-series tables (TimescaleDB hypertables)
   order_book_snapshots (timestamp, symbol, level, bid_price, bid_qty, ask_price, ask_qty)
   signals (timestamp, strategy_id, symbol, side, strength, reason)
   risk_events (timestamp, event_type, metric_value, limit_value, action_taken)

   -- Metadata tables
   strategies (id, name, version, config_json, created_at)
   instruments (symbol, exchange, tick_size, lot_size, fees)
   ```

3. **Indexes**:
   - Time-based queries (most common)
   - Symbol + time range queries
   - Strategy performance queries

**Actions**:
- [ ] Create `docs/database-schema.md` with ER diagram
- [ ] Define retention policies per table type
- [ ] Estimate storage requirements (1 month, 1 year)
- [ ] Create migration scripts (`migrations/001_initial_schema.sql`)
- [ ] Add SQLAlchemy models (`src/trade_engine/core/models.py`)
- [ ] Document backup/restore procedures

**Owner**: TBD
**Target**: Phase 1 (before Phase 2 implementation)

---

### 5. Adapter Interface Specifications 🔌
**Status**: ✅ **MOSTLY COMPLETE** (2025-10-30)

**Current State**:
- `BrokerAdapter` base class exists
- `FeedAdapter` base class exists
- `DataSourceAdapter` base class exists
- 4 broker implementations (Binance, Binance.us, Kraken, simulated)
- 2 feed implementations (BinanceFuturesL2, BinanceUSL2)
- 0 data source implementations (Phase 1)

**Completed Actions**:
- ✅ Document adapter contracts in `docs/reference/adapters/`
  - ✅ `broker-interface.md`: Complete spec with 5 core methods + 4 extended methods
  - ✅ `feed-interface.md`: Complete spec with WebSocket streaming, OrderBook class
  - ✅ `data-source-interface.md`: Complete spec for REST API data fetching
  - ✅ `README.md`: Index with quick start, design principles, testing strategy
  - ✅ `how-to-add-adapters.md`: Step-by-step guide with code templates

**Documentation Highlights**:
- 📖 **Broker Interface**: 25 pages covering synchronous + async interfaces, error handling, health checks
- 📖 **Feed Interface**: 28 pages covering WebSocket streaming, OrderBook patterns, performance targets
- 📖 **Data Source Interface**: 18 pages covering REST API patterns, rate limiting, caching
- 📖 **How-To Guide**: 22 pages with step-by-step instructions, code templates, common pitfalls
- 📖 **README**: 13 pages with overview, design principles, testing strategy, current implementations

**Remaining Work**:
- [ ] Add type hints and docstrings to base classes (minor improvement)
- [ ] Create adapter integration test template (tests/integration/adapters/)
- [ ] Add adapter health check methods to existing implementations
  - `get_latency_ms()` - Measure API ping latency
  - `get_rate_limit_status()` - Track requests used vs limit
  - `is_healthy()` - Overall health check

**Owner**: Completed (documentation), Health checks TBD
**Target**: Documentation ✅ Complete, Health checks Phase 1

---

### 6. Latency & Slippage Monitoring 📊
**Status**: Not implemented
**Why Important**: Medium-frequency strategies need sub-100ms latency

**Metrics to Track**:
1. **Latency Metrics**:
   - API call latency (exchange REST API)
   - WebSocket message latency (order book updates)
   - Order placement latency (signal → order sent)
   - Fill latency (order sent → fill confirmed)
   - Total system latency (signal → fill)

2. **Slippage Metrics**:
   - Expected price vs actual fill price
   - Slippage in basis points
   - Partial fills vs full fills
   - Market impact estimation

**Actions**:
- [ ] Create `src/trade_engine/core/metrics.py`
  ```python
  @dataclass
  class LatencyMetrics:
      api_latency_ms: float
      ws_latency_ms: float
      order_placement_latency_ms: float
      fill_latency_ms: float
      total_latency_ms: float

  @dataclass
  class SlippageMetrics:
      expected_price: Decimal
      actual_price: Decimal
      slippage_bps: Decimal
      fill_ratio: Decimal  # filled / requested
  ```

- [ ] Add latency tracking to all broker adapters
- [ ] Add slippage calculation to order fill handlers
- [ ] Log metrics using TradingLogger
- [ ] Add P50, P95, P99 percentile tracking
- [ ] Set alerting thresholds:
  - Total latency > 100ms: WARNING
  - Total latency > 500ms: CRITICAL
  - Slippage > 10 bps: WARNING
  - Fill ratio < 90%: WARNING

- [ ] Create monitoring dashboard (Phase 4: React UI)

**Owner**: TBD
**Target**: Phase 1 (before paper trading)

---

## 🟢 Medium Priority (Phase 1-2)

### 7. Backtesting vs Live Code Separation
**Status**: ⚠️ Both exist but unclear boundaries

**Actions**:
- [ ] Document what code is backtest-only vs live-only
- [ ] Add runtime checks to prevent backtesting code in live mode
- [ ] Abstract fills: `FillSimulator` (backtest) vs `RealFillHandler` (live)
- [ ] Add integration tests for both paths
- [ ] Document in `docs/architecture.md`

**Owner**: TBD
**Target**: Phase 1

---

### 8. API Contract Definition (FastAPI)
**Status**: Not started (Phase 3 feature)

**Actions**:
- [ ] Design REST API endpoints (OpenAPI spec)
  ```
  GET  /api/v1/engine/status
  POST /api/v1/engine/start
  POST /api/v1/engine/stop
  POST /api/v1/engine/kill
  GET  /api/v1/positions
  GET  /api/v1/orders
  GET  /api/v1/pnl
  GET  /api/v1/metrics
  ```
- [ ] Design WebSocket streaming API
- [ ] Create OpenAPI schema (`docs/api/openapi.yaml`)
- [ ] Generate client SDKs (Python, TypeScript)

**Owner**: TBD
**Target**: Phase 2 (before Phase 3 implementation)

---

### 9. Data Retention & Archival Policy
**Status**: Not defined

**Decisions Needed**:
1. **Hot data** (actively queried):
   - Trades: Last 90 days
   - Positions: Last 90 days
   - Order book snapshots: Last 7 days

2. **Warm data** (archived, queryable):
   - Trades: 90 days - 2 years → S3 Parquet
   - Logs: 90 days - 1 year → S3 compressed

3. **Cold data** (compliance archive):
   - All trades: 7 years (regulatory requirement)
   - Stored in S3 Glacier

**Actions**:
- [ ] Document retention policy in `docs/data-retention.md`
- [ ] Implement log rotation (already done via loguru)
- [ ] Add DB archival scripts (Phase 2)
- [ ] Set up S3 lifecycle policies (Phase 3)

**Owner**: TBD
**Target**: Phase 2

---

### 10. Versioning & Releases
**Status**: No releases yet

**Actions**:
- [ ] Add semantic versioning (MAJOR.MINOR.PATCH)
- [ ] Tag Phase 0 as v0.1.0
- [ ] Update CHANGELOG.md for each release
- [ ] Create release notes template
- [ ] Automate releases via GitHub Actions (on tag push)
- [ ] Generate Docker image tags from version

**Owner**: TBD
**Target**: Phase 0 completion

---

## 📚 Documentation Improvements

### 11. Architecture Documentation
**Status**: README has overview, needs depth

**Actions**:
- [ ] Create `docs/architecture.md` with:
  - System overview diagram
  - Data flow diagrams
  - Sequence diagrams for key flows:
    - Order placement flow
    - Fill handling flow
    - Risk check flow
    - Kill switch flow
- [ ] Add UML class diagrams for core components
- [ ] Document design decisions (ADRs - Architecture Decision Records)

**Owner**: TBD
**Target**: Phase 1

---

### 12. API Documentation
**Status**: No generated docs

**Actions**:
- [ ] Set up Sphinx for Python API docs
- [ ] Generate docs from docstrings
- [ ] Host docs on GitHub Pages or Read the Docs
- [ ] Add "Contributing" guide

**Owner**: TBD
**Target**: Phase 1

---

## 🎯 Success Metrics

### Phase 0 Completion Criteria
- ✅ All CRITICAL items complete (3/3 done)
- [ ] All HIGH priority items complete or planned (0/4 done)
- ✅ Test coverage ≥ 80% (risk management = 100%) - **806 tests passing**
- ✅ CI/CD passing on all PRs
- ✅ No float usage in **critical trading path** (core, brokers, L2 strategy)
- ✅ Secrets never in logs/commits (CI enforced)
- ✅ Risk limits enforced in code + tested (100% coverage)

### Phase 1 Completion Criteria
- [ ] Database schema designed
- [ ] Adapter interfaces documented
- [ ] Latency/slippage monitoring operational
- [ ] All documentation up to date
- [ ] First release tagged (v0.2.0)

---

## 📋 Next Actions

**Status Update (2025-10-30)**:
- ✅ All CRITICAL priorities completed (PR #23)
- ✅ Infrastructure ready for Phase 1 paper trading
- **Next focus**: HIGH priority items (database schema, adapter docs, monitoring)

**Immediate (This Week)**:
1. ✅ ~~Audit codebase for float usage~~ - DONE
2. ✅ ~~Create `risk_rules.py` with hard limits~~ - DONE
3. ✅ ~~Add CI checks for float/secrets~~ - DONE
4. **NEW**: Document adapter interfaces (Item #5)
5. **NEW**: Create `docs/security.md` for secrets policy

**Short-term (Next 2 Weeks)**:
1. Design Postgres schema (Item #4)
2. Implement latency tracking (Item #6)
3. Add slippage monitoring (Item #6)
4. Create architecture diagrams (Item #11)

**Medium-term (Phase 0→1 Transition)**:
1. Complete all documentation
2. Tag Phase 0 release (v0.1.0)
3. Begin Phase 1 implementation (paper trading)

---

## 🔧 Technical Debt & Future Optimizations

### 13. Float Usage Cleanup (Non-Critical Paths)
**Status**: Tracked, not blocking
**Priority**: Low

**Known float usage outside critical path**:
1. **Services layer**:
   - `signal_normalizer.py` - Statistical calculations (z-scores, percentiles)
   - `aggregator.py` - Data aggregation metrics
   - `backtest/metrics.py` - Sharpe ratio, Sortino ratio
   - *Decision*: Keep as float (performance + stdlib compatibility)
   - *Revisit*: If precision issues arise in Phase 2 backtesting

2. **Alpha strategies**:
   - `alpha_macd.py` - EMA calculations
   - `alpha_rsi_divergence.py` - RSI calculations
   - `alpha_bollinger.py` - Standard deviation
   - *Decision*: Keep as float (not in live execution path)
   - *Revisit*: If used in live signal generation

3. **Data types**:
   - `types_microstructure.py` - Order book imbalance calculations
   - `types.py` - OHLCV data from external sources
   - *Decision*: Accept float from external APIs, convert at boundary
   - *Revisit*: Phase 2 if data quality issues

**Tracking**:
- Documented in this section for future reference
- Will review during Phase 2 (backtesting validation)
- May add pre-commit hook if issues arise

### 14. Pre-commit Hooks
**Status**: Not implemented
**Priority**: Low (nice-to-have)

**Actions**:
- [ ] Add hook to detect float in critical paths
- [ ] Add hook to prevent `.env` commits
- [ ] Add hook to run tests before commit
- [ ] Document hook installation in README

**Owner**: TBD
**Target**: Phase 1 (developer experience improvement)

---

## 📞 Questions & Decisions Needed

1. **Database**: PostgreSQL + TimescaleDB or just PostgreSQL?
2. **Retention**: How long to keep raw order book data?
3. **Monitoring**: Which metrics dashboard tool? (Grafana? Custom React?)
4. **Secrets**: AWS Secrets Manager or HashiCorp Vault?
5. **Release cadence**: Weekly? Per-phase? Feature-based?

---

**Last Updated**: 2025-10-30
**Next Review**: Weekly (every Monday)

**Recent Updates**:
- **2025-10-30**: ✅ Completed all 3 CRITICAL priorities (PR #23)
  - Float-to-Decimal migration for critical trading path
  - Risk management rules as code with 100% test coverage
  - Secrets management CI enforcement
  - Enhanced quality gates with 8-pattern float detection
