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
