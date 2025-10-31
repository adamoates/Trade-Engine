# MFT Trading Bot - Development Workflow Guide

## Overview

This guide defines the daily development workflow, git practices, code review procedures, and team collaboration patterns for the MFT trading bot project.

**Philosophy**: Systematic, disciplined development that maintains code quality while moving quickly.

---

## Table of Contents
1. [Daily Development Cycle](#daily-development-cycle)
2. [Git Workflow](#git-workflow)
3. [Code Review Process](#code-review-process)
4. [Testing Strategy](#testing-strategy)
5. [Documentation Practices](#documentation-practices)
6. [Team Collaboration](#team-collaboration)

---

## Daily Development Cycle

### Morning Routine (10 minutes)

```bash
# 1. Start your day
cd ~/Code/Python/mft-trading-bot

# 2. Pull latest changes
git checkout main
git pull origin main

# 3. Review what's happening
git log --oneline -10
gh pr list
gh issue list

# 4. Update ROADMAP.md current status (mental check)
# - Where am I in the timeline?
# - What's my goal for today?
# - Any blockers?
```

### Feature Development Workflow

#### Step 1: Plan Your Work (5-10 minutes)

```bash
# Check ROADMAP.md for current phase tasks
# Example: Phase 2, Week 7 - Signal Generator

# Break down into subtasks:
# - [ ] Implement imbalance calculation
# - [ ] Add signal threshold logic
# - [ ] Write unit tests
# - [ ] Add integration tests
# - [ ] Update documentation
```

#### Step 2: Create Feature Branch

```bash
# Naming convention: <type>/<description>
# Types: feature, fix, refactor, test, docs, chore

# Example:
git checkout -b feature/signal-generator-imbalance

# Or for bug fixes:
git checkout -b fix/order-book-race-condition
```

#### Step 3: Write Tests First (TDD Approach)

```python
# tests/unit/test_signal_generator.py

def test_calculate_imbalance_basic():
    """Test imbalance calculation with balanced book"""
    order_book = create_test_order_book(
        bids=[(50000, 1.0), (49999, 1.0)],
        asks=[(50001, 1.0), (50002, 1.0)]
    )

    imbalance = calculate_imbalance(order_book, depth=2)

    assert imbalance == 1.0, "Balanced book should have 1.0 ratio"

def test_calculate_imbalance_buy_pressure():
    """Test imbalance with strong buy pressure"""
    order_book = create_test_order_book(
        bids=[(50000, 3.0), (49999, 2.0)],  # 5.0 total
        asks=[(50001, 1.0), (50002, 1.0)]   # 2.0 total
    )

    imbalance = calculate_imbalance(order_book, depth=2)

    assert imbalance == 2.5, "Should have 2.5x buy pressure"
```

Run tests (they should fail):
```bash
pytest tests/unit/test_signal_generator.py -v
# Expected: FAILED (function doesn't exist yet)
```

#### Step 4: Implement Feature

```python
# engine/signals/generator.py

from typing import Dict
from decimal import Decimal

def calculate_imbalance(order_book: OrderBook, depth: int = 5) -> float:
    """
    Calculate bid/ask volume ratio from top N levels.

    Args:
        order_book: Current order book state
        depth: Number of price levels to consider

    Returns:
        Imbalance ratio (bid_volume / ask_volume)

    Examples:
        >>> calculate_imbalance(balanced_book, depth=5)
        1.0
        >>> calculate_imbalance(buy_pressure_book, depth=5)
        3.5  # Strong buy pressure
    """
    # Get top N bids (highest prices)
    top_bids = sorted(order_book.bids.items(), reverse=True)[:depth]
    bid_volume = sum(quantity for price, quantity in top_bids)

    # Get top N asks (lowest prices)
    top_asks = sorted(order_book.asks.items())[:depth]
    ask_volume = sum(quantity for price, quantity in top_asks)

    # Handle edge case
    if ask_volume == 0:
        return float('inf') if bid_volume > 0 else 1.0

    return bid_volume / ask_volume
```

#### Step 5: Run Tests

```bash
# Run new tests
pytest tests/unit/test_signal_generator.py -v

# Run all tests
pytest tests/ -v

# Check coverage
pytest --cov=engine.signals --cov-report=term-missing tests/unit/test_signal_generator.py
```

#### Step 6: Check Code Quality

```bash
# Run local CI checks
./scripts/run-ci-checks.sh

# Or run individual checks:

# Format code
black engine/ tests/

# Lint
ruff check engine/ tests/

# Type check
mypy engine/signals/

# If checks fail, fix and re-run
```

#### Step 7: Commit Work

```bash
# Stage changes
git add engine/signals/generator.py
git add tests/unit/test_signal_generator.py

# Commit with descriptive message
git commit -m "feat: Implement imbalance calculation for signal generation

- Add calculate_imbalance function with configurable depth
- Handle edge cases (empty book, zero ask volume)
- Add comprehensive unit tests with 98% coverage
- Validate against manual calculations

Relates to ROADMAP Phase 2, Week 7
"

# Verify commit
git log -1 --stat
```

### Commit Message Guidelines

**Format**:
```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring without behavior change
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks (dependencies, configs)
- `perf`: Performance improvements
- `style`: Code style changes (formatting, no logic change)

**Examples**:

```bash
# Good commit messages
git commit -m "feat: Add WebSocket reconnection logic with exponential backoff"

git commit -m "fix: Correct order book update sequence validation

- Fix off-by-one error in update ID checking
- Add test case for edge case
- Prevents state divergence from exchange

Fixes issue #42
"

git commit -m "refactor: Extract signal validation to separate method

- Improves readability and testability
- No behavior change
- Adds unit tests for validation logic
"

git commit -m "test: Add integration tests for risk manager kill switch

- Test daily loss limit trigger
- Test max drawdown trigger
- Test position flattening on kill switch
- All tests pass with PostgreSQL container

Coverage: 95% on RiskManager class
"
```

```bash
# Bad commit messages (avoid)
git commit -m "Fixed stuff"
git commit -m "WIP"
git commit -m "Updated files"
git commit -m "Changes"
```

### End of Day Routine (10 minutes)

```bash
# 1. Commit any WIP work
git add .
git commit -m "chore: End of day WIP - signal generator [skip ci]"

# 2. Push to your branch
git push origin feature/signal-generator-imbalance

# 3. Update dev log (if using)
# Add notes about what you accomplished, blockers, next steps

# 4. Check CI status
gh run list --limit 5

# 5. Plan tomorrow
# What's the next task?
# Any dependencies or blockers?
```

---

## Git Workflow

### Branch Naming Convention

```
<type>/<description>

Types:
- feature/  - New features
- fix/      - Bug fixes
- refactor/ - Code restructuring
- test/     - Test additions/updates
- docs/     - Documentation
- chore/    - Maintenance

Examples:
feature/order-book-processor
fix/websocket-reconnection
refactor/signal-validation
test/risk-manager-integration
docs/architecture-update
chore/update-dependencies
```

### Branch Lifecycle

```bash
# 1. Create from main
git checkout main
git pull origin main
git checkout -b feature/your-feature

# 2. Develop with regular commits
git add <files>
git commit -m "..."

# 3. Push to remote regularly
git push origin feature/your-feature

# 4. Keep branch updated with main
git checkout main
git pull origin main
git checkout feature/your-feature
git rebase main  # or git merge main

# 5. Create PR when ready
gh pr create --title "Add order book processor" --body "..."

# 6. After PR merged, delete branch
git checkout main
git pull origin main
git branch -d feature/your-feature
git push origin --delete feature/your-feature
```

### Handling Merge Conflicts

```bash
# If rebase causes conflicts
git status  # See conflicted files

# Open each file and resolve conflicts manually
# Look for <<<<<<< HEAD markers

# After resolving:
git add <resolved-files>
git rebase --continue

# If things go wrong:
git rebase --abort  # Start over

# Alternative: merge instead of rebase
git checkout feature/your-feature
git merge main
# Resolve conflicts
git commit
```

### Stashing Changes

```bash
# Need to switch branches but have uncommitted work?

# Stash your changes
git stash save "WIP: Working on signal generator"

# Switch branches and do other work
git checkout main
# ... do work ...

# Return to your branch
git checkout feature/signal-generator

# Restore stashed changes
git stash pop

# View all stashes
git stash list

# Apply specific stash
git stash apply stash@{0}
```

---

## Code Review Process

### Before Creating PR

- [ ] All tests pass locally
- [ ] Code coverage ≥80%
- [ ] Local CI checks pass (`./scripts/run-ci-checks.sh`)
- [ ] Code is formatted (black) and linted (ruff)
- [ ] Documentation updated (if needed)
- [ ] Commit messages are clear
- [ ] No debug code or print statements left
- [ ] No commented-out code
- [ ] No secrets or API keys in code

### Creating a Pull Request

```bash
# Option 1: Using GitHub CLI
gh pr create \
  --title "Add L2 order book processor with snapshot handling" \
  --body "$(cat <<EOF
## What Changed
Implemented the order book processor that maintains real-time state from WebSocket updates.

## Why
Required for Phase 2 (Engine Development) - Week 5-6 deliverable.

## How It Was Tested
- [x] Unit tests pass locally (15 new tests)
- [x] Integration tests with PostgreSQL pass
- [x] Manual testing with Binance testnet WebSocket
- [x] CI checks pass

## Implementation Details
- Handles both snapshot and delta updates
- Maintains separate bid/ask dictionaries
- Validates update sequence to prevent gaps
- Auto-reconnect on WebSocket disconnect

## Checklist
- [x] Code follows project style guidelines
- [x] Tests added (95% coverage on OrderBook class)
- [x] Documentation updated (docstrings + README)
- [x] No float usage in financial code
- [x] Risk limits respected
- [x] ROADMAP.md updated (marked deliverable as completed)

## Performance
- Processes 1,000+ updates/second
- Average latency: 2.3ms per update
- Memory usage: ~50MB for 1000 price levels

## Related Issues
Part of Phase 2 milestone.
EOF
)"

# Option 2: Through GitHub web interface
git push origin feature/your-feature
# Then go to GitHub and click "Create Pull Request"
```

### PR Description Template

```markdown
## What Changed
Brief summary of what this PR does (2-3 sentences)

## Why
Explanation of why this change is needed

## How It Was Tested
- [ ] Unit tests pass locally
- [ ] Integration tests pass locally
- [ ] Manual testing performed
- [ ] CI checks pass

## Implementation Details
- Key design decisions
- Trade-offs considered
- Performance characteristics

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests added/updated (specify coverage %)
- [ ] Documentation updated
- [ ] No float usage in financial code
- [ ] Risk limits respected
- [ ] ROADMAP.md updated if milestone completed

## Related Issues
Links to issues, tickets, or ROADMAP sections
```

### Code Review Checklist (Reviewer)

#### Code Quality
- [ ] Code is readable and well-organized
- [ ] Variable and function names are clear
- [ ] No unnecessary complexity
- [ ] DRY principle followed (no duplication)
- [ ] Error handling is appropriate
- [ ] Edge cases are handled

#### Trading System Safety
- [ ] **CRITICAL**: No `float()` usage for money calculations
- [ ] **CRITICAL**: Risk limits are enforced
- [ ] Decimal used for all financial values
- [ ] All trades are logged
- [ ] Kill switch logic intact (if touched)

#### Testing
- [ ] Tests are comprehensive (happy path + edge cases)
- [ ] Test coverage ≥80%
- [ ] Tests are independent (no shared state)
- [ ] Mocks are used appropriately
- [ ] Tests are fast (<5 seconds for unit tests)

#### Performance
- [ ] No obvious performance issues
- [ ] Efficient algorithms used
- [ ] No n+1 query problems
- [ ] Async code properly awaited
- [ ] Memory leaks unlikely

#### Security
- [ ] No secrets in code
- [ ] Input validation present
- [ ] SQL injection not possible
- [ ] Dependencies are safe (not flagged by security scan)

### Providing Feedback

**Good feedback**:
```
📝 In `engine/signals/generator.py:45`:

Consider extracting this calculation to a separate method for better testability:

    def _calculate_bid_volume(self, bids):
        return sum(qty for price, qty in bids)

This would allow unit testing the volume calculation independently.
```

**Great feedback with example**:
```
⚠️  In `engine/risk/manager.py:78`:

Using `float` for position value violates our financial code safety rule.

Change:
    position_value = float(order.quantity) * float(order.price)

To:
    from decimal import Decimal
    position_value = Decimal(str(order.quantity)) * Decimal(str(order.price))

See CLAUDE.md "Critical Rules" section.
```

**Constructive feedback**:
```
💡 In `tests/test_order_book.py:120`:

This test could be more comprehensive. Consider adding edge cases:
- What if bids dict is empty?
- What if there's a gap in update IDs?
- What if update comes before snapshot?

Example test structure:
    def test_update_before_snapshot_raises_error():
        book = OrderBook('BTCUSDT')
        with pytest.raises(ValueError, match="No snapshot"):
            book.handle_update(delta_update)
```

### Responding to Feedback

```bash
# Make requested changes
# ... edit files ...

# Commit with reference to feedback
git add <files>
git commit -m "refactor: Extract volume calculation per review feedback

- Extract _calculate_bid_volume method
- Extract _calculate_ask_volume method
- Add unit tests for volume calculations
- Improves testability as suggested
"

# Push to update PR
git push origin feature/your-feature

# Comment on review:
# "✅ Updated - extracted volume calculations as suggested"
```

### Merging Pull Requests

**Merge criteria** (ALL must be met):
- [ ] At least 1 approval from team member
- [ ] All CI checks pass (green checkmarks)
- [ ] All conversations resolved
- [ ] Branch is up to date with main
- [ ] No merge conflicts

**Merge strategy**: Squash and merge (recommended)
- Keeps main branch history clean
- Combines all PR commits into one
- Edit the squash commit message to be clear

```
After merge:
1. Delete branch remotely (GitHub does this automatically)
2. Delete branch locally:
   git checkout main
   git pull
   git branch -d feature/your-feature
```

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \        E2E Tests (few)
      /────\       - Complete user flows
     /      \      - Staging environment
    /────────\     - Slow, expensive
   /          \
  /────────────\   Integration Tests (some)
 /              \  - Component interactions
/────────────────\ - Database, API, WebSocket
                   - Medium speed
────────────────── Unit Tests (many)
                   - Individual functions
                   - Fast, isolated
                   - Mock dependencies
```

### Test Organization

```
tests/
├── unit/                 # Fast, isolated tests
│   ├── test_order_book.py
│   ├── test_signal_generator.py
│   └── test_risk_manager.py
├── integration/          # Component interaction tests
│   ├── test_engine_integration.py
│   ├── test_api_endpoints.py
│   └── test_database_operations.py
├── e2e/                  # End-to-end tests (Phase 4+)
│   └── test_trading_flow.py
└── fixtures/             # Shared test data
    ├── order_book_samples.py
    └── market_data.py
```

### Writing Tests

**Unit Test Example**:
```python
# tests/unit/test_signal_generator.py

import pytest
from decimal import Decimal
from engine.signals.generator import SignalGenerator
from tests.fixtures.order_book_samples import create_balanced_book

class TestSignalGenerator:
    """Tests for SignalGenerator class"""

    @pytest.fixture
    def generator(self):
        """Create SignalGenerator with default config"""
        return SignalGenerator(config={
            'imbalance_depth': 5,
            'buy_threshold': 3.0,
            'sell_threshold': 0.33
        })

    def test_calculate_imbalance_balanced_book(self, generator):
        """Should return 1.0 for balanced order book"""
        book = create_balanced_book()

        result = generator.calculate_imbalance(book)

        assert result == 1.0

    def test_calculate_imbalance_buy_pressure(self, generator):
        """Should return >3.0 for strong buy pressure"""
        book = create_test_book(
            bids=[(50000, 5.0), (49999, 4.0)],  # 9.0 total
            asks=[(50001, 1.0), (50002, 2.0)]   # 3.0 total
        )

        result = generator.calculate_imbalance(book)

        assert result == 3.0

    def test_generate_signal_buy(self, generator):
        """Should generate BUY signal for strong buy pressure"""
        book = create_test_book_with_buy_pressure()

        signal = generator.generate_signal(book)

        assert signal.side == 'BUY'
        assert signal.strength > 0.5

    @pytest.mark.parametrize("bid_vol,ask_vol,expected", [
        (5.0, 5.0, 1.0),      # Balanced
        (10.0, 2.0, 5.0),     # Strong buy
        (2.0, 10.0, 0.2),     # Strong sell
        (0.0, 5.0, 0.0),      # No bids
    ])
    def test_imbalance_ratios(self, generator, bid_vol, ask_vol, expected):
        """Test various imbalance scenarios"""
        book = create_test_book_with_volumes(bid_vol, ask_vol)

        result = generator.calculate_imbalance(book)

        assert result == pytest.approx(expected, rel=0.01)
```

**Integration Test Example**:
```python
# tests/integration/test_engine_integration.py

import pytest
import asyncio
from engine.core.engine import TradingEngine
from engine.signals.generator import SignalGenerator
from engine.risk.manager import RiskManager

@pytest.mark.asyncio
class TestEngineIntegration:
    """Integration tests for complete engine"""

    @pytest.fixture
    async def engine(self, db_session):
        """Create engine with real components"""
        config = {
            'symbol': 'BTCUSDT',
            'max_position_size': 10000,
            'daily_loss_limit': 500
        }

        engine = TradingEngine(config)
        await engine.initialize()
        yield engine
        await engine.shutdown()

    async def test_complete_trade_flow(self, engine):
        """Test complete flow: signal → risk check → order → close"""
        # 1. Generate signal
        signal = await engine.generate_signal()
        assert signal is not None

        # 2. Risk check
        can_trade = engine.risk_manager.can_trade(signal)
        assert can_trade is True

        # 3. Place order
        position = await engine.execute_entry(signal)
        assert position is not None
        assert position.status == 'OPEN'

        # 4. Close position
        await engine.execute_exit(position, reason='test')
        assert position.status == 'CLOSED'

        # 5. Verify in database
        db_trade = db_session.query(Trade).filter_by(id=position.id).first()
        assert db_trade is not None
        assert db_trade.pnl is not None
```

### Running Tests

```bash
# All tests
pytest

# Specific directory
pytest tests/unit/

# Specific file
pytest tests/unit/test_signal_generator.py

# Specific test
pytest tests/unit/test_signal_generator.py::test_calculate_imbalance_basic

# With coverage
pytest --cov=engine --cov-report=html

# View coverage report
open htmlcov/index.html

# Fast tests only (skip slow integration tests)
pytest -m "not slow"

# Run tests in parallel (faster)
pytest -n auto

# Run tests with output
pytest -v -s
```

---

## Documentation Practices

### Code Documentation

**Module-level docstring**:
```python
"""
Signal generator for L2 order book imbalance trading strategy.

This module implements the core signal generation logic that analyzes
Level 2 order book data to identify supply/demand imbalances that
predict short-term price movements.

Usage:
    generator = SignalGenerator(config)
    signal = generator.generate_signal(order_book)

    if signal.side == 'BUY':
        # Execute buy order

See Also:
    engine.risk.manager: Risk validation for signals
    engine.execution.executor: Order execution logic
"""
```

**Function docstring**:
```python
def calculate_imbalance(order_book: OrderBook, depth: int = 5) -> float:
    """
    Calculate bid/ask volume ratio from top N levels of order book.

    Analyzes the top N bid and ask levels to compute a ratio that indicates
    market pressure. Values >3.0 suggest buying pressure, <0.33 suggest
    selling pressure.

    Args:
        order_book: Current order book state with bids/asks
        depth: Number of price levels to analyze (default: 5)

    Returns:
        Imbalance ratio as bid_volume / ask_volume
        Returns float('inf') if ask_volume is 0 and bids exist
        Returns 1.0 if both sides are 0

    Raises:
        ValueError: If depth < 1 or order_book is invalid

    Examples:
        >>> book = create_balanced_book()
        >>> calculate_imbalance(book, depth=5)
        1.0

        >>> book = create_book_with_buy_pressure()
        >>> calculate_imbalance(book, depth=5)
        3.5

    Note:
        This calculation is performed on every order book update,
        so it must be highly optimized (<1ms execution time).
    """
```

### Updating Documentation

**When to update docs**:
- New feature added → Update README.md and relevant guides
- API endpoint changed → Update docs/deployment.md
- Configuration changed → Update CLAUDE.md
- Major decision made → Add to docs/guides/architecture-decisions.md
- Phase completed → Update ROADMAP.md

**Documentation checklist** before PR:
- [ ] Code has docstrings
- [ ] README.md updated if needed
- [ ] CLAUDE.md updated for new patterns
- [ ] ROADMAP.md progress updated
- [ ] API documentation updated (Phase 3+)

---

## Team Collaboration

### Communication Channels

**GitHub Issues**: Feature requests, bugs, discussions
```bash
# Create issue
gh issue create --title "Add support for multiple exchanges" --body "..."

# View issues
gh issue list

# Comment on issue
gh issue comment 42 --body "I'm working on this"
```

**Pull Request Discussions**: Code-specific feedback

**Discord/Slack** (if used): Quick questions, daily standups

### Pair Programming

**When to pair**:
- Complex/risky features (risk manager, order execution)
- Learning new concepts (async programming, WebSockets)
- Debugging difficult issues
- Onboarding new team members

**Best practices**:
- Switch driver/navigator every 20-30 minutes
- Commit frequently
- Take breaks every hour
- Document learnings after session

### Code Ownership

**No strict ownership** - anyone can work on any part

**Expertise areas** (optional):
- Engine core: [Name]
- Risk management: [Name]
- API/Frontend: [Name]
- Testing/CI: [Name]

**Review requirements**:
- Risk-critical code (risk manager, kill switch) → 2 approvals required
- Other code → 1 approval sufficient

---

## Quick Reference

### Daily Commands
```bash
# Morning
git checkout main && git pull

# Start feature
git checkout -b feature/your-feature

# During development
pytest tests/ -v
./scripts/run-ci-checks.sh

# Commit
git add . && git commit -m "feat: ..."

# Push
git push origin feature/your-feature

# Create PR
gh pr create

# End of day
git push origin feature/your-feature
```

### Emergency Procedures
```bash
# Need to switch branches with uncommitted work
git stash save "WIP"
git checkout other-branch
# ... work ...
git checkout feature/your-feature
git stash pop

# Messed up commits
git reset --soft HEAD~1  # Undo last commit, keep changes
git reset --hard HEAD~1  # Undo last commit, discard changes

# Need to undo a merge
git reflog  # Find commit before merge
git reset --hard <commit-hash>
```

---

**Remember**: Good development workflow prevents bugs, enables collaboration, and maintains code quality. Follow these practices consistently, especially the testing and code review procedures for a financial trading system.
