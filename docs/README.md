# MFT Bot Documentation

This directory contains all project documentation organized by purpose and use case.

## Documentation Structure

```
docs/
├── README.md              # This file - documentation index
├── deployment.md          # Production deployment overview
├── guides/                # Comprehensive reference guides
│   ├── README.md          # Guide directory index
│   ├── ci-cd-setup.md     # Quick-start CI/CD setup
│   ├── data-pipeline-guide.md      # Complete data pipeline workflows
│   ├── data-validation-guide.md    # Data quality and cleaning
│   ├── development-workflow.md     # Daily development practices
│   ├── github-actions-guide.md     # Complete GitHub Actions reference
│   ├── pipeline-one-liners.md      # Quick copy-paste commands
│   ├── project-setup-checklist.md  # Environment setup checklist
│   ├── python-tool-structure.md    # Python packaging and tool design
│   ├── using-test-fixtures.md      # Historical test data usage
│   └── web3-signals.md             # Web3 on-chain signals guide
```

## Quick Start

### New to the Project?
1. Read: **CLAUDE.md** (project root) - Project overview and critical rules
2. Read: **ROADMAP.md** (project root) - Development phases and current status
3. Follow: **guides/project-setup-checklist.md** - Set up your environment
4. Study: **guides/development-workflow.md** - Learn daily development practices

### Setting Up CI/CD?
1. Quick start: **guides/ci-cd-setup.md**
2. Deep dive: **guides/github-actions-guide.md**
3. Deploy: **deployment.md**

### Ready to Code?
1. Review: **CLAUDE.md** - Code standards and patterns
2. Follow: **guides/development-workflow.md** - Git workflow, testing, code review
3. Use: `./scripts/run-ci-checks.sh` - Local quality checks before pushing

## Primary Documentation Sources

### Project Root Files
- **CLAUDE.md** - AI assistant context, project overview, code standards, critical rules
- **ROADMAP.md** - 7-phase development plan with phase gates and milestones
- **README.md** - Project introduction

### Planning Documents (`/Users/adamoates/Documents/trader/`)
Complete technical specifications and research:
- **mft-architecture.md** - Three-layer system design, component specs, technology stack
- **mft-strategy-spec.md** - L2 imbalance strategy, entry/exit logic, parameters
- **mft-risk-management.md** - Risk limits, kill switch procedures, safety framework
- **mft-roadmap.md** - Detailed phase-by-phase development plan
- **mft-research-questions.md** - Strategy validation and research methodology
- **mft-dev-log.md** - Development journal template

### This Directory (`docs/`)
- **deployment.md** - Production deployment overview and procedures
- **guides/** - Comprehensive operational guides (see below)

## Comprehensive Guides (`docs/guides/`)

Detailed reference documentation for major topics:

### 🚀 **ci-cd-setup.md**
Quick-start guide for GitHub Actions setup
- Step-by-step setup instructions
- Required secrets configuration
- Branch protection setup
- Troubleshooting common issues

### 📊 **data-pipeline-guide.md**
Complete data pipeline from fetch to backtest
- Quick start with Makefile targets
- Complete workflows (fetch → validate → detect → backtest)
- Piped workflows for speed
- Troubleshooting and performance benchmarks

### 🧹 **data-validation-guide.md**
Production-grade OHLCV data validation and cleaning
- Why data validation matters (found 13% corrupt bars)
- Validation checks (gaps, duplicates, zero-volume)
- Cleaning options (drop, ffill, nan)
- Cost modeling for backtests
- Quality reporting and best practices

### 📦 **github-actions-guide.md**
Complete GitHub Actions reference
- Workflow architecture explanation
- Phase-by-phase activation guide
- Best practices and conventions
- Advanced configuration options
- Comprehensive troubleshooting

### ⚡ **pipeline-one-liners.md**
Quick copy-paste commands for data pipeline workflows
- Makefile shortcuts (make full, make pipe)
- Pure Python one-liners (no Makefile required)
- Complete pipelines (fetch → validate → detect → backtest)
- Binance.US domain override examples
- Custom cost assumption examples

### 📋 **project-setup-checklist.md**
Complete environment setup from scratch
- Prerequisites and software installation
- Repository and GitHub configuration
- Local development environment
- VPS and exchange setup
- First feature verification

### 🐍 **python-tool-structure.md**
Understanding Python tool structure and package design
- Current architecture analysis (script-based tools)
- Python tool structure patterns (script vs library vs framework)
- When to refactor to library + CLI
- Industry examples and best practices
- Proposed evolution path for MFT project

### 🔧 **development-workflow.md**
Daily development practices and workflows
- Daily development cycle
- Git workflow and branching strategy
- Code review process
- Testing strategy and practices
- Documentation practices
- Team collaboration patterns

### 🧪 **using-test-fixtures.md**
Using historical test data instead of mocked data
- Why use real historical cryptocurrency data
- Generating fixtures from free public APIs
- Available fixtures (Binance.US, CoinGecko, anomalies)
- Helper functions for loading fixture data
- Migration guide from mocked to real data

### ⛓️ **web3-signals.md**
Web3 on-chain signals for trading enhancement
- Reading blockchain data for trading signals (100% free)
- Gas prices, DEX liquidity, funding rates
- Signal scoring and combination logic
- Integration with L2 order book strategy
- Volatility detection and position sizing

## Quick Reference

### Strategy Core Parameters
- **Buy Threshold**: 3.0x bid/ask volume ratio
- **Sell Threshold**: 0.33x bid/ask volume ratio
- **Imbalance Depth**: Top 5 levels
- **Profit Target**: 0.2% (20 basis points)
- **Stop Loss**: -0.15% (15 basis points)
- **Time Stop**: 60 seconds max hold

### Hard Risk Limits (NON-NEGOTIABLE)
- **Max Position Size**: $10,000
- **Daily Loss Limit**: -$500 (triggers kill switch)
- **Max Drawdown**: -$1,000 from peak (triggers kill switch)
- **Per-Instrument Exposure**: 25% of total capital

### Performance Targets
- **Message Processing**: <5ms
- **Order Book Update**: <2ms
- **Order Placement**: <20ms
- **Total Latency**: <50ms sustained

### Expected Performance (Based on Academic Research)
- **Win Rate**: 52-58% (target 55%+)
- **Profit Factor**: >1.2
- **Sharpe Ratio**: >1.5
- **Daily P&L**: $50-100 on $10K capital

## Development Commands

```bash
# Setup
./scripts/run-ci-checks.sh       # Local CI simulation

# Testing
pytest tests/ -v                  # All tests
pytest --cov=engine --cov=api -v  # With coverage

# Code Quality
black engine/ api/ tests/         # Format code
ruff check engine/ api/ tests/    # Lint code
mypy engine/ api/                 # Type check

# Git Workflow
git checkout -b feature/name      # Create feature branch
gh pr create                      # Create pull request
```

## Documentation Maintenance

### Update Schedule
- **Daily**: Update ROADMAP.md current status as you progress
- **Weekly**: Review and update guides with learnings
- **Phase Completion**: Add phase-specific documentation
- **After Incidents**: Document new procedures and lessons learned

### Contributing to Documentation
When adding new documentation:
1. **Guides** (`docs/guides/`) - For comprehensive, procedural documentation >500 lines
2. **Root docs** (`docs/`) - For high-level overviews and quick references
3. **Code comments** - For implementation details and API documentation
4. **CLAUDE.md** - For AI assistant context and coding patterns

## Related Resources

### GitHub Actions
- Workflows: `.github/workflows/`
- CI Quality Gate: `.github/workflows/ci-quality-gate.yml`
- CD Deployment: `.github/workflows/cd-deploy.yml`

### Scripts
- Local CI checks: `scripts/run-ci-checks.sh`

### Configuration
- Claude Code settings: `.claude/settings.json`
- Custom commands: `.claude/commands/`
- Specialized agents: `.claude/agents/`

---

**Remember**: Documentation is a living artifact. Keep it updated as the project evolves, add real troubleshooting examples, and remove outdated information promptly.
