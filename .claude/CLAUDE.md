# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Trade Engine** (formerly MFT Bot) is a Medium-Frequency Trading system for cryptocurrency futures using Level 2 order book imbalance detection. The strategy identifies supply/demand imbalances in the order book to predict short-term price movements (5-60 second hold times).

**Core Strategy**: L2 Order Book Imbalance Scalping
- Buy signal: Bid/Ask volume ratio > 3.0x (strong buying pressure)
- Sell signal: Bid/Ask volume ratio < 0.33x (strong selling pressure)
- Target: $50-100/day profit on $10K capital
- Expected win rate: 52-58% (based on academic research)

**Project Timeline**: 24 weeks (6 months) from foundation to production trading

## Current Status

- **Current Phase**: Phase 2 (L2 Imbalance Strategy Implementation)
- **Architecture**: Clean Architecture with three-layer separation
- **Recent Milestone**: L2 order book imbalance strategy with multi-broker support
- **Next Gate**: Gate 2→3 (Engine runs 24h without crashes)

## Three-Layer Architecture

The system uses Clean Architecture principles with separation of concerns across three distinct layers:

### Layer 1: Domain Layer (Business Logic)
Core domain models, strategies, and business rules.

**Components**:
- **Domain Models**: Order, Position, Signal, Trade entities
- **Strategies**: L2ImbalanceStrategy and other trading strategies
- **Risk Rules**: Risk limit validation and enforcement logic

**Location**: `src/trade_engine/domain/`

### Layer 2: Application Layer (Use Cases)
Application services that orchestrate domain logic and infrastructure.

**Components**:
- **Trading Services**: Order execution, position management
- **Screening Services**: Instrument analysis and selection
- **Backtest Services**: Historical strategy validation
- **Audit Services**: Trade logging and compliance

**Location**: `src/trade_engine/services/`

### Layer 3: Infrastructure Layer (External Integrations)
Adapters for external systems and data sources.

**Components**:
- **Broker Adapters**: Kraken, Binance.us, etc.
- **Data Feed Adapters**: Real-time L2 order book feeds
- **Data Source Adapters**: Market data providers
- **API**: FastAPI server for engine control
- **Database**: PostgreSQL persistence layer

**Location**: `src/trade_engine/adapters/`, `src/trade_engine/api/`, `src/trade_engine/db/`

## Supported Brokers

The system supports multiple brokers to accommodate different regulatory jurisdictions:

- **Binance Futures** - Primary L2 data feed (full long/short functionality)
- **Kraken Futures** - US-accessible futures trading (recommended for US traders)
- **Binance.us** - US-only spot trading (long-only mode, no shorting)

**Note**: Spot-only mode automatically disables short signals for platforms without margin trading.

See broker adapter implementations in `src/trade_engine/adapters/brokers/`

## Python Environment

- **Python Version**: 3.11+ (tested on 3.11, 3.12, 3.13)
- **Package Management**: setuptools with pyproject.toml
- **Virtual Environment**: Required for development
- **Type Hints**: Mandatory for all functions and methods
- **Dependencies**: See `pyproject.toml` for full dependency list

## Code Standards

### Style Guidelines
- **Formatter**: Black (line length 88)
- **Import Sorter**: isort (profile: black)
- **Linter**: Ruff
- **Type Checker**: mypy (strict mode recommended)

### Code Organization
- All source code in `src/trade_engine/` directory
- All tests in `tests/` directory mirroring src structure
- Documentation in `docs/` directory
- Configuration files at project root

### Directory Structure
```
src/trade_engine/
├── domain/          # Business logic and domain models
│   ├── models/      # Core entities (Order, Position, Signal)
│   ├── strategies/  # Trading strategies (L2ImbalanceStrategy)
│   └── risk/        # Risk management rules
├── services/        # Application services
│   ├── trading/     # Order execution and position management
│   ├── screening/   # Instrument analysis
│   ├── backtest/    # Strategy backtesting
│   └── audit/       # Trade logging
├── adapters/        # External integrations
│   ├── brokers/     # Exchange adapters (Kraken, Binance)
│   ├── feeds/       # Real-time data feeds
│   └── data_sources/# Market data providers
├── api/             # FastAPI server
│   └── routes/      # API endpoints
├── db/              # Database models and migrations
├── core/            # Shared infrastructure (config, logging)
└── utils/           # Helper utilities
```

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
- **Coverage**: pytest-cov (configured in pyproject.toml)
- **Async Testing**: pytest-asyncio
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

- `/setup` - Set up development environment
- `/test` - Run full test suite with coverage
- `/lint` - Run linting and formatting checks

See `.claude/commands/` for command implementations.

## Specialized Agents

Invoke these agents for specific tasks:

- `code-reviewer` - Thorough code review for quality, security, and performance
- `test-generator` - Generate comprehensive test suites
- `performance-optimizer` - Analyze and optimize performance bottlenecks

## Documentation

Documentation is organized in `/docs`:
- `docs/architecture/` - System design and component specifications
- `docs/guides/` - Development guides and workflows
- `docs/reports/` - Audit reports and analysis
- `docs/deployment.md` - Production deployment procedures

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

## Model Context Protocol (MCP) Integration

The project can leverage MCP servers for enhanced development capabilities:

### Recommended MCP Servers

#### Essential (Implement First)
1. **PostgreSQL MCP** - Database operations and trade audit queries
   - Query trade history and performance metrics
   - Validate risk limit enforcement
   - Debug position tracking issues

2. **Slack/Discord MCP** - Critical alerts and monitoring
   - Kill switch triggers
   - Daily loss limit warnings
   - Position notifications
   - System health alerts

#### Phase 2 (Monitoring & Analysis)
3. **Redis MCP** - Real-time state management
   - Cache L2 snapshots
   - Pub/sub for engine ↔ API communication
   - Session state for WebSocket connections

4. **Time-Series DB MCP** (InfluxDB/TimescaleDB)
   - Store L2 order book snapshots
   - Performance metrics tracking
   - Backtesting data storage

#### Phase 3 (Production)
5. **Docker MCP** - Container management
   - Manage test containers
   - Inspect running services
   - Debug deployment issues

6. **Prometheus/Grafana MCP** - Observability
   - Real-time performance dashboards
   - System health monitoring
   - Latency tracking

7. **Cloud Storage MCP** (AWS S3)
   - Historical data archival
   - Trade log backups
   - Disaster recovery

### MCP Configuration
To configure MCP servers, add them to your Claude Code settings or use the appropriate MCP client configuration for your environment.

## Development Setup

### Initial Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Install optional dependencies
pip install -e ".[api,database]"
```

### Running Tests Locally
```bash
# All tests with coverage (same as CI)
pytest --cov=src/trade_engine --cov-report=term-missing -v

# Specific test file
pytest tests/unit/test_risk_manager.py

# Specific test function
pytest tests/unit/test_risk_manager.py::test_kill_switch_triggers

# Run with PostgreSQL container (for integration tests)
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/
docker-compose -f docker-compose.test.yml down

# Fast parallel execution
pytest -n auto  # Uses pytest-xdist
```

### Code Quality (Run Before Pushing)
```bash
# Format code
black src/trade_engine/ tests/

# Sort imports
isort src/trade_engine/ tests/

# Lint
ruff check src/trade_engine/ tests/

# Type check
mypy src/trade_engine/

# Run all quality checks at once
black --check src/ tests/ && \
isort --check-only src/ tests/ && \
ruff check src/ tests/ && \
pytest --cov=src/trade_engine -v
```

### Local CI Simulation
Before pushing, you can run the same checks that GitHub Actions will run:

```bash
# Simulate CI checks locally
./scripts/run-ci-checks.sh  # (if available)
# Or manually run the command chain above
```

## Common Patterns

### Financial Calculation Pattern (CRITICAL)
**ALWAYS use Decimal for money, prices, and quantities:**

```python
from decimal import Decimal, ROUND_HALF_UP

class Position:
    def __init__(self, symbol: str, size: str, entry_price: str):
        # ALWAYS use string input to Decimal for exact precision
        self.symbol = symbol
        self.size = Decimal(size)
        self.entry_price = Decimal(entry_price)

    def calculate_value(self) -> Decimal:
        """Calculate position value in quote currency."""
        value = self.size * self.entry_price
        # Quantize to appropriate precision
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_pnl(self, current_price: str) -> Decimal:
        """Calculate unrealized P&L."""
        current = Decimal(current_price)
        pnl = (current - self.entry_price) * self.size
        return pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# NEVER mix float with Decimal
# If you must convert from float (e.g., from API), do this:
price_from_api = 45234.5  # float from exchange
price = Decimal(str(price_from_api))  # Convert via string
```

### Order Book Maintenance Pattern
```python
from decimal import Decimal
from sortedcontainers import SortedDict
import time

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        # Use SortedDict for O(log n) operations
        self.bids: SortedDict[Decimal, Decimal] = SortedDict()
        self.asks: SortedDict[Decimal, Decimal] = SortedDict()
        self.last_update_time = time.time()

    async def handle_snapshot(self, data: dict):
        """Initialize with full snapshot from exchange."""
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

        self.last_update_time = time.time()

    async def handle_update(self, data: dict):
        """Apply incremental delta updates."""
        # Bid updates
        for price_str, qty_str in data.get('b', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            if qty == 0:
                self.bids.pop(price, None)  # Remove level
            else:
                self.bids[price] = qty  # Update level

        # Ask updates
        for price_str, qty_str in data.get('a', []):
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            if qty == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        self.last_update_time = time.time()

    def get_top_levels(self, depth: int = 5) -> tuple[list, list]:
        """Get top N levels from each side."""
        # Bids are sorted descending (highest first)
        top_bids = list(reversed(list(self.bids.items())[-depth:]))
        # Asks are sorted ascending (lowest first)
        top_asks = list(self.asks.items()[:depth])
        return top_bids, top_asks
```

### Imbalance Calculation Pattern
```python
from decimal import Decimal

def calculate_imbalance(order_book: OrderBook, depth: int = 5) -> Decimal:
    """Calculate bid/ask volume ratio from top N levels.

    Returns:
        Decimal ratio where:
        - > 1.0 indicates bid pressure (more buyers)
        - < 1.0 indicates ask pressure (more sellers)
        - = 1.0 indicates balance
    """
    top_bids, top_asks = order_book.get_top_levels(depth)

    # Sum volumes using Decimal arithmetic
    bid_volume = sum(qty for price, qty in top_bids)
    ask_volume = sum(qty for price, qty in top_asks)

    # Handle edge cases
    if ask_volume == 0:
        # Infinite demand, no supply
        return Decimal("999999") if bid_volume > 0 else Decimal("1.0")

    if bid_volume == 0:
        # No demand, infinite supply
        return Decimal("0")

    # Calculate ratio with proper precision
    ratio = bid_volume / ask_volume
    return ratio.quantize(Decimal("0.001"))  # 3 decimal places
```

### Risk Validation Pattern
```python
from decimal import Decimal
from loguru import logger

class RiskManager:
    def __init__(
        self,
        max_position_size: Decimal,
        daily_loss_limit: Decimal,
        max_drawdown: Decimal
    ):
        self.max_position_size = max_position_size
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown = max_drawdown
        self.peak_equity = Decimal("0")
        self.kill_switch_triggered = False

    def can_trade(self, signal: Signal, current_position: Position) -> bool:
        """Validate ALL risk limits before allowing entry."""
        if self.kill_switch_triggered:
            logger.warning("Kill switch active - all trading disabled")
            return False

        # Check daily loss limit
        daily_pnl = self.get_daily_pnl()
        if daily_pnl < -self.daily_loss_limit:
            self.trigger_kill_switch("Daily loss limit breached")
            return False

        # Check max drawdown
        current_equity = self.get_current_equity()
        drawdown = self.peak_equity - current_equity
        if drawdown > self.max_drawdown:
            self.trigger_kill_switch("Max drawdown breached")
            return False

        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # Check position size
        if signal.position_value > self.max_position_size:
            logger.warning(
                "Position size exceeds limit",
                requested=signal.position_value,
                limit=self.max_position_size
            )
            return False

        return True

    def trigger_kill_switch(self, reason: str):
        """Emergency shutdown of all trading."""
        logger.critical("KILL SWITCH TRIGGERED", reason=reason)
        self.kill_switch_triggered = True
        # TODO: Flatten all positions
        # TODO: Cancel all open orders
        # TODO: Send alerts via MCP (Slack/Discord)
```

### WebSocket Connection Pattern
```python
import asyncio
import websockets
from loguru import logger

class WebSocketManager:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.running = False
        self.ws = None

    async def connect(self, symbol: str):
        """Maintain persistent WebSocket with auto-reconnect."""
        self.running = True
        retry_delay = 5
        max_retry_delay = 60

        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    logger.info("WebSocket connected", symbol=symbol)

                    # Subscribe to data stream
                    await self.subscribe(ws, symbol)

                    # Reset retry delay on successful connection
                    retry_delay = 5

                    # Process messages
                    async for message in ws:
                        await self.handle_message(message)

            except websockets.ConnectionClosed:
                logger.warning(
                    "WebSocket closed, reconnecting",
                    delay=retry_delay
                )
                await asyncio.sleep(retry_delay)
                # Exponential backoff
                retry_delay = min(retry_delay * 2, max_retry_delay)

            except Exception as e:
                logger.error("WebSocket error", error=str(e))
                await asyncio.sleep(retry_delay)

    async def subscribe(self, ws, symbol: str):
        """Send subscription message."""
        sub_msg = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol.lower()}@depth@100ms"],
            "id": 1
        }
        await ws.send(json.dumps(sub_msg))

    async def handle_message(self, message: str):
        """Process incoming WebSocket message."""
        # Implementation depends on strategy
        pass

    async def stop(self):
        """Gracefully stop WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
```

### Strategy Implementation Pattern
```python
from abc import ABC, abstractmethod
from decimal import Decimal

class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, config: dict):
        self.config = config
        self.spot_only_mode = config.get("spot_only", False)

    @abstractmethod
    async def generate_signals(self, market_data: dict) -> list[Signal]:
        """Generate trading signals from market data.

        Returns:
            List of Signal objects with side, strength, confidence
        """
        pass

    def filter_signals(self, signals: list[Signal]) -> list[Signal]:
        """Filter signals based on mode (spot-only removes shorts)."""
        if not self.spot_only_mode:
            return signals

        # Remove short signals in spot-only mode
        return [s for s in signals if s.side != "SELL"]

class L2ImbalanceStrategy(BaseStrategy):
    """L2 order book imbalance trading strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.buy_threshold = Decimal(str(config.get("buy_threshold", 3.0)))
        self.sell_threshold = Decimal(str(config.get("sell_threshold", 0.33)))
        self.depth = config.get("depth", 5)

    async def generate_signals(self, market_data: dict) -> list[Signal]:
        """Generate signals based on L2 imbalance."""
        order_book = market_data['order_book']
        imbalance = calculate_imbalance(order_book, self.depth)

        signals = []

        if imbalance > self.buy_threshold:
            # Strong bid pressure - buy signal
            signals.append(Signal(
                side="BUY",
                strength=float(imbalance),
                confidence=0.8
            ))
        elif imbalance < self.sell_threshold:
            # Strong ask pressure - sell signal
            signals.append(Signal(
                side="SELL",
                strength=float(imbalance),
                confidence=0.8
            ))

        return self.filter_signals(signals)
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

class InsufficientFunds(TradingError):
    """Raised when account balance is insufficient."""
    pass

class ConnectionError(TradingError):
    """Raised when connection to exchange is lost."""
    pass

# Usage
try:
    position = execute_trade(signal)
except RiskLimitBreached as e:
    logger.warning("Trade blocked by risk management", error=str(e))
except OrderRejected as e:
    logger.error("Exchange rejected order", error=str(e))
except InsufficientFunds:
    logger.critical("Account balance too low for trade")
    # Trigger alert via MCP
```

### Logging Pattern
Log EVERYTHING for audit trail and debugging:

```python
from loguru import logger
from decimal import Decimal

# Configure structured logging
logger.add(
    "logs/trading_{time}.log",
    rotation="1 day",
    retention="90 days",
    compression="zip",
    serialize=True  # JSON format for parsing
)

# Log every signal generation
logger.info(
    "signal_generated",
    symbol="BTCUSDT",
    imbalance_ratio=str(imbalance_ratio),  # Decimal to string
    side="BUY",
    strength=0.8,
    timestamp=time.time()
)

# Log every order placement
logger.info(
    "order_placed",
    symbol="BTCUSDT",
    side="BUY",
    size=str(Decimal("0.1")),
    price=str(Decimal("45234.50")),
    order_id="12345",
    timestamp=time.time()
)

# Log every trade execution
logger.info(
    "trade_executed",
    symbol="BTCUSDT",
    side="BUY",
    size=str(Decimal("0.1")),
    fill_price=str(Decimal("45234.50")),
    commission=str(Decimal("4.52")),
    order_id="12345",
    trade_id="67890",
    timestamp=time.time()
)

# Log every risk check
logger.warning(
    "risk_limit_approached",
    daily_pnl=str(Decimal("-450.00")),
    limit=str(Decimal("-500.00")),
    remaining=str(Decimal("50.00")),
    percentage=90.0
)

# Log kill switch triggers
logger.critical(
    "kill_switch_triggered",
    reason="Daily loss limit breached",
    daily_pnl=str(Decimal("-502.15")),
    limit=str(Decimal("-500.00")),
    timestamp=time.time()
)
```

### Database Schema Pattern
```python
from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from decimal import Decimal

Base = declarative_base()

class Trade(Base):
    """All executed trades for audit trail."""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # BUY or SELL
    size = Column(Numeric(20, 8), nullable=False)  # Decimal precision
    price = Column(Numeric(20, 8), nullable=False)
    commission = Column(Numeric(20, 8), nullable=False)
    order_id = Column(String, nullable=False)
    trade_id = Column(String, unique=True, nullable=False)
    timestamp = Column(DateTime, nullable=False)

class Position(Base):
    """Current and historical positions."""
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    size = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8))
    unrealized_pnl = Column(Numeric(20, 2))
    realized_pnl = Column(Numeric(20, 2))
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)

class RiskEvent(Base):
    """Kill switch triggers and limit breaches."""
    __tablename__ = 'risk_events'

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)  # KILL_SWITCH, LIMIT_BREACH
    reason = Column(String, nullable=False)
    metric_value = Column(Numeric(20, 2))
    limit_value = Column(Numeric(20, 2))
    timestamp = Column(DateTime, nullable=False)

# Usage
session.add(Trade(
    symbol="BTCUSDT",
    side="BUY",
    size=Decimal("0.1"),
    price=Decimal("45234.50"),
    commission=Decimal("4.52"),
    order_id="12345",
    trade_id="67890",
    timestamp=datetime.now()
))
session.commit()
```

## Prohibited Actions

- **NEVER commit sensitive information** - API keys, secrets, .env files are gitignored
- **NEVER use `float` for financial calculations** - use Decimal exclusively
- **NEVER execute live trades without paper trading validation** - 60 days minimum
- **NEVER bypass risk limits** - even if signal looks good, respect the limits
- **NEVER modify CLAUDE.md or ROADMAP.md without explicit user request** - these are protected
- **NEVER skip the kill switch test** - it must be verified to work before live trading
- **NEVER proceed past Phase 6 gate without meeting criteria** - paper trading win rate >50% required
- **NEVER use hardcoded API credentials** - always use environment variables
- **NEVER disable risk checks** - even for testing, use test fixtures instead

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
- [ ] Kill switch tested and functional

### Gate 3→4: API Server Working
- [ ] Kill switch tested via API
- [ ] Can control engine via API (start/stop/kill)
- [ ] Database persistence working
- [ ] All trades logged to database

### Gate 4→5: UI Complete
- [ ] Real-time data displayed accurately
- [ ] All controls functional
- [ ] Kill switch button works
- [ ] P&L tracking accurate

### Gate 5→6: Paper Trading Validated ⚠️ CRITICAL
- [ ] 60 days of paper trading completed
- [ ] Win rate >50%
- [ ] Profit factor >1.0
- [ ] Confidence that edge exists
- [ ] Maximum drawdown within limits
- [ ] Sharpe ratio >0.5

**DO NOT proceed to live trading without meeting these criteria**

### Gate 6→7: Micro-Capital Tested
- [ ] 30 days with $100-500 real capital
- [ ] Break-even or positive
- [ ] No critical bugs discovered
- [ ] Risk limits working correctly
- [ ] Kill switch verified with real money

## Progress Tracking

See ROADMAP.md for detailed project phases, features, and current progress.

Current implementation should track:
- Which phase you're in
- Current week (of 24)
- Next milestone target
- Any blockers
- Test results and coverage
- Risk metric compliance

## Documentation References

Detailed project documentation is available in /Users/adamoates/Documents/trader/:
- `mft-architecture.md` - Complete system design and component specifications
- `mft-strategy-spec.md` - L2 imbalance strategy logic and parameters
- `mft-risk-management.md` - All risk limits and kill switch procedures
- `mft-roadmap.md` - Phase-by-phase development plan
- `mft-research-questions.md` - Validation questions for strategy research
- `mft-dev-log.md` - Template for tracking daily/weekly progress

Reference these documents when implementing specific components.

## Performance Targets

### Latency Requirements
- **Message Processing**: <5ms per L2 update
- **Order Placement**: <20ms from signal to order submission
- **Total Signal-to-Execution**: <50ms sustained
- **WebSocket Reconnection**: <5s

### Reliability Targets
- **Uptime**: 99.9% during market hours
- **Data Loss**: 0 trades unlogged
- **Order Success Rate**: >98%
- **WebSocket Stability**: <3 disconnects per 24h

### Testing Targets
- **Code Coverage**: >80% overall, 100% for risk code
- **Test Execution**: <30s for unit tests, <2min for integration
- **CI Pipeline**: <5min total

## Security Guidelines

### API Key Management
```python
# CORRECT: Use environment variables
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# WRONG: Never hardcode
api_key = "abc123..."  # ❌ NEVER DO THIS
```

### Database Credentials
```python
# CORRECT: Environment variables
db_url = os.getenv("DATABASE_URL")

# WRONG: Hardcoded
db_url = "postgresql://user:pass@localhost/db"  # ❌ NEVER
```

### Secret Scanning
- CI pipeline runs secret detection on every commit
- Pre-commit hooks prevent accidental commits of .env files
- Never commit credentials to version control

## Deployment Checklist

Before deploying to production:
- [ ] All tests passing (100% success rate)
- [ ] Code coverage >80%
- [ ] No secrets in code
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Kill switch tested
- [ ] Monitoring alerts configured (MCP Slack/Discord)
- [ ] Backup strategy in place
- [ ] Rollback plan documented
- [ ] Paper trading validated (60 days)
- [ ] Micro-capital tested (30 days)

## Support and Resources

- **GitHub Repository**: https://github.com/adamoates/Trade-Engine
- **Issues**: https://github.com/adamoates/Trade-Engine/issues
- **Documentation**: `/docs` directory
- **External Docs**: `/Users/adamoates/Documents/trader/`

For questions about Claude Code itself, use `/help` or visit https://docs.claude.com/en/docs/claude-code
