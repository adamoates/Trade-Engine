# Trade Fingerprint & Alert System

**Last Updated**: 2025-10-23
**Category**: Architecture
**Status**: Proposed - In Analysis
**Target User**: Naive traders (beginners, no coding background)

---

## Executive Summary

**Concept Shift**: From automated trading bot → AI Trading Coach

Instead of executing trades automatically, the system:
1. **Learns** from the trader's past successful trades (via Robinhood emails)
2. **Monitors** live market conditions in real-time
3. **Alerts** when current conditions match past winning setups
4. **Coaches** the trader on rule adherence and performance patterns

**Key Insight**: Most traders fail due to lack of discipline, not lack of strategy. This tool enforces their own rules by showing them when they followed/broke them.

---

## Problem Statement

### What Naive Traders Actually Want

**NOT this** (what we built):
- Complex backtesting frameworks
- Automated order execution
- Advanced technical indicators
- Python scripts and Makefiles

**THIS instead** (what they need):
1. "What do I do next?" → Clear action items
2. "Am I following my own rules?" → Rule adherence tracking
3. "Am I improving?" → Performance coaching
4. "When should I trade?" → Real-time alerts for winning setups

### The Emotional Hook

Traders don't get excited by "90% backtest accuracy."

They get excited by **insight** they can understand:
- "You trade better when volatility is low"
- "You exit too early in trending markets"
- "You missed 3 winning setups last week because of rule #2"

**Our tool delivers**: Self-awareness through data.

---

## Core Concept: Trade Fingerprints

### What is a Trade Fingerprint?

A "fingerprint" captures the **complete market context** at the moment a trade was entered:

```json
{
  "trade_id": "RH-2025-10-21-12345",
  "symbol": "BTCUSDT",
  "timestamp_utc": "2025-10-21T14:15:00Z",
  "side": "buy",
  "entry_price": 67450.0,
  "pnl_after_24h_pct": 0.85,

  "regime": "TRENDING",
  "direction": "UP",

  "features": {
    "ma20_ratio": 1.013,        # close / MA(20)
    "ma50_ratio": 1.021,        # close / MA(50)
    "ma_slope_3": 0.0018,       # 3-bar MA slope
    "rsi14": 57.2,
    "roc5": 0.0042,             # 5-bar rate of change
    "atr_pct": 0.32,            # ATR as % of price
    "atr_pctile_60d": 0.61,     # ATR percentile (60 days)
    "vol_ratio20": 1.25,        # volume / 20-bar avg
    "hour_utc": 14,
    "dow": 2                    # day of week (0=Mon)
  },

  "outcome": {
    "max_profit_pct": 1.2,
    "max_drawdown_pct": -0.3,
    "hold_duration_hours": 18,
    "exit_reason": "take_profit"
  }
}
```

### How Fingerprints Are Used

**Historical Analysis**:
- Import Robinhood trade emails
- Fetch market data for each trade timestamp
- Extract features (regime, indicators, context)
- Label winners vs losers
- Identify patterns in winning trades

**Live Monitoring**:
- Fetch current market bar every 15 minutes
- Extract same features from live data
- Compare to library of winning fingerprints
- Alert when similarity > threshold (e.g., 82%)

**Coaching**:
- "This looks like your Oct 21 trade (85% similar)"
- "That trade made +0.85% in 18 hours"
- "Your rules say: Enter with 0.5% stop, 1.5% target"

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Trade Fingerprint System                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. IMPORT                                                    │
│     ┌─────────────────┐                                      │
│     │ Robinhood Email │──┐                                   │
│     │ Parser          │  │                                   │
│     └─────────────────┘  │                                   │
│                           ▼                                   │
│     ┌──────────────────────────────────┐                     │
│     │ Trade Database (JSON/SQLite)     │                     │
│     │ - Trade ID, timestamp, symbol    │                     │
│     │ - Entry/exit prices              │                     │
│     │ - P&L, outcome                   │                     │
│     └──────────────────────────────────┘                     │
│                           │                                   │
│  2. ENRICH                │                                   │
│     ┌─────────────────┐  │                                   │
│     │ Market Data     │◀─┘                                   │
│     │ Fetcher         │                                      │
│     │ (Binance/Yahoo) │                                      │
│     └─────────────────┘                                      │
│                           │                                   │
│     ┌─────────────────┐  │                                   │
│     │ Feature         │◀─┘                                   │
│     │ Extractor       │                                      │
│     │ (Regime, MAs,   │                                      │
│     │  RSI, ATR)      │                                      │
│     └─────────────────┘                                      │
│                           │                                   │
│     ┌──────────────────────────────────┐                     │
│     │ Fingerprint Library              │                     │
│     │ - Winning trades (filtered)      │                     │
│     │ - Feature vectors + metadata     │                     │
│     └──────────────────────────────────┘                     │
│                                                               │
│  3. MONITOR                                                   │
│     ┌─────────────────┐                                      │
│     │ Live Data       │──┐                                   │
│     │ Feed (15m bars) │  │                                   │
│     └─────────────────┘  │                                   │
│                           ▼                                   │
│     ┌─────────────────────────────────┐                      │
│     │ Similarity Matcher              │                      │
│     │ - Weighted cosine distance      │                      │
│     │ - Hard filters (regime, dir)    │                      │
│     │ - Threshold-based alerts        │                      │
│     └─────────────────────────────────┘                      │
│                           │                                   │
│  4. ALERT                 │                                   │
│     ┌─────────────────┐  │                                   │
│     │ Notification    │◀─┘                                   │
│     │ Engine          │                                      │
│     │ (Telegram/Email)│                                      │
│     └─────────────────┘                                      │
│                           │                                   │
│  5. COACH                 │                                   │
│     ┌─────────────────┐  │                                   │
│     │ Dashboard       │◀─┘                                   │
│     │ (Streamlit)     │                                      │
│     │ - Alerts        │                                      │
│     │ - Rule adherence│                                      │
│     │ - Performance   │                                      │
│     └─────────────────┘                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## User Experience Design

### Persona: "Alex" - The Naive Trader

**Background**:
- Trades crypto on Robinhood (mobile app)
- Wins some, loses some, no clear pattern
- Wants to improve but doesn't know how
- No coding experience
- Has a trading "system" (written rules) but struggles to follow it

**Pain Points**:
- Can't track if following own rules
- Misses good setups (doesn't watch market 24/7)
- Enters at wrong times (FOMO, boredom)
- No feedback loop (doesn't learn from mistakes)

**Dream Outcome**:
- Alerts when conditions match past winners
- Dashboard showing rule adherence %
- Weekly email: "Here's what you did well/poorly"
- Confidence to stick to the plan

---

### User Journey: Day-to-Day

**Week 1: Setup (One-Time)**

**Monday Morning** (5 minutes):
```
Alex opens laptop:
$ mft setup

Welcome to MFT Trading Coach!

Let's import your Robinhood trades:
1. Forward trade emails to: mft@example.com
   OR
2. Paste email text here: [text area]

> Alex forwards 50 trade emails

✅ 47 trades imported (3 failed to parse - review manually)
✅ Fetched market data for all trades
✅ Built 22 winning trade fingerprints

Next: Set up alerts
```

**Monday Afternoon** (2 minutes):
```
$ mft configure

What would you like to monitor?
Symbols: [BTCUSDT, ETHUSDT, SOLUSDT]
Alert me via:
  [x] Telegram (bot link: t.me/mft_bot)
  [ ] Email
  [ ] SMS

Monitoring started! Check dashboard: http://localhost:8501
```

---

**Week 2+: Daily Use**

**Tuesday 2:15 PM** - Alex's phone buzzes:

```
🎯 MFT Alert: BTCUSDT Setup

Conditions match your Oct 21 trade (85% similar)
That trade: +0.85% in 18 hours

Current Setup:
  Price: $67,450
  Regime: TRENDING UP
  RSI: 57 (neutral)
  ATR: 0.32% (moderate volatility)

Your Rules Say:
  ✅ Enter: YES (all filters passed)
  📊 Size: 0.01 BTC ($674)
  🛑 Stop: $66,450 (-1.5%)
  🎯 Target: $68,450 (+1.5%)

View full analysis: [link]
```

Alex opens Robinhood, places trade manually (not automated!).

---

**Wednesday Evening** - Alex opens dashboard:

```
┌─────────────────────────────────────────────────────────────┐
│                     MFT Trading Coach                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  This Week's Performance                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  Trades: 3                                                    │
│  Win Rate: 67% (2 wins, 1 loss)                              │
│  Avg P&L: +0.4%                                               │
│                                                               │
│  Rule Adherence                                               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  ✅ Followed Rules: 2/3 (67%)                                │
│  ⚠️  Broke Rules: 1/3 (33%)                                  │
│                                                               │
│  What Went Well                                               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  • Trade #1: Entered in TRENDING regime (correct!)           │
│  • Trade #2: Hit take profit (followed plan)                 │
│                                                               │
│  What to Improve                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  ⚠️  Trade #3: Entered during RANGING (rule violation)      │
│     → Lost -0.5% (stop hit)                                  │
│     → Lesson: Wait for TRENDING regime confirmation          │
│                                                               │
│  Missed Opportunities (Alerts You Didn't Take)               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━                               │
│  • Oct 23, 10:15 AM: ETHUSDT setup (would have made +1.2%)   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

**Sunday Night** - Alex gets email:

```
Subject: Your Weekly Trading Performance Summary

Hi Alex,

Here's how you did this week:

✅ 3 trades analyzed
📊 Rule adherence: 67%
💸 Avg P&L: +0.4%

⚠️ You entered 1 trade outside defined regime conditions
   (Oct 23, BTCUSDT - lost -0.5%)

📈 Best setup: BTC Trend Follow (2 wins, 0 losses)
💤 Avoid: ETH mean-reversion (0 wins, 1 loss)

Next week's focus:
- Be patient: Wait for TRENDING regime confirmation
- Review your rule #3 before entering

Keep improving!
MFT Trading Coach
```

---

## Technical Implementation

### Phase 1: Email Parser & Import (Week 1)

**Components**:
1. Robinhood email parser (regex-based)
2. Trade database (JSON or SQLite)
3. Market data fetcher (reuse existing tools)
4. Feature extractor (reuse regime detection)

**New Files**:
```
app/
  importers/
    robinhood_email.py      # Parse trade emails
    trade_db.py             # Simple JSON/SQLite storage
  features/
    extractor.py            # Build fingerprints
    library.py              # Manage fingerprint collection
```

**Example Trade Record**:
```json
{
  "id": "RH-2025-10-21-12345",
  "source": "robinhood_email",
  "symbol": "BTC",
  "side": "buy",
  "timestamp": "2025-10-21T14:15:00Z",
  "entry_price": 67450.0,
  "exit_price": 67900.0,
  "qty": 0.01,
  "pnl_usd": 4.50,
  "pnl_pct": 0.67,
  "hold_duration_hours": 6.5,
  "exit_reason": "manual",
  "tags": ["winner", "trending_setup"]
}
```

---

### Phase 2: Fingerprint Builder (Week 1-2)

**Reuse Existing Infrastructure**:
- ✅ `tools/fetch_binance_ohlcv.py` - Get historical bars
- ✅ `scripts/detect_regimes.py` - Regime classification
- ✅ Strategy indicators (MA, RSI, ATR, etc.)

**New Component**: Feature Extraction Pipeline

```python
# app/features/extractor.py
def build_fingerprint(trade, ohlcv_bars):
    """
    Extract features from market data at trade timestamp.

    Args:
        trade: Trade record (from email parser)
        ohlcv_bars: DataFrame of OHLCV data around trade time

    Returns:
        Fingerprint dict with regime + features
    """
    # Get bar at trade timestamp
    bar = ohlcv_bars.loc[trade.timestamp]

    # Extract features
    features = {
        # Price vs MAs
        "ma20_ratio": bar.close / bar.ma20,
        "ma50_ratio": bar.close / bar.ma50,
        "ma_slope_3": (bar.ma20 - bar.ma20.shift(3)) / bar.ma20,

        # Momentum
        "rsi14": bar.rsi14,
        "roc5": (bar.close - bar.close.shift(5)) / bar.close.shift(5),
        "macd_hist": bar.macd_hist,

        # Volatility
        "atr_pct": bar.atr / bar.close,
        "atr_pctile_60d": percentile_rank(bar.atr, window=60),

        # Volume
        "vol_ratio20": bar.volume / bar.volume.rolling(20).mean(),

        # Time context
        "hour_utc": bar.timestamp.hour,
        "dow": bar.timestamp.dayofweek
    }

    return {
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "timestamp_utc": trade.timestamp,
        "regime": bar.regime,  # From regime detection
        "direction": "UP" if features["ma_slope_3"] > 0 else "DOWN",
        "features": features,
        "outcome": {
            "pnl_pct": trade.pnl_pct,
            "hold_duration_hours": trade.hold_duration_hours
        }
    }
```

---

### Phase 3: Similarity Matching (Week 2)

**Weighted Cosine Distance**:

```python
# app/features/matcher.py
import numpy as np

FEATURE_WEIGHTS = {
    "ma20_ratio": 2.0,      # Price position critical
    "ma50_ratio": 1.5,
    "ma_slope_3": 2.0,      # Direction critical
    "rsi14": 1.0,
    "roc5": 1.5,
    "atr_pct": 1.5,
    "atr_pctile_60d": 1.0,
    "vol_ratio20": 1.0,
    "hour_utc": 0.5,        # Less important
    "dow": 0.5
}

def weighted_cosine_similarity(current, template, weights):
    """
    Calculate weighted cosine similarity between two fingerprints.

    Returns:
        float: Similarity score (0.0 to 1.0, higher = more similar)
    """
    # Extract feature vectors
    keys = weights.keys()
    curr_vec = np.array([current["features"][k] for k in keys])
    tmpl_vec = np.array([template["features"][k] for k in keys])
    weight_vec = np.array([weights[k] for k in keys])

    # Apply weights
    curr_weighted = curr_vec * weight_vec
    tmpl_weighted = tmpl_vec * weight_vec

    # Cosine similarity
    dot_product = (curr_weighted * tmpl_weighted).sum()
    norm_product = np.linalg.norm(curr_weighted) * np.linalg.norm(tmpl_weighted)

    if norm_product == 0:
        return 0.0

    return dot_product / norm_product

def find_matches(current_fingerprint, template_library, threshold=0.82):
    """
    Find all template fingerprints matching current conditions.

    Args:
        current_fingerprint: Current market fingerprint
        template_library: List of winning trade fingerprints
        threshold: Minimum similarity score (0.0-1.0)

    Returns:
        List of (template, score) tuples, sorted by score descending
    """
    matches = []

    for template in template_library:
        # Hard filters (must match exactly)
        if current_fingerprint["regime"] != template["regime"]:
            continue

        if np.sign(current_fingerprint["features"]["ma_slope_3"]) != \
           np.sign(template["features"]["ma_slope_3"]):
            continue

        # Similarity score
        score = weighted_cosine_similarity(current_fingerprint, template, FEATURE_WEIGHTS)

        if score >= threshold:
            matches.append((template, score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches
```

---

### Phase 4: Live Monitoring & Alerts (Week 2-3)

**Bar-Close Polling**:

```python
# app/monitor/live_scanner.py
import time
from datetime import datetime, timedelta
from app.features.extractor import build_fingerprint
from app.features.matcher import find_matches
from app.features.library import load_template_library
from app.notifiers.telegram import send_telegram_alert

def monitor_live(config):
    """
    Poll market data every bar close, check for matches.

    Args:
        config: Configuration dict (symbols, interval, threshold, etc.)
    """
    symbols = config["symbols"]
    interval = config["interval"]  # e.g., "15m"
    threshold = config["similarity_threshold"]

    # Load winning trade templates
    templates = load_template_library("data/fingerprints/winners.json")

    # Track last alert time (cooldown)
    last_alert = {}

    while True:
        # Wait for next bar close
        wait_for_bar_close(interval)

        # Fetch latest bars for all symbols
        for symbol in symbols:
            bars = fetch_latest_bars(symbol, interval, lookback=100)

            # Extract current fingerprint
            current = build_fingerprint_from_bars(bars)

            # Find matches
            matches = find_matches(current, templates, threshold=threshold)

            # Alert if match found (with cooldown)
            if matches and should_alert(symbol, last_alert, config["cooldown_bars"]):
                top_match, score = matches[0]
                send_alert(symbol, current, top_match, score, config)
                last_alert[symbol] = datetime.utcnow()

        # Sleep until next check (poll every minute, wait for bar close)
        time.sleep(60)

def wait_for_bar_close(interval):
    """Sleep until next bar close."""
    # Parse interval (e.g., "15m" -> 15 minutes)
    minutes = int(interval.rstrip("m"))

    now = datetime.utcnow()
    next_close = now.replace(second=0, microsecond=0)
    next_close += timedelta(minutes=minutes - (now.minute % minutes))

    sleep_seconds = (next_close - now).total_seconds()
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
```

---

### Phase 5: Streamlit Dashboard (Week 3)

**Interactive UI for Traders**:

```python
# app/dashboard.py
import streamlit as st
import pandas as pd
from app.features.library import load_template_library, load_trade_history
from app.features.matcher import find_matches

st.set_page_config(page_title="MFT Trading Coach", layout="wide")

st.title("🎯 MFT Trading Coach")

# Sidebar: Configuration
with st.sidebar:
    st.header("Settings")
    symbols = st.multiselect("Symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], default=["BTCUSDT"])
    threshold = st.slider("Alert Threshold", 0.70, 0.95, 0.82, 0.01)

    if st.button("Refresh Data"):
        st.cache_data.clear()

# Main: Performance Summary
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Trades This Week", "3")
    st.metric("Win Rate", "67%", "+5%")

with col2:
    st.metric("Avg P&L", "+0.4%")
    st.metric("Rule Adherence", "67%", "-10%")

with col3:
    st.metric("Best Setup", "BTC Trend Follow")
    st.metric("Worst Setup", "ETH Mean Reversion")

# Trade History
st.header("Recent Trades")
trades = load_trade_history()
df = pd.DataFrame(trades)
st.dataframe(df[["timestamp", "symbol", "side", "pnl_pct", "regime", "rule_adherence"]])

# Fingerprint Library
st.header("Winning Trade Templates")
templates = load_template_library("data/fingerprints/winners.json")

template_id = st.selectbox("Select Template", [t["trade_id"] for t in templates])
template = next(t for t in templates if t["trade_id"] == template_id)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Trade Details")
    st.write(f"**Symbol**: {template['symbol']}")
    st.write(f"**Regime**: {template['regime']}")
    st.write(f"**P&L**: +{template['outcome']['pnl_pct']:.2f}%")

with col2:
    st.subheader("Features")
    st.json(template["features"])

# Live Monitoring
st.header("Current Market Conditions")

if st.button("Check for Matches Now"):
    current = build_current_fingerprint(symbols[0])  # TODO: implement
    matches = find_matches(current, templates, threshold=threshold)

    if matches:
        st.success(f"✅ Found {len(matches)} matching setups!")
        for template, score in matches[:3]:
            st.write(f"- {template['trade_id']} (similarity: {score:.2%})")
    else:
        st.info("No matches found. Keep monitoring...")
```

---

## Anti-Noise & Safety Mechanisms

### 1. Cool-down Periods
```python
cooldown_bars = 4  # No alerts for 4 bars after last alert
```

### 2. Regime Hysteresis
```python
# Require regime stable for 2-3 bars before alerting
if regime_stable_for_n_bars(current, n=2):
    # OK to alert
```

### 3. Cost Sanity Check
```python
# Only alert if expected TP >= 2-3× round-trip cost
expected_tp = template["outcome"]["pnl_pct"]
min_tp = config["costs"]["roundtrip_bps"] * config["min_tp_multiple"]

if expected_tp < min_tp:
    # Skip alert (not worth the fees)
```

### 4. Daily Alert Cap
```python
max_alerts_per_day = 5
alerts_today = count_alerts_today()

if alerts_today >= max_alerts_per_day:
    # Stop alerting until tomorrow
```

### 5. Audit Log
```python
# Log every alert decision
log_entry = {
    "timestamp": datetime.utcnow().isoformat(),
    "symbol": symbol,
    "current_fingerprint": current,
    "matched_template": template["trade_id"],
    "similarity_score": score,
    "alert_sent": True,
    "trader_action": None  # Filled in later
}

append_to_jsonl("logs/alerts.jsonl", log_entry)
```

---

## Configuration File

```yaml
# app/config/fingerprint_monitor.yaml

# Symbols to monitor
symbols:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT

# Bar interval
interval: 15m

# Matching parameters
similarity_threshold: 0.82

# Hard filters
must_match:
  regime: true           # Regime must match exactly
  direction: true        # MA slope direction must match

# Safety controls
cooldown_bars: 4         # Bars between alerts
max_alerts_per_day: 5
min_tp_vs_cost: 2.0      # Alert only if TP >= 2× costs

# Notification channels
notify:
  telegram:
    enabled: true
    bot_token: ${TG_BOT_TOKEN}
    chat_id: ${TG_CHAT_ID}

  email:
    enabled: false
    smtp_server: smtp.gmail.com
    smtp_port: 587
    from: alerts@mft.com
    to: trader@example.com

# Costs (for sanity checks)
costs:
  roundtrip_bps: 17      # Spot: 17 bps total

# Data sources
data:
  market_data_provider: binance
  trade_history_path: data/trades/history.json
  fingerprint_library_path: data/fingerprints/winners.json
```

---

## Cross-Reference with Existing Infrastructure

### What We Reuse (No Changes)

| Component | Existing File | How It's Reused |
|-----------|---------------|-----------------|
| Market data fetching | `tools/fetch_binance_ohlcv.py` | Get historical bars for trade timestamps |
| Data validation | `tools/validate_clean_ohlcv.py` | Ensure quality of fetched bars |
| Regime detection | `scripts/detect_regimes.py` | Label regime for each fingerprint |
| Indicators | `strategies/implementations/trending_strategy_v3.py` | Extract MA, RSI, ATR features |
| Makefile | `Makefile` | Add new targets (`make import-trades`, `make monitor`, `make dashboard`) |

### What's New

| Component | New File | Purpose |
|-----------|----------|---------|
| Email parser | `app/importers/robinhood_email.py` | Parse trade emails |
| Trade database | `app/importers/trade_db.py` | Store trades (JSON/SQLite) |
| Feature extractor | `app/features/extractor.py` | Build fingerprints |
| Fingerprint library | `app/features/library.py` | Manage templates |
| Similarity matcher | `app/features/matcher.py` | Find matches |
| Live monitor | `app/monitor/live_scanner.py` | Poll & alert |
| Dashboard | `app/dashboard.py` | Streamlit UI |
| Telegram notifier | `app/notifiers/telegram.py` | Send alerts |

---

## Success Criteria

### MVP (Minimum Viable Product) - Week 3

**Must Have**:
- ✅ Import 50+ trades from Robinhood emails
- ✅ Build fingerprints for all trades
- ✅ Identify top 10 winning templates
- ✅ Monitor 3 symbols live (15m bars)
- ✅ Alert when similarity > 82%
- ✅ Telegram notifications working
- ✅ Basic Streamlit dashboard

**Success Metrics**:
- Alert latency < 60 seconds from bar close
- False positive rate < 20% (trader agrees with 80%+ of alerts)
- Dashboard loads < 2 seconds

---

### Phase 2 - Week 4-6

**Enhanced Features**:
- Rule adherence tracking
- Performance coaching (weekly emails)
- Multi-symbol monitoring (10+ symbols)
- Historical backtest: "If I followed all alerts, what would P&L be?"
- Mobile-friendly dashboard

**Success Metrics**:
- Trader uses dashboard 3+ times per week
- Takes action on 50%+ of alerts
- Self-reported: "Helps me stick to my plan"

---

## Next Steps

### Immediate (This Week)

1. **Create new branch**:
   ```bash
   git checkout -b feature/trade-fingerprint-coach
   ```

2. **Implement Email Parser** (1-2 days)
   - Parse Robinhood trade confirmation emails
   - Extract: symbol, side, timestamp, prices, qty
   - Store in JSON database

3. **Implement Feature Extractor** (1-2 days)
   - Reuse regime detection + indicator calculations
   - Build fingerprint for each historical trade
   - Filter to winning trades only

4. **Implement Matcher** (1 day)
   - Weighted cosine similarity
   - Hard filters (regime, direction)
   - Return top N matches

5. **Build Basic Dashboard** (1-2 days)
   - Streamlit app
   - Show trade history
   - Show fingerprint library
   - Manual "check for matches" button

---

### Week 2-3

1. **Live Monitoring** (2-3 days)
   - Bar-close polling
   - Auto-match checking
   - Cooldown + safety controls

2. **Telegram Alerts** (1 day)
   - Bot setup
   - Alert formatting
   - Delivery confirmation

3. **Testing** (2-3 days)
   - Test with real Robinhood emails
   - Validate fingerprint matching
   - Tune similarity threshold

---

## Conclusion

This system transforms MFT from an **automated trading bot** (risky, complex) into an **AI Trading Coach** (safe, educational, valuable).

**Key Benefits**:
- ✅ No live trading risk (alerts only)
- ✅ No broker API dependency (email + public data)
- ✅ Psychologically safe (teaches discipline)
- ✅ Scalable (add semi-automation later)
- ✅ Reuses 80% of existing infrastructure

**Target User**: Beginners who want to improve, not programmers who want to automate.

**Unique Value**: Self-awareness through data - "This is what you actually did vs what you should have done."

---

**Status**: Ready to implement
**Branch**: `feature/trade-fingerprint-coach` (to be created)
**Timeline**: 3-6 weeks for MVP
**Stakeholder Approval**: Pending

---

**Credit**: Concept based on user-provided "trade fingerprint & alert system" design.
