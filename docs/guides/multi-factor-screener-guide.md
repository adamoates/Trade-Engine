# Multi-Factor Stock Screener Guide

Complete guide to finding stocks with multiple buy signals using the Multi-Factor Screener.

## Overview

The Multi-Factor Screener identifies stocks that match **7 key buy signals**:

1. ✅ **Price Breakout** - Broke above 20-day high
2. ✅ **Volume Surge** - Trading volume 2x+ average
3. ✅ **MA Alignment** - Price > 50MA > 200MA (golden cross)
4. ✅ **MACD Crossover** - MACD line crossed above signal line
5. ✅ **RSI Momentum** - RSI between 40-70 (rising trend)
6. ✅ **Price Gain** - 8%+ gain today
7. ✅ **Market Cap** - Above $500M minimum (filters micro-cap stocks)

## Quick Start

```bash
# Run the demo screener
python scripts/demo_multi_factor_screener.py
```

## How It Works

### 1. Universe Filtering

First, the screener filters out stocks that don't meet basic criteria:

```python
from decimal import Decimal
from trade_engine.services.screening import MultiFactorScreener

screener = MultiFactorScreener(
    min_market_cap=Decimal("500_000_000"),  # $500M minimum
    min_price=Decimal("10.0"),              # $10 minimum
    lookback_days=20,                       # 20-day breakout window
    ma_short=50,                            # 50-day moving average
    ma_long=200                             # 200-day moving average
)
```

### 2. Signal Matching

For each stock, the screener calculates:

| Signal | Calculation | Pass Criteria |
|--------|-------------|---------------|
| **Breakout Score** | Distance from 20-day high | Score ≥ 70/100 |
| **Volume Ratio** | Today's volume / 20-day avg | Ratio ≥ 2.0x |
| **MA Alignment** | Price > 50MA > 200MA | Boolean (True/False) |
| **MACD Bullish** | MACD crossed above signal | Boolean (True/False) |
| **RSI Value** | 14-period RSI | 40 ≤ RSI ≤ 70 |
| **Gain %** | (Close - Prev Close) / Prev Close × 100 | Gain ≥ 8% |
| **Market Cap** | Company market capitalization | Market Cap ≥ $500M |

### 3. Scoring System

Each match gets scored on two dimensions:

#### Breakout Score (0-100)
```
100 = New 20-day high (at or above)
75  = Within 2% of 20-day high
50  = Within 5% of 20-day high
0   = Below 20-day high by >5%
```

#### Momentum Score (0-100)
```
RSI contribution:     0-40 points (optimal: 50-70)
MACD contribution:    0-30 points (bullish crossover)
Volume contribution:  0-30 points (higher ratio = more points)
```

#### Composite Score (0-100)
Weighted combination of all factors:
- 25% Breakout score
- 25% Momentum score
- 20% Signals matched (out of 7)
- 15% Gain percentage
- 15% Volume ratio

## Usage Examples

### Example 1: Basic Scan

```python
from decimal import Decimal
from trade_engine.services.screening import MultiFactorScreener

# Initialize screener
screener = MultiFactorScreener()

# Define universe (S&P 500, NASDAQ 100, etc.)
universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", ...]

# Scan for matches
matches = screener.scan_universe(
    symbols=universe,
    min_gain_percent=Decimal("8.0"),     # 8%+ gain
    min_volume_ratio=Decimal("2.0"),     # 2x volume
    min_breakout_score=70,                # Strong breakout
    min_signals_matched=4                 # 4 out of 7 signals
)

# Get top 10 picks
top_picks = matches[:10]

for match in top_picks:
    print(f"{match.symbol}: Score {match.composite_score}, "
          f"Signals {match.signals_matched}/7, "
          f"Gain {match.gain_percent}%")
```

### Example 2: Aggressive Scan (More Matches)

Lower thresholds to find more candidates:

```python
matches = screener.scan_universe(
    symbols=universe,
    min_gain_percent=Decimal("5.0"),      # Lower gain requirement
    min_volume_ratio=Decimal("1.5"),      # Lower volume requirement
    min_breakout_score=50,                 # More lenient breakout
    min_signals_matched=3                  # Fewer signals required
)
```

### Example 3: Conservative Scan (Best Setups Only)

Higher thresholds for highest quality matches:

```python
matches = screener.scan_universe(
    symbols=universe,
    min_gain_percent=Decimal("10.0"),     # 10%+ gain
    min_volume_ratio=Decimal("3.0"),      # 3x volume
    min_breakout_score=90,                 # Near/at 20-day high
    min_signals_matched=5                  # 5+ signals required
)
```

### Example 4: Daily Automated Scan

```python
import schedule
import time
from datetime import datetime

def daily_scan():
    """Run screener at market close."""
    screener = MultiFactorScreener()

    # Load full universe (e.g., from CSV)
    with open("universes/sp500.txt") as f:
        universe = [line.strip() for line in f]

    matches = screener.scan_universe(
        symbols=universe,
        min_gain_percent=Decimal("8.0"),
        min_volume_ratio=Decimal("2.0"),
        min_breakout_score=70,
        min_signals_matched=4
    )

    # Export results to CSV
    timestamp = datetime.now().strftime("%Y%m%d")
    with open(f"results/scan_{timestamp}.csv", "w") as f:
        f.write("Symbol,Price,Gain%,Volume Ratio,Score,Signals\n")
        for m in matches:
            f.write(f"{m.symbol},{m.price},{m.gain_percent},"
                   f"{m.volume_ratio},{m.composite_score},"
                   f"{m.signals_matched}\n")

    print(f"Scan complete: {len(matches)} matches found")

# Schedule daily at 4:05 PM ET (after market close)
schedule.every().day.at("16:05").do(daily_scan)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Interpreting Results

### ScreenerMatch Object

Each match contains:

```python
@dataclass
class ScreenerMatch:
    symbol: str              # Stock ticker
    price: Decimal           # Current price
    gain_percent: Decimal    # % gain today
    gain_dollars: Decimal    # $ gain today
    volume_ratio: Decimal    # Volume / 20-day avg
    breakout_score: int      # 0-100 (distance from 20-day high)
    momentum_score: int      # 0-100 (RSI + MACD + volume)
    ma_alignment: bool       # True if 50MA > 200MA
    macd_bullish: bool       # True if MACD crossed above
    rsi_value: Decimal       # Current RSI (14-period)
    signals_matched: int     # Count (0-7)
    composite_score: int     # Overall score (0-100)
```

### Score Interpretation

| Composite Score | Interpretation | Action |
|----------------|----------------|--------|
| **80-100** | 🔥 Strong buy signal | High conviction - check fundamentals |
| **60-79** | ✅ Good buy signal | Solid setup - verify catalyst |
| **40-59** | ⚠️ Moderate signal | Needs confirmation - check news |
| **0-39** | 🚫 Weak signal | Skip or wait for better setup |

### Signals Matched Interpretation

| Signals Matched | Interpretation |
|----------------|----------------|
| **6-7** | Exceptional - All systems go |
| **5** | Strong - Most signals aligned |
| **4** | Good - Solid multi-factor setup |
| **3** | Moderate - Needs fundamental confirmation |
| **0-2** | Weak - Not enough conviction |

## Filtering for Fundamentals

After technical screening, check fundamentals:

### 1. Recent Catalysts (Last 2 Days)

```python
def check_catalysts(symbol: str) -> List[str]:
    """Check for recent news catalysts."""
    catalysts = []

    # Check for:
    # - Earnings beat + guidance raise
    # - Major contract wins
    # - Acquisition/merger announcements
    # - Product launches
    # - Analyst upgrades

    # Example (pseudo-code):
    news = fetch_recent_news(symbol, days=2)
    for item in news:
        if "earnings" in item.headline.lower():
            catalysts.append("Earnings report")
        if "contract" in item.headline.lower():
            catalysts.append("Contract win")
        # ... more checks

    return catalysts
```

### 2. Institutional Flow

```python
def check_institutional_flow(symbol: str) -> Dict:
    """Check for institutional buying."""
    return {
        "dark_pool_volume": get_dark_pool_volume(symbol),
        "insider_buying": get_insider_transactions(symbol),
        "options_flow": get_unusual_options_activity(symbol)
    }
```

### 3. Complete Workflow

```python
# 1. Technical screening
matches = screener.scan_universe(symbols, ...)

# 2. Filter for fundamentals
for match in matches:
    catalysts = check_catalysts(match.symbol)
    flow = check_institutional_flow(match.symbol)

    if catalysts and flow["dark_pool_volume"] > threshold:
        print(f"✅ {match.symbol} - Technical + Fundamental match")
        print(f"   Catalysts: {', '.join(catalysts)}")
        print(f"   Institutional flow confirmed")
    else:
        print(f"⚠️  {match.symbol} - Technical only (skip?)")
```

## Advanced Customization

### Custom Weighting

Adjust composite score weights based on your preference:

```python
# In multi_factor_screener.py, modify _calculate_composite_score():

def _calculate_composite_score(self, ...):
    # Default weights
    w_breakout = Decimal("0.25")   # 25% breakout
    w_momentum = Decimal("0.25")   # 25% momentum
    w_signals = Decimal("0.20")    # 20% signals matched
    w_gain = Decimal("0.15")       # 15% gain
    w_volume = Decimal("0.15")     # 15% volume

    # Example: Emphasize breakout more
    # w_breakout = Decimal("0.40")
    # w_momentum = Decimal("0.30")
    # w_signals = Decimal("0.15")
    # w_gain = Decimal("0.10")
    # w_volume = Decimal("0.05")
```

### Custom Thresholds

```python
screener = MultiFactorScreener(
    min_market_cap=Decimal("1_000_000_000"),  # $1B (large cap only)
    min_price=Decimal("20.0"),                 # $20+ (higher quality)
    lookback_days=30,                          # 30-day breakout
    ma_short=20,                               # Shorter MA (more responsive)
    ma_long=50                                 # Shorter long MA
)
```

## Performance Tips

### 1. Batch Processing

For large universes (1000+ stocks):

```python
from concurrent.futures import ThreadPoolExecutor

def scan_batch(symbols_batch):
    screener = MultiFactorScreener()
    return screener.scan_universe(symbols_batch, ...)

# Split universe into batches
batch_size = 100
batches = [universe[i:i+batch_size]
           for i in range(0, len(universe), batch_size)]

# Process in parallel
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(scan_batch, batches))

# Combine results
all_matches = [match for batch in results for match in batch]
```

### 2. Caching Data

Cache OHLCV data to avoid refetching:

```python
import pickle
from pathlib import Path

cache_dir = Path("data/cache")
cache_dir.mkdir(exist_ok=True)

def fetch_with_cache(symbol, interval, start, end):
    cache_file = cache_dir / f"{symbol}_{interval}_{start.date()}.pkl"

    if cache_file.exists():
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    data = data_source.fetch_ohlcv(symbol, interval, start, end)

    with open(cache_file, "wb") as f:
        pickle.dump(data, f)

    return data
```

## Troubleshooting

### Issue: No matches found

**Solutions:**
1. Lower `min_gain_percent` (try 5% instead of 8%)
2. Lower `min_volume_ratio` (try 1.5x instead of 2.0x)
3. Lower `min_signals_matched` (try 3 instead of 4)
4. Expand your universe (more stocks = more chances)

### Issue: Too many matches (not selective enough)

**Solutions:**
1. Raise `min_gain_percent` (try 10% or 12%)
2. Raise `min_volume_ratio` (try 3.0x or higher)
3. Raise `min_signals_matched` (try 5 or 6)
4. Raise `min_breakout_score` (try 80 or 90)

### Issue: yfinance rate limiting

**Solutions:**
1. Add delays between requests
2. Use caching (see Performance Tips)
3. Consider paid data provider for production

## Next Steps

1. **Build your universe** - Get list of S&P 500, NASDAQ 100, etc.
2. **Run daily scans** - Automate at market close
3. **Track performance** - Log matches and outcomes
4. **Refine thresholds** - Adjust based on results
5. **Add fundamental checks** - Catalyst verification
6. **Backtest signals** - Historical win rate analysis

## Related Documentation

- [CLAUDE.md](../../.claude/CLAUDE.md) - Project overview and standards
- [ROADMAP.md](../../ROADMAP.md) - Phase 1: Instrument Screener
- [Yahoo Finance Source](../reference/data_sources.md#yahoo-finance) - Data provider details
- [Alpha Strategies](../reference/alpha_strategies.md) - Technical indicators

## Example Output

```
================================================================================
Found 12 stocks matching criteria
================================================================================

🎯 Top Signal Matches (ranked by composite score):

────────────────────────────────────────────────────────────────────────────────
#1  NVDA  -  Score: 87/100
────────────────────────────────────────────────────────────────────────────────

📈 Price Action:
   Current Price:    $485.32
   Today's Gain:     $42.18 (9.5%)

📊 Volume:
   Volume Ratio:     3.2x average

🎯 Technical Signals (6/7 matched):
   ✓ Breakout Score:  95/100
   ✓ Momentum Score:  85/100
   ✓ MA Alignment:   50MA > 200MA, Price > 50MA
   ✓ MACD Signal:    Bullish crossover
   ✓ RSI Value:       62.4 (40-70 optimal)

💡 Interpretation:
   🔥 STRONG BUY SIGNAL - Multiple confirmations
```
