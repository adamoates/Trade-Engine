# MFT Bot Development Roadmap

## Progress Convention
- `[ ]` = Todo
- `[-]` = In Progress 🏗️ YYYY/MM/DD
- `[x]` = Completed ✅ YYYY/MM/DD

---

## Project Overview

**Goal**: Build a profitable medium-frequency trading bot for crypto futures using Level 2 order book imbalance detection

**Strategy**: L2 Order Book Imbalance Scalping
- Buy when bid volume / ask volume > 3.0x
- Sell when bid volume / ask volume < 0.33x
- Hold time: 5-60 seconds
- Profit target: 0.2%, Stop loss: -0.15%

**Target Performance**: $50-100/day profit on $10K capital
**Timeline**: 24 weeks (6 months) from start to production
**Classification**: Medium-Frequency Trading (MFT)

---

## Phase 0: Foundation & Infrastructure Setup

**Duration**: Weeks 1-2
**Goal**: Set up development environment and validate exchange connectivity

### Key Deliverables
- [ ] VPS provisioned (Ubuntu 22.04, 2-4 CPU cores, 4-8GB RAM)
- [ ] Low-latency connection verified (<50ms to Binance)
- [ ] Binance testnet account created with API keys
- [ ] Python 3.11+ environment configured
- [ ] Core libraries installed (asyncio, websockets, uvloop, ccxt)
- [ ] Basic L2 data recording script functional
- [ ] 24 hours of L2 data successfully recorded

### Success Criteria
✅ VPS accessible via SSH
✅ Latency consistently <50ms to Binance
✅ Can connect to Binance WebSocket feed
✅ L2 data recording runs without crashes for 24h
✅ Recorded data is parseable and valid

### Phase Gate: 0→1
- [ ] VPS latency <50ms to target exchange
- [ ] 24h of clean L2 data recorded
- [ ] Exchange API authentication working

---

## Phase 1: Instrument Screener Development

**Duration**: Weeks 3-4
**Goal**: Build tool to identify optimal trading instruments

### Key Deliverables
- [ ] Python screener script that fetches all available pairs
- [ ] Volume filter implemented (>$10M 24h volume)
- [ ] Spread filter implemented (<0.1% bid-ask spread)
- [ ] Historical imbalance frequency calculator
- [ ] Ranked output showing top 5-10 candidates
- [ ] React Scanner UI prototype (displays results)

### Success Criteria
✅ Screener analyzes 100+ crypto pairs in <5 minutes
✅ Identifies 3-5 viable instruments meeting all criteria
✅ UI displays sortable results with key metrics
✅ Can export selected instruments to JSON config

### Phase Gate: 1→2
- [ ] Screener identifies 3+ viable instruments
- [ ] Selected instruments meet all criteria
- [ ] Decision made on primary trading pair (BTC/USDT)

---

## Phase 2: Core Trading Engine Development

**Duration**: Weeks 5-10 ⚠️ **CRITICAL PHASE**
**Goal**: Build the autonomous trading engine

### 2.1: Order Book Processor (Weeks 5-6)
- [ ] WebSocket connection handler with auto-reconnect
- [ ] Order book state maintenance (bids/asks dictionaries)
- [ ] L2 update processing (handle snapshots + deltas)
- [ ] Performance: Handle 1,000+ messages/second
- [ ] Latency monitoring (log processing time per message)

### 2.2: Signal Generator (Week 7)
- [ ] Imbalance ratio calculator (top 5 levels)
- [ ] Threshold logic (>3.0x = BUY signal, <0.33x = SELL)
- [ ] Signal validation (check data freshness, completeness)
- [ ] Historical signal tracking (for later analysis)

### 2.3: Risk Manager (Week 8)
- [ ] Position size validator (max $10,000)
- [ ] Daily loss tracker and limit enforcer (-$500 max)
- [ ] Max drawdown calculator and circuit breaker (-$1,000)
- [ ] Per-instrument exposure limiter (25% max)
- [ ] Order size sanity checks (prevent fat fingers)

### 2.4: Order Executor (Week 9)
- [ ] Smart order placement (limit vs. market logic)
- [ ] Retry mechanism (network failures, rejections)
- [ ] Fill confirmation and position tracking
- [ ] Slippage calculator and logger
- [ ] Rate limit handling (exponential backoff)

### 2.5: Main Engine Integration (Week 10)
- [ ] Async event loop connecting all components
- [ ] Graceful shutdown handler
- [ ] State persistence (positions, P&L to database)
- [ ] Comprehensive logging (every decision, order, error)
- [ ] Health metrics collection (latency, errors, uptime)

### Success Criteria
✅ Engine runs 24 hours without crashing (testnet)
✅ Processes L2 updates with <10ms average latency
✅ Correctly calculates imbalance ratios (verified manually)
✅ Respects all risk limits (tested with simulated breaches)
✅ Places orders successfully 99%+ of the time
✅ Recovers from WebSocket disconnections automatically

### Phase Gate: 2→3
- [ ] Engine runs 24h without crashes
- [ ] All risk limits enforced correctly
- [ ] Signal generation validated manually

---

## Phase 3: API Server & Integration

**Duration**: Weeks 11-12
**Goal**: Build FastAPI server to control engine and serve data

### Key Deliverables
- [ ] FastAPI application structure
- [ ] RESTful endpoints (start, stop, status, position, orders)
- [ ] WebSocket endpoint for real-time metrics streaming
- [ ] Authentication/authorization (API key-based)
- [ ] CORS configuration for frontend access
- [ ] PostgreSQL database integration
- [ ] Logging and monitoring hooks

### API Endpoints to Implement
```
POST   /engine/start      - Start trading with config
POST   /engine/stop       - Graceful shutdown
POST   /engine/pause      - Pause trading (keep connections)
POST   /engine/resume     - Resume trading
POST   /engine/kill       - Emergency stop (flatten positions)

GET    /engine/status     - Is engine running? Current symbol?
GET    /engine/position   - Current holdings, unrealized P&L
GET    /engine/orders     - Recent orders (last 100)
GET    /engine/stats      - Performance statistics
GET    /engine/health     - Latency, errors, last heartbeat

WS     /engine/stream     - Real-time P&L, position updates
```

### Success Criteria
✅ API server responds to all endpoints <100ms
✅ WebSocket streams data without disconnects
✅ Engine can be started/stopped via API
✅ Kill switch flattens positions within 5 seconds
✅ API handles 100 concurrent requests without issues

### Phase Gate: 3→4
- [ ] API server functional
- [ ] Kill switch tested and working
- [ ] Database persistence functional

---

## Phase 4: Bot Control UI Development

**Duration**: Weeks 13-14
**Goal**: Build React dashboard for monitoring and control

### 4.1: Engine Controls
- [ ] Start/Stop/Pause button interface
- [ ] Configuration form (symbol, leverage, thresholds)
- [ ] Kill switch (prominent, red, confirmed action)
- [ ] Connection status indicator

### 4.2: Monitoring Dashboards
- [ ] Real-time P&L chart (last 6 hours)
- [ ] Current position display
- [ ] Recent orders table (last 50)
- [ ] Risk metrics gauges (daily loss, drawdown, exposure)
- [ ] Health indicators (latency, errors, uptime)

### 4.3: Analytics Views
- [ ] Performance statistics (win rate, profit factor)
- [ ] Historical trades table (filterable, sortable)
- [ ] Trade distribution charts
- [ ] Imbalance signal frequency analysis

### Success Criteria
✅ UI connects to API server via WebSocket
✅ Real-time data updates <1 second delay
✅ All controls functional (can start/stop engine)
✅ Kill switch works instantly
✅ Responsive design (works on desktop + tablet)

### Phase Gate: 4→5
- [ ] UI connects and displays real-time data
- [ ] All controls functional
- [ ] Monitoring dashboards accurate

---

## Phase 5: Paper Trading Validation

**Duration**: Weeks 15-18 ⚠️ **CRITICAL VALIDATION PHASE**
**Goal**: Prove the strategy works with live data, zero risk

### Deliverables
- [ ] Engine runs on live L2 data (not testnet)
- [ ] Simulated order execution (no real trades)
- [ ] 60 days of continuous paper trading
- [ ] Daily performance reports
- [ ] Strategy parameter tuning based on results

### What to Measure
- **Win Rate**: Target 55%+, acceptable 50%+
- **Profit Factor**: Gross wins / gross losses, target >1.2
- **Average Win/Loss**: Target 1:1 ratio or better
- **Sharpe Ratio**: Risk-adjusted returns, target >1.0
- **Max Drawdown**: Should stay under risk limits
- **Trade Frequency**: Are you getting enough opportunities?

### Success Criteria (Hard Requirements)
✅ Win rate >50% over 60 days
✅ Profit factor >1.0 (after simulated fees)
✅ System uptime >99% (minimal crashes)
✅ Daily theoretical P&L positive 60%+ of days
✅ No violation of risk limits in simulation

### Failure Criteria (Must Restart or Pivot)
❌ Win rate <45% after 60 days
❌ Profit factor <0.8 consistently
❌ Strategy only works in specific market regimes
❌ Simulated profits don't cover real fees

### Phase Gate: 5→6 ⚠️ **CRITICAL GATE**
- [ ] 60 days of paper trading completed
- [ ] Win rate >50%
- [ ] Profit factor >1.0
- [ ] Confidence that edge exists

**If this gate fails, DO NOT proceed to live trading. Reassess strategy.**

---

## Phase 6: Micro-Capital Live Testing

**Duration**: Weeks 19-22
**Goal**: Validate with real money, minimal risk

### Approach
- **Starting Capital**: $100-500 (not $10,000 yet!)
- **Goal**: Break-even or small profit
- **Real Purpose**: Debug real-world execution issues

### What You'll Discover (The "Unknown Unknowns")
- Slippage is worse than paper trading suggested
- Order rejections happen more than expected
- Fee structure impacts thin margins significantly
- Exchange maintenance windows disrupt trading
- Network issues cause missed opportunities
- Position tracking has subtle bugs

### Deliverables
- [ ] Real exchange account with minimal funding
- [ ] Engine connected to live trading API
- [ ] 30 days of live trading with micro-capital
- [ ] Comparison report: Paper trading vs. Live
- [ ] Bug fixes for all issues discovered

### Success Criteria
✅ No catastrophic losses (capital protected by limits)
✅ Engine handles real execution successfully
✅ Break-even or positive P&L after 30 days
✅ Confidence in system stability and correctness

### Phase Gate: 6→7
- [ ] 30 days of live micro-capital testing
- [ ] Break-even or positive
- [ ] No critical bugs discovered
- [ ] System stable and reliable

---

## Phase 7: Production Scaling & Optimization

**Duration**: Week 23+
**Goal**: Scale to full capital and optimize

### If Phase 6 Succeeded, Now:
- [ ] Increase capital gradually ($500 → $1K → $5K → $10K)
- [ ] Add second instrument (diversification)
- [ ] Optimize latency hotspots (Python → Cython/Rust if needed)
- [ ] Add redundancy (backup WebSocket connections)
- [ ] Implement alerting (Discord/Telegram/Email)
- [ ] Add advanced monitoring (Prometheus/Grafana)

### Capital Scaling Strategy
```
Week 23-24: $500   → Target $5-10/day
Week 25-26: $1,000 → Target $10-20/day
Week 27-28: $2,500 → Target $25-40/day
Week 29-30: $5,000 → Target $40-70/day
Week 31+:   $10,000 → Target $50-100/day
```

### Success Criteria (Final)
✅ $50-100/day profit consistently on $10K capital
✅ Sharpe ratio >1.5 over 90 days
✅ Max drawdown stays <10% of capital
✅ System uptime >99.5%
✅ Can run for weeks without manual intervention

---

## Technical Debt Tracking

### Code Quality
- [ ] Refactor legacy code sections as patterns emerge
- [ ] Improve test coverage in weak areas
- [ ] Update dependencies quarterly
- [ ] Standardize error handling across all components

### Documentation
- [ ] Keep CLAUDE.md updated with new patterns
- [ ] Document all architectural decisions
- [ ] Maintain dev log with weekly updates
- [ ] Create runbooks for operational procedures

### Infrastructure
- [ ] Optimize database queries
- [ ] Enhance monitoring coverage
- [ ] Implement automated backups
- [ ] Set up disaster recovery procedures

---

## Current Status

**Update this section as you progress:**

### Current Phase
Phase: [e.g., Phase 0 - Infrastructure Setup]

### Current Week
Week: [e.g., Week 1 of 24]

### Last Completed Milestone
Date: [YYYY/MM/DD]
Milestone: [Description]

### Next Milestone
Target Date: [YYYY/MM/DD]
Milestone: [Description]

### Blockers
- [List any current blockers]

### Key Decisions Made
- [Decision 1: e.g., "Chose Binance over Bybit"]
- [Decision 2: e.g., "Using BTC/USDT as primary pair"]

---

## Budget Summary

| Phase | Duration | Estimated Cost | Purpose |
|-------|----------|----------------|---------|
| Phase 0 | 2 weeks | $25 | VPS setup |
| Phase 1 | 2 weeks | $0 | Development only |
| Phase 2 | 6 weeks | $100 | VPS continued (6 weeks) |
| Phase 3 | 2 weeks | $35 | VPS + database |
| Phase 4 | 2 weeks | $10 | Hosting (optional) |
| Phase 5 | 4 weeks | $80 | VPS continued (4 weeks) |
| Phase 6 | 4 weeks | $500 | Learning capital |
| Phase 7 | Ongoing | Variable | Scaling capital |

**Total 6-month budget**: ~$750-1,500 (includes learning losses)

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025 | 1.0 | Initial roadmap based on MFT project plan |

---

**Remember**: This is a marathon, not a sprint. Each phase builds on the previous. Don't skip phases or rush through gates. The majority of retail trading bots fail because they skip validation (Phase 5-6) and go straight to live trading with capital they can't afford to lose.

**Your advantage**: Following this systematic, phase-gated approach.
