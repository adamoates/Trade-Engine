# Trade Engine Documentation

**Clear path-based navigation for all documentation**

## 🚀 Getting Started

New to the project? Start here:
- [**Quickstart Guide**](getting-started/quickstart.md) - 5-minute setup
- [Installation](getting-started/installation.md) - Detailed setup
- [Architecture Overview](getting-started/architecture-overview.md) - System design
- [First Run](getting-started/first-run.md) - Run your first backtest

## 📈 Trading Strategies

Learn about implemented strategies:
- [**L2 Order Book Imbalance**](strategies/l2-imbalance.md) - PRIMARY STRATEGY - Order book scalping
- [Breakout Detector](strategies/breakout-detector.md) - 7-factor breakout detection
- [Open Interest & Funding](strategies/open-interest-funding.md) - Derivatives analysis
- [Regime Detector](strategies/regime-detector.md) - Market regime classification
- [Volume RVOL](strategies/volume-rvol.md) - Volume analysis
- [Multi-Factor Screener](strategies/multi-factor-screener.md) - Stock screening
- [Configuration Examples](strategies/configuration-examples.md) - Strategy configs
- [Spot-Only Trading](strategies/spot-only-trading.md) - Long-only mode

## 💻 Development

Contributing to the project:
- [Development Setup](development/setup.md) - Complete environment setup
- [Workflow](development/workflow.md) - Daily development practices
- [Git Workflow](development/git-workflow.md) - Branching and PRs
- [Testing Guide](development/testing.md) - Testing strategies
- [Code Standards](development/code-standards.md) - Coding conventions

## 🔧 Operations

Running and deploying:
- [Deployment Guide](operations/deployment.md) - Production deployment
- [Database Operations](operations/database.md) - PostgreSQL management
- [Data Recording](operations/data-recording.md) - Real-time data capture
- [Monitoring](operations/monitoring.md) - System monitoring
- [Troubleshooting](operations/troubleshooting.md) - Common issues
- [Docker Performance](operations/docker-performance.md) - Container optimization
- [Live Server Guide](operations/live-server-quick-reference.md) - Server management

## 📊 Data Pipeline

Working with market data:
- [Pipeline Overview](data/pipeline-overview.md) - Complete data workflows
- [Data Validation](data/validation.md) - Quality checks and cleaning
- [Test Fixtures](data/fixtures.md) - Historical test data
- [Data Sources](data/sources.md) - API integrations
- [Web3 Signals](data/web3-signals.md) - On-chain data
- [Pipeline One-Liners](data/pipeline-one-liners.md) - Quick commands

## 🏦 Broker Integration

Exchange connectivity:
- [Broker Comparison](brokers/comparison.md) - Feature comparison
- [Broker Testing](brokers/testing.md) - Integration testing
- [Kraken Guide](brokers/kraken.md) - Kraken Futures (US-accessible)
- [Binance Guide](brokers/binance.md) - Binance Futures
- [Binance.us Guide](brokers/binance-us.md) - US spot trading

## ⚙️ CI/CD & Automation

Continuous integration and deployment:
- [CI/CD Setup](ci-cd/setup.md) - Quick-start setup
- [GitHub Actions](ci-cd/github-actions.md) - Complete reference
- [Quality Gates](ci-cd/quality-gates.md) - Automated checks

## 📚 Technical Reference

API and implementation details:
- [Adapter Interfaces](reference/adapters/) - Broker/feed/source adapters
- [API Reference](reference/api/) - FastAPI endpoints
- [Database Schema](reference/database-schema.md) - PostgreSQL tables
- [Logging Reference](reference/logging.md) - Structured logging
- [Python Tool Structure](reference/python-tool-structure.md) - Package design

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
- **Issues**: Check [Troubleshooting](operations/troubleshooting.md)
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
