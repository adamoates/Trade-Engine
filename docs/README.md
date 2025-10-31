# Trade Engine Documentation

**Clear path-based navigation for all documentation**

## 🚀 Getting Started

New to the project? Start here:
- [Development Setup](development/setup.md) - Complete environment setup
- [Architecture Overview](architecture/live-trading-evolution.md) - System design evolution
- [Development Workflow](development/workflow.md) - Daily development practices

**Coming Soon**:
- Quickstart Guide (5-minute setup)
- Installation Guide (detailed setup)
- First Run Tutorial (run your first backtest)

## 📈 Trading Strategies

Learn about implemented strategies:
- [Breakout Detector](strategies/breakout-detector.md) - 7-factor breakout detection
- [Open Interest & Funding](strategies/open-interest-funding.md) - Derivatives analysis
- [Regime Detector](strategies/regime-detector.md) - Market regime classification
- [Volume RVOL](strategies/volume-rvol.md) - Volume analysis
- [Multi-Factor Screener](strategies/multi-factor-screener.md) - Stock screening
- [Configuration Examples](strategies/configuration-examples.md) - Strategy configs
- [Spot-Only Trading](strategies/spot-only-trading.md) - Long-only mode

**Coming Soon**:
- L2 Order Book Imbalance Guide (PRIMARY STRATEGY)

## 💻 Development

Contributing to the project:
- [Development Setup](development/setup.md) - Complete environment setup
- [Workflow](development/workflow.md) - Daily development practices
- [Git Workflow](development/git-workflow.md) - Branching and PRs

**Coming Soon**:
- Testing Guide (testing strategies)
- Code Standards (coding conventions)

## 🔧 Operations

Running and deploying:
- [Deployment Guide](operations/deployment.md) - Production deployment
- [Data Recording](operations/data-recording.md) - Real-time data capture
- [Docker Performance](operations/docker-performance.md) - Container optimization
- [Live Server Guide](operations/live-server-quick-reference.md) - Server management
- [Live Server Updates](operations/live-server-update.md) - Update procedures

**Coming Soon**:
- Database Operations (PostgreSQL management)
- Monitoring Guide (system monitoring)
- Troubleshooting Guide (common issues)

## 📊 Data Pipeline

Working with market data:
- [Pipeline Overview](data/pipeline-overview.md) - Complete data workflows
- [Data Validation](data/validation.md) - Quality checks and cleaning
- [Test Fixtures](data/fixtures.md) - Historical test data
- [Web3 Signals](data/web3-signals.md) - On-chain data
- [Pipeline One-Liners](data/pipeline-one-liners.md) - Quick commands

**Coming Soon**:
- Data Sources Guide (API integrations)

## 🏦 Broker Integration

Exchange connectivity:
- [Broker Comparison](brokers/comparison.md) - Feature comparison
- [Broker Testing](brokers/testing.md) - Integration testing

**Coming Soon**:
- Kraken Guide (Kraken Futures - US-accessible)
- Binance Guide (Binance Futures)
- Binance.us Guide (US spot trading)

## ⚙️ CI/CD & Automation

Continuous integration and deployment:
- [CI/CD Setup](ci-cd/setup.md) - Quick-start setup
- [GitHub Actions](ci-cd/github-actions.md) - Complete reference

**Coming Soon**:
- Quality Gates Guide (automated checks)

## 📚 Technical Reference

API and implementation details:
- [Adapter Interfaces](reference/adapters/README.md) - Broker/feed/source adapters
  - [Broker Interface](reference/adapters/broker-interface.md)
  - [Feed Interface](reference/adapters/feed-interface.md)
  - [Data Source Interface](reference/adapters/data-source-interface.md)
  - [How to Add Adapters](reference/adapters/how-to-add-adapters.md)
- [Logging Reference](reference/logging.md) - Structured logging
- [Logging Initialization](reference/logging-initialization.md) - Setup guide
- [Logging Testing](reference/logging-testing.md) - Testing patterns
- [Python Tool Structure](reference/python-tool-structure.md) - Package design
- [Documentation Guide](reference/documentation-guide.md) - Writing docs

**Coming Soon**:
- API Reference (FastAPI endpoints)
- Database Schema Reference (PostgreSQL tables)

## 🏗️ Architecture

System design and evolution:
- [Live Trading Evolution](architecture/live-trading-evolution.md) - System evolution
- [TDD Audit Strategy](architecture/tdd-audit-and-strategy.md) - Testing approach
- [Trade Fingerprint System](architecture/trade-fingerprint-system.md) - Trade identification

## 📋 Reports & Analysis

Historical reports and audits:
- [All Reports](reports/) - Sprint summaries, audits, test reports
- [Archived Docs](archive/) - Old refactoring documentation

---

## Looking for Something Specific?

### Critical Documents
- **Project Rules**: [`../.claude/CLAUDE.md`](../.claude/CLAUDE.md) - AI context, code standards, critical rules
- **Development Roadmap**: [`../ROADMAP.md`](../ROADMAP.md) - Phase-gate development plan
- **Main README**: [`../README.md`](../README.md) - Project overview

### Quick Commands
```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,database]"

# Testing
pytest tests/ -v
pytest --cov=src/trade_engine --cov-report=term-missing

# Code Quality
black src/ tests/
ruff check src/ tests/
mypy src/

# Run Engine
python -m trade_engine.api.server
```

### Common Tasks
- **First time setup?** → [Development Setup](development/setup.md)
- **Adding a new strategy?** → [Strategy Configuration](strategies/configuration-examples.md)
- **Deploying to production?** → [Deployment Guide](operations/deployment.md)
- **Running backtests?** → [Test Fixtures](data/fixtures.md)
- **Setting up CI/CD?** → [CI/CD Setup](ci-cd/setup.md)

### Getting Help
- **Issues**: Check operations guides or file an issue
- **Questions**: See [GitHub Discussions](https://github.com/adamoates/Trade-Engine/discussions)
- **Bugs**: File an [issue](https://github.com/adamoates/Trade-Engine/issues)

---

## Documentation Philosophy

This documentation follows a **progressive disclosure** pattern:
1. **Getting Started** - Quick wins for new users
2. **Task-Oriented Guides** - How to accomplish specific goals
3. **Technical Reference** - Deep implementation details
4. **Architecture** - Design decisions and evolution

**Remember**: Documentation is living - keep it updated as the project evolves!
