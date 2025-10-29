# Paper Trading & Integration Testing Guide

Complete guide for testing the L2 Order Book Imbalance strategy before live trading.

---

## Overview

This guide covers three types of testing:

1. **Integration Demos** - Short-term testing (minutes to hours) to verify system functionality
2. **Paper Trading Validation** - Long-term testing (60 days) to validate strategy edge
3. **Live Trading Preparation** - Final steps before risking real capital

---

## Part 1: Integration Testing

### Purpose

Verify that all components work together correctly:
- L2 data feed (WebSocket connections)
- Strategy signal generation
- Risk management
- Broker API integration
- System performance (<50ms latency target)

### Available Demos

#### 1. Kraken Futures Integration Demo (Recommended for US Traders)

**Features:**
- ✅ US-accessible
- ✅ Demo environment (no real money)
- ✅ Full L2 strategy (long + short)
- ✅ Free to test

**Setup:**
```bash
# 1. Get Kraken Futures Demo credentials
# Go to: https://demo-futures.kraken.com/
# Create account (auto-generates demo funds)
# Generate API keys with "Full Access"

# 2. Add to .env file
echo "KRAKEN_DEMO_API_KEY=your_demo_key" >> .env
echo "KRAKEN_DEMO_API_SECRET=your_demo_secret" >> .env

# 3. Run dry-run test (monitor only)
python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 60 --dry-run

# 4. Run live demo (demo funds, not real money)
python tools/demo_kraken_l2_integration.py --symbol PF_XBTUSD --duration 300 --live
```

**Expected Output:**
```
================================================================================
STARTING KRAKEN FUTURES L2 DEMO
================================================================================
Kraken L2 Demo initialized | Symbol: PF_XBTUSD | Mode: LIVE DEMO | Duration: 300s
Connected to Kraken Futures DEMO
Order book snapshot loaded: 50 bids, 50 asks
WebSocket connected

SIGNAL #1: BUY | Price: 43500.5 | Qty: 0.0023 | Reason: Strong bullish imbalance (3.2x)
BUY executed | Order ID: 12345

STATE | Imbalance: 1.85 | Mid: 43520.0 | Spread: 0.05 bps | Signals: 1 | Latency: 3.42ms

SIGNAL #2: CLOSE | Price: 43580.0 | Qty: 0.0023 | Reason: Take profit hit (+0.20%)
Position CLOSED

================================================================================
KRAKEN DEMO COMPLETE
================================================================================
Duration: 300.0s
Signals Generated: 5
Trades Executed: 3 (LIVE DEMO)
Performance:
  Avg Latency: 4.12ms
  P95 Latency: 7.85ms
  Max Latency: 12.30ms
✓ Latency target MET (<50ms)
================================================================================
```

---

#### 2. Binance.us Spot Integration Demo (US-Only, Spot Trading)

**Features:**
- ✅ US-accessible
- ⚠️ **NO TESTNET** - Live mode uses REAL MONEY
- ⚠️ Spot-only (long positions only, no shorting)
- ⚠️ ~50% fewer signals than futures mode

**Setup:**
```bash
# 1. Get Binance.us credentials
# Go to: https://www.binance.us/
# Create account, complete KYC
# Generate API keys with "Enable Trading"

# 2. Add to .env file
echo "BINANCE_US_API_KEY=your_api_key" >> .env
echo "BINANCE_US_API_SECRET=your_api_secret" >> .env

# 3. ALWAYS start with dry-run
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 60 --dry-run

# 4. Live trading (USES REAL MONEY - requires confirmation)
python tools/demo_binanceus_l2_integration.py --symbol BTCUSDT --duration 120 --live --i-understand-this-is-real-money
```

**⚠️ IMPORTANT WARNINGS:**

- **NO TESTNET**: Binance.us does not have a public testnet. Live mode uses REAL MONEY.
- **START SMALL**: Use minimal position sizes ($10-50) for initial testing
- **SPOT-ONLY**: Can only take long positions. Short signals are ignored.
- **50% FEWER SIGNALS**: Bearish L2 imbalances cannot be traded (no shorting)

---

### Integration Testing Checklist

Before moving to paper trading, verify:

- [ ] WebSocket connects successfully
- [ ] Order book data updates in real-time
- [ ] Signals generate correctly (buy/sell/close)
- [ ] Risk manager blocks trades when limits exceeded
- [ ] Broker API executes orders successfully
- [ ] Average latency <50ms sustained
- [ ] System runs for 1+ hour without crashes
- [ ] Kill switch works (stop and flatten positions)

---

## Part 2: Paper Trading Validation (60 Days)

### Purpose

Validate that the strategy has a statistical edge:
- **Gate 5→6 Requirements** (CLAUDE.md):
  - 60 days of continuous paper trading
  - Win rate >50%
  - Profit factor >1.0
  - Confidence that edge exists

### Paper Trading Framework

The `paper_trading_validator.py` script:
- Runs strategy in simulated mode (no real trades)
- Logs all signals and simulated P&L
- Tracks performance metrics
- Persists data in SQLite database
- Generates daily/weekly reports
- Validates Gate 5→6 requirements

---

### Setup: Kraken Futures (Recommended)

```bash
# Start 60-day paper trading session
python tools/paper_trading_validator.py \
  --broker kraken \
  --symbol PF_XBTUSD \
  --session 60days_kraken \
  --duration 1440  # 24 hours per run

# View current statistics
python tools/paper_trading_validator.py --session 60days_kraken --report

# Resume after interruption
python tools/paper_trading_validator.py \
  --broker kraken \
  --symbol PF_XBTUSD \
  --session 60days_kraken \
  --duration 1440
```

**Recommended Setup:**
- Run on a VPS or server (24/7 uptime)
- Use `systemd` or `supervisor` for auto-restart
- Check reports weekly
- Continue until 60 days completed

---

### Setup: Binance.us Spot (Alternative)

```bash
# Start 60-day paper trading session (spot-only mode)
python tools/paper_trading_validator.py \
  --broker binance_us \
  --symbol BTCUSDT \
  --session 60days_binanceus \
  --duration 1440

# View statistics
python tools/paper_trading_validator.py --session 60days_binanceus --report
```

**Note:** Spot-only mode will show ~50% fewer signals. Win rate should still be >50% on the signals that are generated (long entries only).

---

### Expected Results

**After 60 Days:**

```
================================================================================
FINAL PAPER TRADING REPORT - Session: 60days_kraken
================================================================================
Days Running: 60.2 / 60 days required
Total Trades: 347
Winning Trades: 189
Losing Trades: 158
Win Rate: 54.47% (Target: >50%)
Total P&L: $4,235.67
Avg Win: $45.23
Avg Loss: -$32.18
Profit Factor: 1.53 (Target: >1.0)
Max Drawdown: $487.32

Gate 5→6 Requirements:
  [✓] 60 days completed: 60.2 days
  [✓] Win rate >50%: 54.47%
  [✓] Profit factor >1.0: 1.53

================================================================================
✓ ALL GATE 5→6 REQUIREMENTS MET - READY FOR LIVE TRADING
================================================================================
```

**If Requirements NOT Met:**
- Continue paper trading
- Review signals and exits
- Consider parameter tuning
- DO NOT proceed to live trading

---

### Automating Paper Trading (24/7)

#### Option 1: systemd (Linux)

```bash
# Create systemd service
sudo nano /etc/systemd/system/paper-trading.service
```

```ini
[Unit]
Description=L2 Strategy Paper Trading
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Trade-Engine
ExecStart=/path/to/.venv/bin/python tools/paper_trading_validator.py --broker kraken --symbol PF_XBTUSD --session 60days --duration 1440
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable paper-trading
sudo systemctl start paper-trading

# Check status
sudo systemctl status paper-trading

# View logs
sudo journalctl -u paper-trading -f
```

#### Option 2: tmux/screen (Quick Setup)

```bash
# Start tmux session
tmux new -s paper-trading

# Run paper trading
python tools/paper_trading_validator.py --broker kraken --symbol PF_XBTUSD --session 60days --duration 999999

# Detach: Ctrl+B then D
# Reattach: tmux attach -t paper-trading
```

---

## Part 3: Live Trading Preparation

### Prerequisites

Before risking real capital:

1. **Gate 5→6 PASSED**:
   - [ ] 60 days paper trading completed
   - [ ] Win rate >50% achieved
   - [ ] Profit factor >1.0 achieved
   - [ ] Max drawdown acceptable

2. **System Verification**:
   - [ ] Integration tests passed
   - [ ] Kill switch tested and working
   - [ ] API keys secured (not in code)
   - [ ] Risk limits configured correctly
   - [ ] Logging and audit trail enabled

3. **Capital Requirements**:
   - [ ] Minimum $100-500 for micro-capital testing
   - [ ] Willing to lose entire test amount
   - [ ] Not using borrowed or needed funds

---

### Micro-Capital Testing (Gate 6→7)

**Start with minimal capital:**

```bash
# Kraken Futures - $100 capital
python tools/demo_kraken_l2_integration.py \
  --symbol PF_XBTUSD \
  --duration 86400 \  # 24 hours
  --live

# Monitor closely for 30 days
# Target: Break-even or small profit
# Goal: Verify no critical bugs
```

**Risk Limits for Micro-Capital:**
```python
# Update app/constants.py
DEFAULT_MAX_DAILY_LOSS_USD = 50  # $50 max loss per day
DEFAULT_MAX_POSITION_USD = 100   # $100 max position
DEFAULT_MAX_TRADES_PER_DAY = 10  # Limit overtrading
```

---

### Live Trading Best Practices

1. **Start Small**:
   - Use $100-500 for first month
   - Increase capital only after consistent profitability
   - Never risk more than 1-2% per trade

2. **Monitor Continuously**:
   - Check P&L daily
   - Review weekly reports
   - Watch for anomalies or unexpected behavior

3. **Have a Kill Switch Plan**:
   - Know how to stop the bot immediately
   - Can manually close positions if needed
   - Test kill switch monthly

4. **Risk Management**:
   - Never override risk limits
   - Respect daily loss limits
   - Take breaks if losing streak occurs

5. **Record Keeping**:
   - All trades logged to database
   - Track slippage and fees
   - Monthly performance reviews

---

## Troubleshooting

### WebSocket Connection Issues

```bash
# Error: WebSocket timeout or connection refused

# Solution 1: Check network/firewall
ping stream.binance.com

# Solution 2: Use testnet
# Kraken: demo-futures.kraken.com
# Binance: stream.binancefuture.com (testnet)

# Solution 3: Increase timeout
# Edit app/constants.py:
WEBSOCKET_TIMEOUT_SECONDS = 30
```

### API Authentication Errors

```bash
# Error: HTTP 401 or "Invalid API key"

# Solution 1: Verify credentials
cat .env | grep API_KEY

# Solution 2: Check API permissions
# Kraken: Needs "Full Access"
# Binance.us: Needs "Enable Trading"

# Solution 3: Regenerate keys
# Old keys may expire or be revoked
```

### Low Signal Count

```bash
# Issue: Very few signals generating

# Causes:
# 1. Low market volatility (L2 strategy needs volatility)
# 2. Spread filter blocking signals (spread > 50 bps)
# 3. Cooldown period preventing rapid signals

# Solutions:
# 1. Wait for volatile market conditions
# 2. Check imbalance thresholds (may need tuning)
# 3. Review spread filter settings
```

### Database Locked Errors

```bash
# Error: database is locked

# Solution: SQLite doesn't handle concurrent writes well
# Only run ONE paper trading session per database file
# Use different session names for parallel testing:
python tools/paper_trading_validator.py --session 60days_v1 ...
python tools/paper_trading_validator.py --session 60days_v2 ...
```

---

## FAQ

### Q: How long does integration testing take?

**A:** 1-3 hours per demo. Recommended timeline:
- Dry-run: 30-60 minutes
- Live demo (Kraken demo env): 2-4 hours
- Verify latency and stability

### Q: Can I speed up paper trading (less than 60 days)?

**A:** No. Gate 5→6 requires 60 days for statistical validity. You need sufficient sample size to:
- Verify win rate across different market conditions
- Measure max drawdown accurately
- Build confidence in the strategy edge

**Shortcutting this leads to live trading with unvalidated strategy.**

### Q: What if paper trading fails (win rate <50%)?

**A:** DO NOT proceed to live trading. Options:
1. Continue paper trading longer (variance can cause short-term losses)
2. Review and tune strategy parameters
3. Consider that strategy may not have edge (market conditions changed)
4. Research alternative strategies

### Q: Binance.us vs Kraken Futures - which is better?

**A:**
| Feature | Kraken Futures | Binance.us Spot |
|---------|----------------|-----------------|
| **US Access** | ✅ Yes | ✅ Yes |
| **Testnet** | ✅ Yes (free demo) | ❌ No |
| **Can Short** | ✅ Yes | ❌ No |
| **Signals** | 100% (full strategy) | ~50% (long only) |
| **Recommendation** | ⭐ Recommended | Use only if needed |

**Verdict:** Use **Kraken Futures** for full L2 strategy effectiveness.

### Q: How much profit should I expect?

**A:** Conservative estimates (based on $10K capital):
- **Target**: $50-100/day ($1,500-3,000/month)
- **Win Rate**: 52-58% (based on academic research)
- **Profit Factor**: 1.2-1.5 (after fees and slippage)
- **Drawdown**: Expect -$500-1,000 at times

**Reality check:**
- Some days will be negative
- Variance is high in short-term
- 60-day paper trading provides realistic expectations

### Q: What if I don't have 60 days?

**A:** You can run paper trading in parallel with other work. The validator runs autonomously:
- Set up on VPS or home server
- Runs 24/7 automatically
- Check reports weekly
- After 60 days, review results

**Time investment**: ~2 hours setup, ~30 min/week monitoring

---

## Next Steps

1. **Start with Integration Testing**:
   - Run Kraken demo for 2-4 hours
   - Verify all components work
   - Measure latency and stability

2. **Begin 60-Day Paper Trading**:
   - Use `paper_trading_validator.py`
   - Set up automation (systemd/tmux)
   - Check reports weekly

3. **After Gate 5→6 Met**:
   - Start micro-capital testing ($100-500)
   - Monitor for 30 days
   - Scale up if profitable

4. **Production Trading**:
   - Only after successful micro-capital phase
   - Start with conservative position sizes
   - Never stop monitoring

---

## Support

**Issues:**
- GitHub: https://github.com/anthropics/claude-code/issues
- Check logs: All demos log to stderr

**Documentation:**
- Broker comparison: `docs/guides/broker-comparison.md`
- Spot-only mode: `docs/guides/spot-only-trading.md`
- Architecture: `docs/architecture/`

---

**Generated:** 2025-10-29
**Version:** 1.0
