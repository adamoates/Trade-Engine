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
**Status**: ⚠️ Policy documented, enforcement incomplete
**Why Critical**: Float rounding errors can cause financial losses

**Actions**:
- [ ] Add pre-commit hook to detect `float` in financial calculations
- [ ] Audit existing code for float usage in prices/quantities/PnL
- [ ] Add linter rule (ruff/pylint) to flag float in domain/services
- [ ] Add CI check: grep for dangerous patterns
  ```bash
  # Patterns to detect:
  - float(price)
  - float(qty)
  - price: float
  - amount: float (in financial contexts)
  ```
- [ ] Document exceptions (e.g., ratios, percentages OK as float)

**Owner**: TBD
**Target**: Phase 0 (before any live trading)

---

### 2. Secrets Management 🔒
**Status**: ⚠️ `.env.example` exists, but no validation

**Actions**:
- [ ] Add pre-commit hook to prevent `.env` commits
- [ ] Verify API keys never appear in logs (audit logging_config.py)
- [ ] Add secret detection to CI (GitHub secret scanning, gitleaks)
- [ ] Document secrets policy in `docs/security.md`
- [ ] Plan for production: AWS Secrets Manager or Vault (Phase 3+)

**Owner**: TBD
**Target**: Phase 0 (immediate)

---

### 3. Risk Management Rules as Code 📋
**Status**: ⚠️ Rules documented in CLAUDE.md, not enforced in code

**Current Rules** (from CLAUDE.md):
- Max Position Size: $10,000
- Daily Loss Limit: -$500 (triggers kill switch)
- Max Drawdown: -$1,000 from peak equity
- Per-Instrument Exposure: 25% of capital
- Position Hold Time: 60 seconds max

**Actions**:
- [ ] Create `src/trade_engine/core/risk_rules.py` with RiskRule dataclass
- [ ] Move hard limits from comments to constants
  ```python
  @dataclass(frozen=True)
  class RiskLimits:
      MAX_POSITION_SIZE_USD: Decimal = Decimal("10000")
      DAILY_LOSS_LIMIT_USD: Decimal = Decimal("-500")
      MAX_DRAWDOWN_USD: Decimal = Decimal("-1000")
      MAX_INSTRUMENT_EXPOSURE_PCT: Decimal = Decimal("0.25")
      MAX_HOLD_TIME_SECONDS: int = 60
  ```
- [ ] Add tests for each limit (100% coverage required)
- [ ] Document each rule: why it exists, how to tune
- [ ] Add CI check to verify risk rules are tested

**Owner**: TBD
**Target**: Phase 0 (before paper trading)

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
**Status**: Base classes exist, no formal spec

**Current State**:
- `BrokerAdapter` base class exists
- `FeedAdapter` base class exists
- 4 broker implementations (Binance, Binance.us, Kraken, mock)
- 2 feed implementations (BinanceFuturesL2, BinanceUSL2)

**Actions**:
- [ ] Document adapter contracts in `docs/adapters/`
  - `broker-interface.md`: Required methods, error handling, retry logic
  - `feed-interface.md`: Required methods, reconnect logic, rate limits
  - `data-source-interface.md`: For Web3, fundamentals, etc.

- [ ] Add type hints and docstrings to all base classes
- [ ] Create adapter integration test template
  ```python
  # tests/integration/adapters/test_broker_adapter.py
  @pytest.mark.parametrize("broker_class", [BinanceBroker, KrakenBroker, ...])
  def test_broker_adapter_contract(broker_class):
      """Verify all brokers implement required interface."""
      broker = broker_class()
      assert hasattr(broker, 'buy')
      assert hasattr(broker, 'sell')
      # ... test all required methods
  ```

- [ ] Add adapter health check methods (latency, rate limit status)
- [ ] Document how to add new adapters (template + checklist)

**Owner**: TBD
**Target**: Phase 1

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
- [ ] All CRITICAL items complete
- [ ] All HIGH priority items complete or planned
- [ ] Test coverage ≥ 80% (risk management = 100%)
- [ ] CI/CD passing on all PRs
- [ ] No float usage in financial code
- [ ] Secrets never in logs/commits
- [ ] Risk limits enforced in code + tested

### Phase 1 Completion Criteria
- [ ] Database schema designed
- [ ] Adapter interfaces documented
- [ ] Latency/slippage monitoring operational
- [ ] All documentation up to date
- [ ] First release tagged (v0.2.0)

---

## 📋 Next Actions

**Immediate (This Week)**:
1. Audit codebase for float usage in financial calculations
2. Add pre-commit hook for secret detection
3. Create `risk_rules.py` with hard limits
4. Document adapter interfaces

**Short-term (Next 2 Weeks)**:
1. Design Postgres schema
2. Implement latency tracking
3. Add slippage monitoring
4. Create architecture diagrams

**Medium-term (Phase 0→1 Transition)**:
1. Complete all documentation
2. Tag Phase 0 release (v0.1.0)
3. Begin Phase 1 implementation

---

## 📞 Questions & Decisions Needed

1. **Database**: PostgreSQL + TimescaleDB or just PostgreSQL?
2. **Retention**: How long to keep raw order book data?
3. **Monitoring**: Which metrics dashboard tool? (Grafana? Custom React?)
4. **Secrets**: AWS Secrets Manager or HashiCorp Vault?
5. **Release cadence**: Weekly? Per-phase? Feature-based?

---

**Last Updated**: 2025-10-29
**Next Review**: Weekly (every Monday)
