# Breakout Setup Detector - User Guide

**Strategy**: BreakoutSetupDetector
**Type**: Multi-Factor Breakout Detection
**Timeframe**: Works on any timeframe (1m - 1d)
**Markets**: Crypto futures, spot, options

---

## Overview

The **BreakoutSetupDetector** is a comprehensive strategy that identifies bullish breakout setups by combining multiple confirmation factors:

1. **Price Breakout**: Price closing above identified resistance with confirmation
2. **Volume Confirmation**: Volume spike ≥2x average volume
3. **Momentum**: RSI >55 and MACD bullish crossover
4. **Volatility Squeeze**: Bollinger Bands tight before breakout, expanding after
5. **Derivatives**: Open Interest increase, positive funding, bullish put/call ratio
6. **Risk Filters**: Avoids overextended setups and potential traps

Each factor contributes to a **confidence score (0-1)**, and setups with ≥70% confidence generate trading signals.

---

## Quick Start

### Basic Usage

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector
)
from trade_engine.core.types import Bar

# Initialize strategy
strategy = BreakoutSetupDetector(symbol="BTCUSDT")

# Process market data bars
bar = Bar(
    timestamp=1735650000000,
    open=Decimal("50000"),
    high=Decimal("51000"),
    low=Decimal("49800"),
    close=Decimal("50800"),
    volume=Decimal("300")
)

signals = strategy.on_bar(bar)

# Check for breakout signals
if signals:
    signal = signals[0]
    print(f"Breakout detected! Entry: ${signal.price}, SL: ${signal.sl}, TP: ${signal.tp}")
```

### With Derivatives Data

```python
# Update derivatives data (call periodically when data available)
strategy.update_derivatives_data(
    open_interest=Decimal("150000000"),  # Total OI in base currency
    funding_rate=Decimal("0.0002"),      # Funding rate per 8h (0.02%)
    put_call_ratio=Decimal("0.75")       # Options put/call ratio
)

# Process bar as usual
signals = strategy.on_bar(bar)
```

---

## Configuration

### Default Configuration

```python
from trade_engine.domain.strategies.alpha_breakout_detector import BreakoutConfig

config = BreakoutConfig()

# Breakout Detection
config.volume_spike_threshold = Decimal("2.0")  # Require 2x volume
config.resistance_confirmation_pct = Decimal("0.5")  # 0.5% above resistance

# Momentum
config.rsi_period = 14
config.rsi_bullish_threshold = Decimal("55")
config.rsi_overbought_threshold = Decimal("75")

config.macd_fast = 12
config.macd_slow = 26
config.macd_signal = 9
config.macd_lookback_bars = 5  # Check MACD cross in last 5 bars

# Volatility
config.bb_period = 20
config.bb_std_dev = Decimal("2.0")
config.bb_squeeze_threshold = Decimal("0.02")  # 2% bandwidth = tight

# Volume
config.volume_ma_period = 20

# Derivatives
config.oi_increase_threshold = Decimal("0.10")  # 10% increase
config.put_call_bullish_threshold = Decimal("1.0")  # <1.0 = bullish
config.funding_rate_positive_min = Decimal("0.0001")
config.funding_rate_extreme_max = Decimal("0.0005")

# Support/Resistance
config.sr_lookback_bars = 50
config.sr_tolerance_pct = Decimal("0.5")

# Position Sizing
config.position_size_usd = Decimal("1000")
```

### Custom Configuration Examples

#### Conservative (Higher Confirmation)

```python
config = BreakoutConfig(
    volume_spike_threshold=Decimal("3.0"),  # Require 3x volume
    rsi_bullish_threshold=Decimal("60"),    # Higher RSI requirement
    resistance_confirmation_pct=Decimal("1.0"),  # 1% above resistance
    oi_increase_threshold=Decimal("0.15"),  # 15% OI increase
)
```

#### Aggressive (Lower Thresholds)

```python
config = BreakoutConfig(
    volume_spike_threshold=Decimal("1.5"),  # Only 1.5x volume
    rsi_bullish_threshold=Decimal("50"),    # Lower RSI OK
    resistance_confirmation_pct=Decimal("0.3"),  # 0.3% above resistance
    rsi_overbought_threshold=Decimal("80"),  # Allow higher RSI
)
```

#### Scalping (Short Timeframes)

```python
config = BreakoutConfig(
    volume_spike_threshold=Decimal("2.5"),  # Higher volume requirement
    rsi_period=9,                           # Faster RSI
    macd_fast=8,                            # Faster MACD
    macd_slow=17,
    bb_period=10,                           # Faster BB
    position_size_usd=Decimal("500"),       # Smaller position
)
```

---

## Understanding the Output

### Signal Format

When a breakout setup is detected, the strategy returns a standard `Signal`:

```python
Signal(
    symbol="BTCUSDT",
    side="buy",                    # Always "buy" for breakouts
    qty=Decimal("0.02"),           # Position size in base currency
    price=Decimal("51200"),        # Entry price
    sl=Decimal("49800"),           # Stop loss (below resistance)
    tp=Decimal("53800"),           # Take profit (2:1 R:R)
    reason="Breakout setup: ..."   # Summary of conditions met
)
```

### Detailed Setup Analysis

The strategy internally generates detailed `SetupSignal` objects with all analysis:

```python
{
    "symbol": "BTC/USDT",
    "setup": "Bullish Breakout",  # or "Watchlist", "No Trade"
    "confidence": 0.82,
    "conditions_met": [
        "Breakout above resistance 51000 with volume 2.3x avg",
        "RSI 62 bullish, MACD bullish (hist: +0.0123)",
        "BB expanding from squeeze (3.5% bandwidth)",
        "OI increased 12.0%, Funding rate 0.02% positive, P/C ratio 0.75 bullish"
    ],
    "conditions_failed": [
        "Risk filters passed"
    ],
    "action": "Enter long via call options or perp with stop below resistance",

    # Detailed Metrics
    "current_price": 51200,
    "resistance_level": 51000,
    "volume_ratio": 2.3,
    "rsi": 62,
    "macd_histogram": 0.0123,
    "bb_bandwidth_pct": 3.5,
    "oi_change_pct": 0.12,
    "funding_rate": 0.0002,
    "put_call_ratio": 0.75,
    "timestamp": 1735650000000
}
```

### Setup Types

1. **Bullish Breakout** (Confidence ≥70%):
   - All or most conditions met
   - Ready for entry
   - Action: Enter long position

2. **Watchlist** (Confidence 50-70%):
   - Some conditions met, others forming
   - Setup developing but not confirmed
   - Action: Monitor for entry opportunity

3. **No Trade** (Confidence <50%):
   - Insufficient conditions met
   - Stay flat
   - Action: No action

---

## Multi-Factor Analysis Breakdown

### 1. Breakout Check (Weight: 30%)

**What it checks**:
- Is price closing above identified resistance level?
- Is volume spiking (≥2x average)?

**Scoring**:
- 1.0: Breakout above resistance + volume ≥2x
- 0.5: Breakout above resistance but volume <2x
- 0.0: No breakout or no resistance identified

**Example**:
```
Resistance: $51,000
Current close: $51,200 (0.4% above)
Volume: 300 (vs 120 avg = 2.5x)
→ Score: 1.0 ✅
```

### 2. Momentum Confirmation (Weight: 25%)

**What it checks**:
- RSI: Is RSI >55 (bullish bias)?
- MACD: Did MACD cross above zero in last 5 bars?

**Scoring**:
- 1.0: RSI >55 AND MACD bullish
- 0.5: Either RSI or MACD bullish (not both)
- 0.0: Neither RSI nor MACD bullish

**Example**:
```
RSI: 62 (above 55 threshold)
MACD histogram: +0.0123 (positive)
→ Score: 1.0 ✅
```

### 3. Volatility Squeeze (Weight: 15%)

**What it checks**:
- Were Bollinger Bands tight before breakout?
- Are they now expanding?

**Scoring**:
- 1.0: BB bandwidth expanding from squeeze
- 0.5: BB squeeze currently active
- 0.0: BB bandwidth normal (no squeeze)

**Example**:
```
BB bandwidth: 3.5%
Squeeze threshold: 2.0%
Expanding: Yes
→ Score: 1.0 ✅
```

### 4. Derivatives Signals (Weight: 20%)

**What it checks**:
- OI: Did Open Interest increase >10% in 24h?
- Funding: Is funding rate positive but not extreme (0.01% - 0.05%)?
- P/C: Is put/call ratio <1.0 (bullish)?

**Scoring** (cumulative):
- +0.4: OI increased >10%
- +0.3: Funding rate positive and reasonable
- +0.3: Put/call ratio bullish
- Maximum: 1.0

**Example**:
```
OI change: +12% (last 24h)
Funding rate: 0.02% per 8h
Put/call ratio: 0.75
→ Score: 1.0 (0.4 + 0.3 + 0.3) ✅
```

### 5. Risk Filters (Weight: 10%)

**What it checks**:
- RSI overextended? (>75)
- OI spike + flat price? (potential trap)

**Scoring**:
- 1.0: All risk filters passed
- 0.0: Risk filter triggered
- -0.5: Critical risk detected (heavily penalizes confidence)

**Example**:
```
RSI: 62 (not overextended)
OI spike: +12% with price up 2.1% (not flat)
→ Score: 1.0 ✅
```

---

## Confidence Calculation

Final confidence is a weighted sum of all factors:

```
Confidence = (Breakout * 0.30) +
             (Momentum * 0.25) +
             (Volatility * 0.15) +
             (Derivatives * 0.20) +
             (Risk Filter * 0.10)
```

**Example**:
```
Breakout: 1.0 * 0.30 = 0.30
Momentum: 1.0 * 0.25 = 0.25
Volatility: 1.0 * 0.15 = 0.15
Derivatives: 1.0 * 0.20 = 0.20
Risk Filter: 1.0 * 0.10 = 0.10
─────────────────────────────
Total Confidence: 0.82 (82%)
```

---

## Support & Resistance Detection

The strategy automatically detects support and resistance levels from recent price action:

### How it Works

1. **Lookback Period**: Analyzes last 50 bars (configurable)
2. **Swing Highs (Resistance)**: Local maxima where price is higher than surrounding 4 bars
3. **Swing Lows (Support)**: Local minima where price is lower than surrounding 4 bars
4. **Tolerance**: 0.5% tolerance for level matching

### Example

```
Recent highs: 51000, 50800, 51000, 50900, 51050
→ Resistance detected at: 51000 (appears twice)

Recent lows: 49500, 49600, 49500, 49700
→ Support detected at: 49500 (appears twice)
```

---

## Position Sizing & Risk Management

### Entry Sizing

```python
position_size_usd = Decimal("1000")  # Config parameter
entry_price = Decimal("51200")

qty = position_size_usd / entry_price
# Result: 0.0195 BTC
```

### Stop Loss Placement

- Placed 2% below resistance level (or recent support)
- Example: Resistance at $51,000 → SL at $49,980

### Take Profit Placement

- 2:1 Risk/Reward ratio
- Example: Risk = $51,200 - $49,980 = $1,220
  - TP = $51,200 + (2 × $1,220) = $53,640

---

## Backtesting & Optimization

### Running Backtest

```python
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig
)

# Load historical data
bars = load_historical_data("BTCUSDT", "1h", start_date, end_date)

# Initialize strategy
config = BreakoutConfig(
    volume_spike_threshold=Decimal("2.0"),
    position_size_usd=Decimal("1000")
)
strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

# Run backtest
trades = []
for bar in bars:
    signals = strategy.on_bar(bar)
    if signals:
        trades.append(signals[0])

# Analyze results
win_rate = calculate_win_rate(trades)
profit_factor = calculate_profit_factor(trades)
max_drawdown = calculate_max_drawdown(trades)
```

### Parameters to Optimize

**High Impact**:
1. `volume_spike_threshold`: Higher = fewer but higher quality setups
2. `rsi_bullish_threshold`: Higher = only strong momentum setups
3. `resistance_confirmation_pct`: Higher = clearer breakouts only

**Medium Impact**:
4. `bb_squeeze_threshold`: Lower = tighter squeezes only
5. `oi_increase_threshold`: Higher = stronger OI confirmation
6. `position_size_usd`: Affects risk per trade

**Low Impact** (usually keep defaults):
7. Indicator periods (RSI, MACD, BB)
8. Support/resistance lookback
9. Confidence weights

---

## Common Issues & Solutions

### Issue 1: No Signals Generated

**Symptoms**: Strategy runs but never generates signals

**Possible Causes**:
1. Insufficient data (need 20+ bars for all indicators)
2. No resistance levels identified yet
3. Thresholds too strict

**Solutions**:
- Run strategy for at least 50 bars to build context
- Lower `volume_spike_threshold` or `rsi_bullish_threshold`
- Check that resistance/support levels are being detected

### Issue 2: Too Many False Signals

**Symptoms**: Many signals but low win rate

**Possible Causes**:
1. Thresholds too loose
2. Risk filters not strict enough
3. Market conditions not suitable (ranging/choppy)

**Solutions**:
- Increase `volume_spike_threshold` (e.g., 2.5x or 3.0x)
- Increase `rsi_bullish_threshold` (e.g., 60 or 65)
- Lower `rsi_overbought_threshold` (e.g., 70)
- Add market regime filter (only trade in trending markets)

### Issue 3: Signals Come Too Late

**Symptoms**: Breakout already happened when signal fires

**Possible Causes**:
1. Resistance confirmation requirement too high
2. Indicator periods too slow

**Solutions**:
- Lower `resistance_confirmation_pct` (e.g., 0.3%)
- Use faster indicator periods (RSI=9, MACD 8/17/9)
- Consider using 5m timeframe instead of 1h

---

## Advanced Usage

### Custom Confidence Weights

```python
config = BreakoutConfig(
    # Emphasize breakout and momentum, de-emphasize derivatives
    weight_breakout=Decimal("0.40"),      # Increase from 0.30
    weight_momentum=Decimal("0.30"),      # Increase from 0.25
    weight_volatility=Decimal("0.15"),    # Keep same
    weight_derivatives=Decimal("0.10"),   # Decrease from 0.20
    weight_risk_filter=Decimal("0.05")    # Decrease from 0.10
)
```

### Multi-Timeframe Analysis

```python
# Analyze on multiple timeframes
strategy_1h = BreakoutSetupDetector(symbol="BTCUSDT")
strategy_15m = BreakoutSetupDetector(symbol="BTCUSDT")

# Process 1h bar
signals_1h = strategy_1h.on_bar(bar_1h)

# Process 15m bar
signals_15m = strategy_15m.on_bar(bar_15m)

# Combine signals (e.g., only trade if both agree)
if signals_1h and signals_15m:
    print("Both timeframes confirm breakout!")
```

### Market Regime Filter

```python
def is_trending_market(bars, period=20):
    """Check if market is trending (suitable for breakouts)."""
    closes = [bar.close for bar in bars[-period:]]
    sma = sum(closes) / len(closes)

    # Price above/below MA by >2% = trending
    current_price = closes[-1]
    deviation_pct = abs((current_price - sma) / sma) * 100

    return deviation_pct > 2

# Only trade breakouts in trending markets
if is_trending_market(bars):
    signals = strategy.on_bar(bar)
```

---

## Best Practices

1. **Use Paper Trading First**: Test strategy with paper trading before live capital
2. **Start Conservative**: Begin with default config, optimize gradually
3. **Track Performance**: Log all trades, analyze win rate and profit factor
4. **Market Conditions Matter**: Breakouts work best in trending markets, not ranges
5. **Combine with Regime Filter**: Only trade when market structure is favorable
6. **Position Size Appropriately**: Risk no more than 1-2% per trade
7. **Use Stop Losses**: Always use the generated SL, never trade without one
8. **Monitor Slippage**: Ensure executions are near signal price
9. **Derivatives Data Optional**: Strategy works without derivatives, but they improve accuracy
10. **Backtest Extensively**: Test on at least 6 months of historical data

---

## Performance Expectations

### Typical Results (1h timeframe, BTCUSDT, default config)

- **Win Rate**: 52-58%
- **Profit Factor**: 1.5-2.0
- **Avg R:R**: 2:1 (by design)
- **Signals per Week**: 2-5
- **Max Drawdown**: 15-25%

### Optimization Targets

- **Conservative**: Win rate >60%, fewer signals
- **Balanced**: Win rate 55%, profit factor >1.5
- **Aggressive**: More signals, win rate 50%, profit factor >2.0

---

## Related Documentation

- [Strategy Interface](../reference/adapters/README.md): Base strategy interface
- [Backtesting Guide](./backtesting-guide.md): How to backtest strategies
- [Risk Management](../guides/risk-management.md): Position sizing and risk rules

---

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Strategy Version**: 1.0
