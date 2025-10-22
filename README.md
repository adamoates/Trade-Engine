# MFT Trading Bot

Medium-frequency cryptocurrency trading system using Level 2 order book imbalance detection.

## Current Status

**Phase**: Phase 0 - Infrastructure Setup (Weeks 1-2)
**Week**: Week 1 of 24
**Focus**: VPS provisioning, latency testing, 24h L2 data recording

**Current Tech Stack** (Phase 0):
- Python 3.11+
- ccxt (exchange connectivity)
- pandas (data analysis)
- Binance Futures Testnet

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

```
MFT/
├── scripts/           # Phase 0 data collection scripts
├── docs/             # Comprehensive documentation
│   └── guides/       # Setup and workflow guides
├── CLAUDE.md         # AI assistant context
├── ROADMAP.md        # 7-phase development plan
└── requirements.txt  # Phase 0 minimal dependencies
```

## Quick Start

See [docs/guides/project-setup-checklist.md](docs/guides/project-setup-checklist.md) for complete setup instructions.

**Phase 0 Week 1**:
1. Provision VPS (NYC, <50ms to Binance)
2. Run `scripts/setup_vps.sh`
3. Record 24h L2 data: `python scripts/record_l2_data.py`
4. Validate quality: `python scripts/validate_data.py`

## Documentation

- **CLAUDE.md** - Project overview, code standards, critical rules
- **ROADMAP.md** - 7-phase development plan with gates
- **docs/** - Complete documentation index
- **docs/guides/** - Comprehensive setup and workflow guides

## Development Principles

1. **Phase-Gated Development** - Complete current phase before advancing
2. **YAGNI** - Only add technology when actually needed
3. **Financial Code Safety** - Never use float for money calculations
4. **Risk-First** - Hard limits enforced in code (non-negotiable)

---

**Current Milestone**: Record and validate 24h of clean L2 data (Phase 0 Gate 1)
