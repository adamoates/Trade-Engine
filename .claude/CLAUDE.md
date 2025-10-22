# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MFT Bot** is a Medium-Frequency Trading system for cryptocurrency futures using Level 2 order book imbalance detection. The strategy identifies supply/demand imbalances in the order book to predict short-term price movements (5-60 second hold times).

**Core Strategy**: L2 Order Book Imbalance Scalping
- Buy signal: Bid/Ask volume ratio > 3.0x (strong buying pressure)
- Sell signal: Bid/Ask volume ratio < 0.33x (strong selling pressure)
- Target: $50-100/day profit on $10K capital
- Expected win rate: 52-58% (based on academic research)

**Project Timeline**: 24 weeks (6 months) from foundation to production trading

## Three-Layer Architecture

The system uses a separation of concerns across three distinct layers:

### Layer 1: Execution Layer (Trading Engine)
Core autonomous trading engine that processes real-time L2 data and executes trades.

**Components**:
- **WebSocket Manager**: Binance L2 depth stream connection with auto-reconnect
- **Order Book Processor**: Real-time bid/ask state maintenance (sortedcontainers)
- **Signal Generator**: Imbalance ratio calculation and threshold checking
- **Risk Manager**: Position size, daily loss, drawdown enforcement
- **Order Executor**: Smart order placement with retry logic
- **State Manager**: Position tracking, P&L calculation, metrics

**Performance Targets**:
- Message processing: <5ms
- Order placement: <20ms
- Total latency: <50ms sustained

### Layer 2: Orchestration Layer (API Server)
FastAPI server that controls the engine and serves monitoring data.

**Endpoints**:
- Engine control: `/engine/start`, `/engine/stop`, `/engine/kill`
- Data retrieval: `/engine/status`, `/engine/position`, `/engine/orders`
- Real-time streaming: `/engine/stream` (WebSocket)

### Layer 3: Presentation Layer (UI)
React dashboard for pre-trade analysis and live monitoring.

**Interfaces**:
- **Scanner UI** (Phase 1): Pre-trade instrument analysis and selection
- **Bot Control UI** (Phase 4): Live monitoring, P&L tracking, kill switch

## Python Environment

- **Python Version**: 3.11+
- **Package Management**: Will be established (poetry recommended)
- **Virtual Environment**: Required for development
- **Type Hints**: Mandatory for all functions and methods

## Code Standards

### Style Guidelines
- **Formatter**: Black (line length 88)
- **Import Sorter**: isort (profile: black)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode recommended)

### Code Organization
- All source code in `src/` directory
- All tests in `tests/` directory mirroring src structure
- Documentation in `docs/` directory
- Configuration files at project root

### Naming Conventions
- Classes: PascalCase (e.g., `TradingStrategy`, `MarketData`)
- Functions/methods: snake_case (e.g., `execute_trade`, `calculate_returns`)
- Constants: UPPER_SNAKE_CASE (e.g., `MAX_POSITION_SIZE`)
- Private methods: prefix with underscore (e.g., `_validate_order`)

## Critical Rules

### Trading System Safety (NON-NEGOTIABLE)
- **NEVER use `float` for money/price calculations** - Python floats cause rounding errors in financial calculations
- **Use Decimal** for all prices, quantities, and P&L calculations
- **All trades MUST be logged** to database for audit trail and reconciliation
- **API keys NEVER in code** - use environment variables (.env file, gitignored)
- **Risk limits enforced in code** - no exceptions, no overrides without kill switch
- **Kill switch must be tested** - verify it flattens positions and stops trading

### Hard Risk Limits (Enforced by RiskManager)
- **Max Position Size**: $10,000 per trade
- **Daily Loss Limit**: -$500 (triggers kill switch)
- **Max Drawdown**: -$1,000 from peak equity (triggers kill switch)
- **Per-Instrument Exposure**: 25% of total capital max
- **Position Hold Time**: 60 seconds max (time stop)

### Strategy Parameters (Tunable During Paper Trading)
- **Imbalance Depth**: 5 levels (top 5 bids/asks)
- **Buy Threshold**: 3.0x bid/ask ratio
- **Sell Threshold**: 0.33x bid/ask ratio
- **Profit Target**: 0.2% (20 basis points)
- **Stop Loss**: -0.15% (15 basis points)

### Development Workflow
1. Create feature branch from main
2. Implement with comprehensive error handling (trading systems MUST handle failures gracefully)
3. Write tests for ALL risk-critical code (position sizing, P&L calculation, kill switch)
4. Run full test suite before commit
5. Update CLAUDE.md if adding new patterns or architectural decisions
6. Use descriptive commit messages explaining WHY, not just WHAT

## Testing Requirements

### Testing Framework
- **Primary**: pytest
- **Coverage**: pytest-cov
- **Mocking**: pytest-mock or unittest.mock

### Test Organization
- Unit tests for all public functions
- Integration tests for component interactions
- Use fixtures for test data and setup
- Parametrize tests for multiple scenarios
- Mock external APIs and market data sources

### Test Naming
- Pattern: `test_<function>_<scenario>_<expected_result>`
- Example: `test_calculate_returns_with_negative_pnl_returns_loss`

### Coverage Requirements
- Minimum 80% coverage for trading logic
- 100% coverage for risk management code
- Critical paths must have comprehensive tests

## Custom Commands

Use these slash commands for common workflows:

- `/project:setup` - Set up development environment
- `/project:test` - Run full test suite with coverage
- `/project:lint` - Run linting and formatting checks

## Specialized Agents

Invoke these agents for specific tasks:

- `code-reviewer` - Thorough code review for quality, security, and performance
- `test-generator` - Generate comprehensive test suites
- `performance-optimizer` - Analyze and optimize performance bottlenecks

## Documentation

Maintain up-to-date documentation in `/docs`:
- `architecture.md` - System design and component relationships
- `trading-strategies.md` - Strategy implementations and patterns
- `data-sources.md` - Market data providers and APIs
- `deployment.md` - Production deployment procedures

Reference detailed documentation using `@docs/filename.md` syntax.

## CI/CD Pipeline

The project uses GitHub Actions for automated quality gates and deployment.

### Phase 1: Continuous Integration (CI)
**File**: `.github/workflows/ci-quality-gate.yml`

**Triggers**: Every push and pull request

**What it checks**:
- Code formatting (Black)
- Linting (Ruff)
- Unit and integration tests (pytest with PostgreSQL)
- Test coverage (80% minimum)
- Float usage in financial code (must use Decimal)
- Risk limit definitions
- Kill switch implementation
- Security scanning (dependencies, secrets)

**Result**: Code CANNOT be merged to main unless all checks pass

### Phase 2: Continuous Deployment (CD)
**File**: `.github/workflows/cd-deploy.yml`

**Triggers**: Merge to main branch

**What it does**:
1. Re-verifies all quality checks
2. Builds production Docker images
3. Deploys to staging automatically
4. Waits for manual approval
5. Deploys to production after approval

**Manual Approval Required**: Production deployment requires explicit approval from project lead

See `docs/deployment.md` for complete CI/CD documentation.

## Development Setup

### Initial Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # if using setuptools
```

### Running Tests Locally
```bash
# All tests with coverage (same as CI)
pytest --cov=engine --cov=api --cov-report=term-missing -v

# Specific test file
pytest tests/test_risk_manager.py

# Specific test function
pytest tests/test_risk_manager.py::test_kill_switch_triggers

# Run with PostgreSQL container (for integration tests)
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/
docker-compose -f docker-compose.test.yml down
```

### Code Quality (Run Before Pushing)
```bash
# Format code
black engine/ api/ scanner/ tests/

# Sort imports
isort engine/ api/ scanner/ tests/

# Lint
ruff check engine/ api/ scanner/ tests/

# Type check
mypy engine/ api/

# Run all quality checks at once
black --check engine/ api/ tests/ && \
ruff check engine/ api/ tests/ && \
pytest --cov=engine --cov=api -v
```

### Local CI Simulation
Before pushing, you can run the same checks that GitHub Actions will run:

```bash
# Simulate CI checks locally
./scripts/run-ci-checks.sh  # (create this script based on ci-quality-gate.yml)
```

## Common Patterns

### Order Book Maintenance Pattern
```python
class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, float] = {}  # {price: quantity}
        self.asks: Dict[float, float] = {}  # {price: quantity}
        self.last_update_time = time.time()

    async def handle_snapshot(self, data: dict):
        """Initialize with full snapshot from exchange."""
        self.bids = {float(p): float(q) for p, q in data['bids']}
        self.asks = {float(p): float(q) for p, q in data['asks']}

    async def handle_update(self, data: dict):
        """Apply incremental delta updates."""
        for price, quantity in data['b']:
            price, quantity = float(price), float(quantity)
            if quantity == 0:
                self.bids.pop(price, None)  # Remove level
            else:
                self.bids[price] = quantity  # Update level
```

### Imbalance Calculation Pattern
```python
def calculate_imbalance(order_book: OrderBook, depth: int = 5) -> float:
    """Calculate bid/ask volume ratio from top N levels."""
    top_bids = sorted(order_book.bids.items(), reverse=True)[:depth]
    top_asks = sorted(order_book.asks.items())[:depth]

    bid_volume = sum(qty for price, qty in top_bids)
    ask_volume = sum(qty for price, qty in top_asks)

    if ask_volume == 0:
        return float('inf') if bid_volume > 0 else 1.0

    return bid_volume / ask_volume
```

### Risk Validation Pattern
```python
class RiskManager:
    def can_trade(self, signal: Signal, current_position: Position) -> bool:
        """Validate ALL risk limits before allowing entry."""
        # Check daily loss limit
        if self.get_daily_pnl() < -MAX_DAILY_LOSS:
            self.trigger_kill_switch("Daily loss limit breached")
            return False

        # Check max drawdown
        drawdown = self.peak_equity - self.get_current_equity()
        if drawdown > MAX_DRAWDOWN:
            self.trigger_kill_switch("Max drawdown breached")
            return False

        # Check position size
        if signal.position_value > MAX_POSITION_SIZE:
            logger.warning("Position size exceeds limit")
            return False

        return True
```

### Error Handling Pattern
Use specific exceptions with context:

```python
class TradingError(Exception):
    """Base exception for all trading errors."""
    pass

class RiskLimitBreached(TradingError):
    """Raised when any risk limit is exceeded."""
    pass

class OrderRejected(TradingError):
    """Raised when exchange rejects order."""
    pass

class DataStale(TradingError):
    """Raised when order book data is too old."""
    pass
```

### Logging Pattern
Log EVERYTHING for audit trail and debugging:

```python
import logging
import structlog

logger = structlog.get_logger()

# Log every trade decision
logger.info(
    "signal_generated",
    symbol="BTCUSDT",
    imbalance_ratio=3.5,
    side="BUY",
    strength=0.8,
    timestamp=time.time()
)

# Log every order placement
logger.info(
    "order_placed",
    symbol="BTCUSDT",
    side="BUY",
    size=Decimal("0.1"),
    order_id="12345",
    timestamp=time.time()
)

# Log every risk check
logger.warning(
    "risk_limit_approached",
    daily_pnl=Decimal("-450"),
    limit=Decimal("-500"),
    remaining=Decimal("50")
)
```

## Prohibited Actions

- **NEVER commit sensitive information** - API keys, secrets, .env files are gitignored
- **NEVER use `float` for financial calculations** - use Decimal exclusively
- **NEVER execute live trades without paper trading validation** - 60 days minimum
- **NEVER bypass risk limits** - even if signal looks good, respect the limits
- **NEVER modify CLAUDE.md or ROADMAP.md without explicit user request** - these are protected
- **NEVER skip the kill switch test** - it must be verified to work before live trading
- **NEVER proceed past Phase 6 gate without meeting criteria** - paper trading win rate >50% required

## Phase Gate Requirements

The project uses a strict phase-gate methodology. You CANNOT proceed to the next phase without meeting ALL criteria:

### Gate 0→1: Infrastructure Ready
- [ ] VPS latency <50ms to Binance
- [ ] 24h of L2 data recorded successfully
- [ ] WebSocket connection stable

### Gate 1→2: Instruments Selected
- [ ] Screener identifies 3+ viable instruments
- [ ] Primary trading pair decided (likely BTC/USDT)

### Gate 2→3: Engine Functional
- [ ] Engine runs 24h without crashes
- [ ] Risk limits enforced correctly
- [ ] Signal generation validated manually

### Gate 3→4: API Server Working
- [ ] Kill switch tested and functional
- [ ] Can control engine via API
- [ ] Database persistence working

### Gate 4→5: UI Complete
- [ ] Real-time data displayed accurately
- [ ] All controls functional

### Gate 5→6: Paper Trading Validated ⚠️ CRITICAL
- [ ] 60 days of paper trading completed
- [ ] Win rate >50%
- [ ] Profit factor >1.0
- [ ] Confidence that edge exists
**DO NOT proceed to live trading without meeting these criteria**

### Gate 6→7: Micro-Capital Tested
- [ ] 30 days with $100-500 real capital
- [ ] Break-even or positive
- [ ] No critical bugs discovered

## Progress Tracking

See ROADMAP.md for detailed project phases, features, and current progress.

Current implementation should track:
- Which phase you're in
- Current week (of 24)
- Next milestone target
- Any blockers

## Documentation References

Detailed project documentation is available in /Users/adamoates/Documents/trader/:
- `mft-architecture.md` - Complete system design and component specifications
- `mft-strategy-spec.md` - L2 imbalance strategy logic and parameters
- `mft-risk-management.md` - All risk limits and kill switch procedures
- `mft-roadmap.md` - Phase-by-phase development plan
- `mft-research-questions.md` - Validation questions for strategy research
- `mft-dev-log.md` - Template for tracking daily/weekly progress

Reference these documents when implementing specific components.
