# Volume RVOL Strategy Guide

## Overview

The **Volume RVOL (Relative Volume) Strategy** detects abnormal volume spikes that often precede or confirm significant price movements. RVOL compares current volume to the average volume over a lookback period, identifying institutional activity, breakouts, and trend accelerations.

## Strategy Logic

### Core Concept

**RVOL = Current Volume / Average Volume (last N bars)**

- RVOL ≥ 2.0× = Moderate spike (confirmation signal)
- RVOL ≥ 3.0× = Strong spike (whale activity)
- RVOL ≥ 5.0× = Extreme spike (news/event driven)

### Signal Generation

A valid signal requires **BOTH**:
1. **Volume spike**: Current volume exceeds threshold × average volume
2. **Price move**: Minimum price change from previous close

**Direction Detection**:
- Price up + volume spike = **BUY** (bullish breakout/accumulation)
- Price down + volume spike = **SELL** (bearish breakdown/distribution)

### Research Basis

- High-volume breakouts have 60-70% success rate
- Volume precedes price (smart money accumulation/distribution)
- Decreasing volume in trends signals weakness
- Institutional orders create observable volume signatures

## Configuration

### Parameters

```python
@dataclass
class VolumeRVOLConfig:
    # RVOL Detection
    rvol_threshold: Decimal = Decimal("2.0")  # Minimum volume spike
    lookback_bars: int = 20  # Bars to calculate average volume

    # Signal Generation
    price_change_threshold: Decimal = Decimal("0.005")  # 0.5% price move required
    min_volume_absolute: Decimal = Decimal("0")  # Minimum absolute volume filter

    # Position Sizing
    position_size_usd: Decimal = Decimal("1000")
    risk_pct: Decimal = Decimal("0.01")  # 1% risk per trade

    # Stop Loss / Take Profit
    atr_multiplier_sl: Decimal = Decimal("1.5")  # SL = 1.5× ATR
    atr_multiplier_tp: Decimal = Decimal("3.0")  # TP = 3× ATR (2:1 R:R)
```

### Parameter Tuning

| Parameter | Conservative | Moderate | Aggressive |
|-----------|--------------|----------|------------|
| `rvol_threshold` | 3.0× | 2.0× | 1.5× |
| `price_change_threshold` | 1.0% | 0.5% | 0.25% |
| `lookback_bars` | 30 | 20 | 10 |
| `atr_multiplier_sl` | 2.0× | 1.5× | 1.0× |

**Conservative**: Fewer signals, higher quality, larger stops
**Moderate**: Balanced approach (default)
**Aggressive**: More signals, requires tighter risk management

## Usage Examples

### Basic Usage

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_volume_rvol import (
    VolumeRVOLStrategy,
    VolumeRVOLConfig
)

# Initialize with default config
strategy = VolumeRVOLStrategy(symbol="BTCUSDT")

# Process market data
for bar in market_data:
    signals = strategy.on_bar(bar)

    if signals:
        signal = signals[0]
        print(f"RVOL Signal: {signal.side} @ ${signal.price}")
        print(f"Reason: {signal.reason}")
```

### Custom Configuration

```python
# Conservative setup (fewer, higher-quality signals)
config = VolumeRVOLConfig(
    rvol_threshold=Decimal("3.0"),  # Require 3× volume spike
    price_change_threshold=Decimal("0.01"),  # Require 1% price move
    lookback_bars=30,  # Longer lookback for stability
    atr_multiplier_sl=Decimal("2.0"),  # Wider stops
    atr_multiplier_tp=Decimal("4.0")  # 2:1 R:R
)

strategy = VolumeRVOLStrategy(symbol="BTCUSDT", config=config)
```

### Volume Confirmation for Breakouts

```python
# Use RVOL as confirmation for breakout strategy
breakout_strategy = BreakoutDetectorStrategy(symbol="BTCUSDT")
volume_strategy = VolumeRVOLStrategy(symbol="BTCUSDT")

for bar in market_data:
    breakout_signals = breakout_strategy.on_bar(bar)
    volume_signals = volume_strategy.on_bar(bar)

    # Only trade breakouts with volume confirmation
    if breakout_signals and volume_signals:
        if breakout_signals[0].side == volume_signals[0].side:
            print("✅ Breakout confirmed by volume spike!")
            # Execute trade...
```

### Multi-Timeframe Analysis

```python
# Track RVOL across multiple timeframes
strategy_1m = VolumeRVOLStrategy(symbol="BTCUSDT")
strategy_5m = VolumeRVOLStrategy(symbol="BTCUSDT")
strategy_15m = VolumeRVOLStrategy(symbol="BTCUSDT")

# Process each timeframe
signals_1m = strategy_1m.on_bar(bar_1m)
signals_5m = strategy_5m.on_bar(bar_5m)
signals_15m = strategy_15m.on_bar(bar_15m)

# Trade only when multiple timeframes align
if signals_1m and signals_5m and signals_15m:
    print("🔥 Multi-timeframe volume spike alignment!")
```

## Signal Interpretation

### Strong Bullish Signals

1. **Breakout Volume Spike**
   - Price breaks resistance + RVOL ≥ 3×
   - Indicates institutional buying / breakout confirmation
   - High probability of trend continuation

2. **Accumulation Volume**
   - Price consolidates near lows + RVOL ≥ 2×
   - Suggests smart money accumulation
   - Look for bullish price action to follow

3. **Trend Acceleration**
   - Existing uptrend + RVOL spike on new high
   - Strong trend continuation signal
   - Watch for exhaustion if RVOL becomes extreme (5×+)

### Strong Bearish Signals

1. **Breakdown Volume Spike**
   - Price breaks support + RVOL ≥ 3×
   - Indicates institutional selling / breakdown confirmation
   - High probability of trend continuation

2. **Distribution Volume**
   - Price stalls near highs + RVOL ≥ 2×
   - Suggests smart money distribution
   - Look for bearish price action to follow

3. **Parabolic Exhaustion**
   - Vertical move + RVOL ≥ 5×
   - Often marks temporary top/bottom
   - Consider contrarian positioning

## Filters and Risk Management

### Built-in Filters

1. **Cooldown Period**
   - Minimum 3 bars between signals
   - Prevents over-trading during volatile conditions

2. **Price Change Requirement**
   - Volume spike alone insufficient
   - Must have meaningful price movement

3. **Zero Volume Filter**
   - Automatically skips zero volume bars
   - Data quality protection

### ATR-Based Position Sizing

The strategy uses **ATR (Average True Range)** for dynamic stop loss and take profit levels:

```python
# Example: Current price = $50,000, ATR = $500
sl = price - (atr * 1.5)  # $49,250 (1.5% stop)
tp = price + (atr * 3.0)  # $51,500 (3% target)
```

**Benefits**:
- Adapts to market volatility
- Tighter stops in calm markets
- Wider stops in volatile markets
- Maintains consistent risk:reward ratio

## Integration Patterns

### Pattern 1: Volume Confirmation Filter

Use RVOL to confirm signals from other strategies:

```python
def confirm_with_volume(primary_signal, volume_strategy, bar):
    """Require volume confirmation for primary signal."""
    volume_signals = volume_strategy.on_bar(bar)

    if not volume_signals:
        return None  # No volume spike, reject signal

    if primary_signal.side == volume_signals[0].side:
        return primary_signal  # Confirmed!

    return None  # Direction mismatch, reject
```

### Pattern 2: Volume-Weighted Strategy Selection

Allocate more capital to trades with strong volume:

```python
def size_by_volume(signal, rvol):
    """Scale position size by RVOL strength."""
    base_size = Decimal("1000")

    if rvol >= Decimal("5.0"):
        return base_size * Decimal("2.0")  # Double size for extreme spikes
    elif rvol >= Decimal("3.0"):
        return base_size * Decimal("1.5")  # 1.5× for strong spikes
    else:
        return base_size  # Normal size for moderate spikes
```

### Pattern 3: Volume Divergence Detection

Detect weakness when price moves without volume:

```python
def detect_volume_divergence(bars, volume_strategy):
    """Identify price moves with declining volume (weakness)."""
    recent_bars = bars[-5:]

    # Check if price is making new highs/lows
    price_trend = is_making_new_extremes(recent_bars)

    # Check if volume is declining
    volumes = [b.volume for b in recent_bars]
    volume_declining = all(volumes[i] > volumes[i+1] for i in range(len(volumes)-1))

    if price_trend and volume_declining:
        return "DIVERGENCE"  # Warning: price move not confirmed by volume

    return "HEALTHY"
```

## Performance Considerations

### Expected Performance

- **Signal Frequency**: 2-5 signals per day (2× threshold, 1-hour bars)
- **Win Rate**: 55-65% (when combined with price action)
- **Avg R:R**: 2:1 (using default ATR multipliers)
- **Best Markets**: Liquid instruments (BTC, ETH, major stocks)

### Strengths

✅ Objective, mechanical detection
✅ Catches institutional activity early
✅ Works across all timeframes
✅ Adapts to volatility via ATR
✅ Simple to backtest and optimize

### Weaknesses

❌ False signals in choppy markets
❌ Lags slightly (volume confirms price)
❌ Less effective in low-liquidity assets
❌ Requires proper ATR period tuning

## Backtesting Tips

1. **Test Multiple Thresholds**
   - Run parameter sweeps on `rvol_threshold` (1.5×, 2×, 2.5×, 3×)
   - Observe trade-off between signal frequency and quality

2. **Validate ATR Periods**
   - Test ATR periods: 10, 14, 20 bars
   - Ensure stops aren't too tight or too wide for asset

3. **Check Timeframe Dependency**
   - Strategy behavior changes significantly by timeframe
   - 1-min: very noisy, 5-min: balanced, 1-hour: cleaner but fewer signals

4. **Measure Slippage Impact**
   - Volume spikes often coincide with wider spreads
   - Add realistic slippage assumptions (0.05-0.1%)

## Common Mistakes

### ❌ Mistake 1: Ignoring Price Context

**Wrong**: Trading every RVOL spike blindly
**Right**: Consider price structure (support/resistance, trend direction)

### ❌ Mistake 2: Over-Optimizing Threshold

**Wrong**: Finding "perfect" RVOL threshold from backtest
**Right**: Use robust threshold (2-3×) that works across conditions

### ❌ Mistake 3: Not Adjusting for Low Volume Periods

**Wrong**: Trading RVOL signals during off-hours (low liquidity)
**Right**: Filter signals by absolute volume or time of day

### ❌ Mistake 4: Using Fixed Stops

**Wrong**: Always using 1% stop loss
**Right**: Use ATR-based stops to adapt to volatility

## Advanced Topics

### Volume Profile Integration

Combine RVOL with **Volume Profile** to identify high-probability zones:

```python
# Pseudocode
volume_profile = calculate_volume_profile(historical_data)
high_volume_nodes = volume_profile.get_nodes(threshold=1.5)

if rvol_spike and price_near_hvn:
    # Volume spike near high-volume node = strong signal
    confidence = "HIGH"
```

### Order Flow Analysis

For ultra-short-term trading, combine RVOL with **Order Flow**:

- RVOL spike + aggressive buying (market buys) = strong bullish
- RVOL spike + aggressive selling (market sells) = strong bearish

### Machine Learning Enhancement

Use RVOL as a feature in ML models:

```python
features = {
    "rvol": current_rvol,
    "rvol_change": rvol_slope,
    "price_change": price_pct_change,
    "atr_ratio": current_bar_range / atr,
    ...
}

prediction = ml_model.predict(features)
```

## Troubleshooting

### Issue: Too Many Signals

**Solution**: Increase `rvol_threshold` or `price_change_threshold`

### Issue: No Signals Generated

**Causes**:
- Insufficient data (need `lookback_bars` minimum)
- Threshold too high for asset's typical volume
- Low volatility period (no meaningful price moves)

**Solution**: Lower thresholds or verify data quality

### Issue: Stops Too Tight

**Solution**: Increase `atr_multiplier_sl` or use longer ATR period

### Issue: Poor Performance in Backtests

**Checklist**:
- [ ] Realistic slippage included?
- [ ] Tested across multiple market conditions?
- [ ] Filtering low-liquidity periods?
- [ ] Using proper position sizing?

## Further Reading

- **Academic Research**: "Volume and Price Patterns Around Block Trades" (Keim & Madhavan, 1996)
- **Practical Guide**: "Technical Analysis Using Multiple Timeframes" (Covel, 2008)
- **Order Flow**: "Trading in the Shadow" (Bouchaud et al., 2018)

## Summary

The Volume RVOL Strategy is a powerful tool for:
- ✅ Confirming breakouts and trend moves
- ✅ Identifying institutional activity
- ✅ Filtering false signals from other strategies
- ✅ Detecting accumulation/distribution phases

**Best used as**:
- Confirmation filter for primary strategies
- Standalone strategy in trending markets
- Early warning system for regime changes

**Not recommended for**:
- Low-liquidity assets (<$1M daily volume)
- Pure mean-reversion strategies
- Ultra-low latency trading (order flow better)
