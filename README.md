# MFT Trading Bot

Medium-frequency cryptocurrency trading system using Level 2 order book imbalance detection.

## Current Status

**Phase**: Phase 0 - Infrastructure Setup (Weeks 1-2)
**Week**: Week 1 of 24
**Focus**: ✅ VPS provisioned, 🔄 Recording 24h L2 data

**Current Tech Stack** (Phase 0):
- Python 3.11+
- ccxt (exchange connectivity)
- pandas (data analysis)
- Binance.US (spot market - BTC/USD)

**Infrastructure**:
- VPS: Linode (173.255.230.154)
- Latency: 1.5ms to Binance API ✅
- Recording: BTC/USD L2 order book (5 levels, 1/sec)
- Started: 2025-10-22 11:08 UTC
- Expected completion: 2025-10-23 11:08 UTC

**Future Tech Stack** (Phase 2+):
- asyncio, websockets (Phase 2)
- PostgreSQL (Phase 2)
- FastAPI (Phase 3)
- React (Phase 4)

## Core Strategy

**L2 Order Book Imbalance Detection**
- Buy Signal: Bid/Ask volume ratio > 3.0x
- Sell Signal: Bid/Ask volume ratio < 0.33x
- Target: $50-100/day profit on $10K capital
- Hold Time: 5-60 seconds (medium frequency)

## Project Structure

The system follows **Clean Architecture** with three distinct layers:

### Three-Layer Architecture

**Layer 1: Domain (Business Logic)** - Pure Python
- `src/trade_engine/domain/strategies/` - Trading strategies (12 strategies)
- `src/trade_engine/domain/risk/` - Risk management logic

**Layer 2: Services (Orchestration)** - Application services
- `src/trade_engine/services/trading/` - Live trading engine
- `src/trade_engine/services/backtest/` - Backtesting engine
- `src/trade_engine/services/data/` - Data aggregation

**Layer 3: Adapters (Infrastructure)** - External integrations
- `src/trade_engine/adapters/brokers/` - 4 broker implementations
- `src/trade_engine/adapters/data_sources/` - 5 data providers
- `src/trade_engine/adapters/feeds/` - L2 order book feed

### Directory Overview

```
trade-engine/
├── src/trade_engine/  # Main codebase (Clean Architecture)
│   ├── adapters/     # Brokers, data sources, feeds
│   ├── domain/       # Business logic (strategies, risk)
│   ├── services/     # Trading engine, backtesting
│   └── core/         # Configuration, types, constants
├── tests/            # Test suite (465 tests, 100% passing)
│   ├── unit/        # Unit tests
│   └── integration/ # Integration tests
├── data/             # Market data (CSVs, L2 snapshots, gitignored)
├── logs/             # Runtime logs (gitignored)
├── scripts/          # Development & deployment scripts
├── docs/             # Comprehensive documentation
│   └── guides/      # Setup and workflow guides
├── CLAUDE.md         # Project instructions for Claude Code
├── ROADMAP.md        # 7-phase development plan
└── pytest.ini        # Test configuration
```

## Quick Start

### For Beginners (5-Minute Setup)

**1. Install Python 3.13+**
```bash
python3 --version  # Should be 3.13 or newer
```

**2. Clone & Setup**
```bash
git clone <your-repo-url>
cd MFT
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Get Free Testnet API Keys**
- Visit: https://testnet.binancefuture.com
- Sign up (no real money needed!)
- Go to API Management → Create New Key
- Copy your API Key (64 characters) and Secret (64 characters)

**4. Set Environment Variables**
```bash
export BINANCE_TESTNET_API_KEY="your_64_character_key_here"
export BINANCE_TESTNET_API_SECRET="your_64_character_secret_here"
```

**5. Download Sample Data**
```bash
python tools/fetch_binance_ohlcv.py \
  --market spot \
  --symbol BTCUSDT \
  --interval 15m \
  --days 7 \
  --out data/btc_15m.csv
```

**6. Validate & Clean Data**
```bash
python tools/validate_clean_ohlcv.py \
  data/btc_15m.csv \
  --out data/btc_15m_clean.csv \
  --fill drop \
  --report data/quality_report.json
```

**7. Run Tests**
```bash
pytest tests/unit/ -v
```

### For Developers (Advanced Setup)

See [docs/guides/project-setup-checklist.md](docs/guides/project-setup-checklist.md) for VPS setup, L2 data collection, and production deployment.

### Troubleshooting

**"ModuleNotFoundError: No module named 'requests'"**
→ You forgot to activate the virtual environment. Run: `source .venv/bin/activate`

**"Invalid API key format. Binance API keys should be 64 characters."**
→ Make sure you copied the FULL key from Binance (it's very long!)

**Need Help?**
- Check [docs/guides/](docs/guides/) for detailed guides
- See test report: [docs/TEST_REPORT_2025-10-23.md](docs/TEST_REPORT_2025-10-23.md)
- Review risk management: Tests verify daily loss limits, position sizing, kill switches

## Viewing Results (Live Monitoring)

### 📊 Logs are Your Primary Interface

The bot writes **structured JSON logs** to view all trading activity:

```bash
# View live results (tail logs in real-time)
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq '.'

# Filter specific events
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "signal_generated")'
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "order_placed")'
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "risk_block")'
```

**What's Logged:**
- 📊 Bar events (received, skipped, warnings)
- 🎯 Signal events (generated, risk blocks)
- 📤 Order events (placed, executed, errors)
- ⚠️ Strategy & broker errors
- 🔴 Lifecycle events (shutdown, emergency stop)

**Log Format:** JSON lines in `logs/audit_YYYY-MM-DD.jsonl` (daily rotation)

**Future Monitoring:**
- Phase 3: API endpoints to query results
- Phase 4: React dashboard with live charts

See [CLAUDE.md § Monitoring & Logging](#) for complete log analysis commands.

## Documentation

### 📚 Core Documentation (Single Source of Truth)

- **[README.md](README.md)** - Project overview and quick start (you are here)
- **[ROADMAP.md](ROADMAP.md)** - 7-phase development plan with milestones and gates
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[.claude/CLAUDE.md](.claude/CLAUDE.md)** - AI assistant instructions: coding standards, critical rules, architecture

### 📖 Guides & References

- **[Documentation Guide](docs/reference/documentation-guide.md)** - Where to find and update documentation
- **[Git Workflow](docs/guides/git-workflow.md)** - Branch strategy, commit conventions, PR process
- **[Development Workflow](docs/guides/development-workflow.md)** - Local setup and development
- **[CI/CD Setup](docs/guides/ci-cd-setup.md)** - GitHub Actions and quality gates
- **[All Guides](docs/guides/)** - Complete list of how-to guides

## Development Principles

1. **Phase-Gated Development** - Complete current phase before advancing
2. **YAGNI** - Only add technology when actually needed
3. **Financial Code Safety** - Never use float for money calculations
4. **Risk-First** - Hard limits enforced in code (non-negotiable)

---

**Current Milestone**: Record and validate 24h of clean L2 data (Phase 0 Gate 1)
