# Market Regime Detector Strategy Guide

## Overview

The **Market Regime Detector Strategy** classifies market conditions into six distinct regimes to enable regime-aware strategy selection and risk management. By combining technical indicators (ADX, Hurst Exponent) with price structure analysis, this strategy helps other trading systems adapt to changing market conditions.

## Why Regime Detection Matters

**Key Insight**: Different strategies perform best in different market conditions.

- **Trend-following strategies** excel in **trending markets** but fail in **ranges**
- **Mean-reversion strategies** excel in **ranges** but get crushed in **trends**
- **Volatility strategies** profit from **high volatility** but underperform in **calm markets**

**Solution**: Detect the current regime and dynamically select appropriate strategies.

## The Six Market Regimes

| Regime | Characteristics | Best Strategies |
|--------|-----------------|-----------------|
| **Strong Uptrend** | High ADX (>25), High Hurst (>0.55), Higher highs/lows | Trend-following LONG |
| **Weak Uptrend** | Moderate ADX, Bullish structure | Momentum LONG, breakout |
| **Strong Downtrend** | High ADX (>25), High Hurst (>0.55), Lower highs/lows | Trend-following SHORT |
| **Weak Downtrend** | Moderate ADX, Bearish structure | Momentum SHORT, breakdown |
| **Range-Bound** | Low ADX (<20), Low Hurst (<0.45) | Mean-reversion, theta decay |
| **High Volatility** | Extreme ATR, no clear trend | Volatility strategies, stay out |

## Strategy Logic

### Component 1: ADX (Trend Strength)

**Average Directional Index (ADX)** measures trend strength (not direction).

- **ADX < 20**: Weak or no trend (ranging)
- **ADX 20-25**: Moderate trend developing
- **ADX > 25**: Strong trend in place
- **ADX > 40**: Very strong trend (may be nearing exhaustion)

**Calculation**:
1. True Range (TR) = max(H-L, |H-C_prev|, |C_prev-L|)
2. Directional Movements: +DM = H_today - H_yesterday, -DM = L_yesterday - L_today
3. Smoothed +DI and -DI from directional movements
4. ADX = smoothed average of |+DI - -DI|

### Component 2: Hurst Exponent (Trend Persistence)

**Hurst Exponent (H)** measures whether price action is trending or mean-reverting.

- **H > 0.5**: Trending (persistent behavior)
- **H = 0.5**: Random walk (no memory)
- **H < 0.5**: Mean-reverting (anti-persistent)

**Interpretation**:
- H = 0.7: Strong trend (today's move predicts tomorrow's direction)
- H = 0.5: Pure noise (coin flip)
- H = 0.3: Mean-reversion (today's move predicts reversal tomorrow)

**Calculation**: Uses Rescaled Range (R/S) analysis across multiple time scales.

### Component 3: Price Structure

**Price Structure Analysis** identifies higher highs/lows (uptrend) or lower highs/lows (downtrend).

```
Uptrend Structure:
  HH = Higher High (new peak)
  HL = Higher Low (pullback above previous low)

Downtrend Structure:
  LH = Lower High (failed rally)
  LL = Lower Low (new bottom)
```

### Classification Logic

```python
if ADX > 25 and Hurst > 0.55:
    if higher_highs and higher_lows:
        regime = STRONG_UPTREND
    elif lower_highs and lower_lows:
        regime = STRONG_DOWNTREND

elif ADX > 20:
    if higher_highs:
        regime = WEAK_UPTREND
    elif lower_lows:
        regime = WEAK_DOWNTREND

elif ADX < 20 and Hurst < 0.45:
    regime = RANGE_BOUND

elif ATR > ATR_threshold:
    regime = HIGH_VOLATILITY

else:
    regime = UNKNOWN
```

## Configuration

### Parameters

```python
@dataclass
class RegimeDetectorConfig:
    # ADX Calculation
    adx_period: int = 14  # Standard ADX period
    adx_trend_threshold: Decimal = Decimal("25")  # ADX > 25 = trending
    adx_weak_threshold: Decimal = Decimal("20")  # ADX < 20 = ranging

    # Hurst Exponent Calculation
    hurst_lookback: int = 100  # Bars for Hurst calculation
    hurst_trend_threshold: Decimal = Decimal("0.55")  # H > 0.55 = trending
    hurst_mean_revert_threshold: Decimal = Decimal("0.45")  # H < 0.45 = mean-revert

    # Price Structure
    swing_lookback: int = 10  # Bars to identify swing highs/lows

    # Volatility Detection
    atr_period: int = 14
    atr_volatility_multiplier: Decimal = Decimal("2.0")  # ATR > 2× avg = high vol

    # Signal Generation (optional)
    emit_signals_on_change: bool = False  # Generate signals on regime change
    position_size_usd: Decimal = Decimal("1000")
```

### Parameter Tuning by Timeframe

| Timeframe | ADX Period | Hurst Lookback | Swing Lookback |
|-----------|------------|----------------|----------------|
| **1-min** | 14-20 | 50-100 | 5-10 |
| **5-min** | 14 | 100 | 10 |
| **15-min** | 14 | 100 | 10-15 |
| **1-hour** | 14 | 100-200 | 15-20 |
| **Daily** | 14 | 200-300 | 20-30 |

## Usage Examples

### Basic Usage (As a Filter)

```python
from trade_engine.domain.strategies.alpha_regime_detector import (
    RegimeDetectorStrategy,
    MarketRegime
)

# Initialize regime detector
regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT")

# Process bars
for bar in market_data:
    regime_detector.on_bar(bar)

    # Query current regime
    current_regime = regime_detector.get_current_regime()

    if regime_detector.is_trending():
        print("✅ Trending market - use trend-following strategies")
    elif regime_detector.is_ranging():
        print("⚠️ Ranging market - use mean-reversion strategies")
```

### Regime-Aware Strategy Selection

```python
# Initialize multiple strategies
breakout_strategy = BreakoutDetectorStrategy(symbol="BTCUSDT")
mean_reversion_strategy = MeanReversionStrategy(symbol="BTCUSDT")
regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT")

for bar in market_data:
    # Update regime
    regime_detector.on_bar(bar)

    # Select strategy based on regime
    if regime_detector.is_trending():
        # Use trend-following in trends
        signals = breakout_strategy.on_bar(bar)

    elif regime_detector.is_ranging():
        # Use mean-reversion in ranges
        signals = mean_reversion_strategy.on_bar(bar)

    else:
        # Stay out during high volatility or unknown regimes
        print("⏸️ No suitable regime - staying flat")
        signals = []

    # Execute signals...
```

### Risk Management by Regime

```python
def get_position_size(regime: MarketRegime, base_size: Decimal) -> Decimal:
    """Adjust position size based on regime."""

    if regime == MarketRegime.STRONG_UPTREND:
        return base_size * Decimal("1.5")  # 1.5× in strong trends

    elif regime in [MarketRegime.WEAK_UPTREND, MarketRegime.WEAK_DOWNTREND]:
        return base_size * Decimal("1.0")  # Normal size

    elif regime == MarketRegime.RANGE_BOUND:
        return base_size * Decimal("0.75")  # 75% size in ranges

    elif regime == MarketRegime.HIGH_VOLATILITY:
        return base_size * Decimal("0.5")  # 50% size in volatility

    else:
        return Decimal("0")  # No position in unknown regime

# Usage
regime = regime_detector.get_current_regime()
position_size = get_position_size(regime, base_size=Decimal("1000"))
```

### Signal Generation on Regime Changes

```python
# Enable signal generation
config = RegimeDetectorConfig(emit_signals_on_change=True)
regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT", config=config)

for bar in market_data:
    signals = regime_detector.on_bar(bar)

    if signals:
        signal = signals[0]
        print(f"📢 Regime changed to: {signal.reason}")

        # Take action on regime change
        if "STRONG_UPTREND" in signal.reason:
            # Rotate into trend-following long strategies
            pass
        elif "RANGE_BOUND" in signal.reason:
            # Rotate into mean-reversion strategies
            pass
```

## Signal Interpretation

### Regime Transitions

**Key Insight**: Regime *changes* are as important as the regime itself.

#### Transition: Range → Uptrend
```
Previous: RANGE_BOUND (ADX 18, Hurst 0.43)
Current: WEAK_UPTREND (ADX 22, Hurst 0.52)

Interpretation: Trend developing, early stage
Action: Enter long trend-following positions
Risk: Could be false breakout
```

#### Transition: Uptrend → High Volatility
```
Previous: STRONG_UPTREND (ADX 32, Hurst 0.62)
Current: HIGH_VOLATILITY (ATR spike)

Interpretation: Trend breakdown, uncertainty
Action: Reduce position sizes, tighten stops
Risk: Could signal reversal
```

#### Transition: Downtrend → Range
```
Previous: STRONG_DOWNTREND (ADX 28)
Current: RANGE_BOUND (ADX 19)

Interpretation: Selling exhaustion, consolidation
Action: Exit trend shorts, prepare mean-reversion longs
Risk: Could be pause before continuation
```

### Using Helper Methods

```python
regime = regime_detector.get_current_regime()

# Check specific conditions
is_bullish = regime_detector.is_bullish()  # Any uptrend
is_bearish = regime_detector.is_bearish()  # Any downtrend
is_trending = regime_detector.is_trending()  # Any trend
is_ranging = regime_detector.is_ranging()  # Range-bound

# Make trading decisions
if is_bullish and is_trending:
    # Strong long bias
    strategy_weight = 1.5

elif is_ranging:
    # Neutral bias, use reversions
    strategy_weight = 0.75

elif is_bearish and is_trending:
    # Strong short bias
    strategy_weight = 1.5
```

## Integration Patterns

### Pattern 1: Multi-Strategy Portfolio

```python
class PortfolioManager:
    def __init__(self):
        self.regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT")
        self.strategies = {
            "trend": TrendFollowingStrategy(symbol="BTCUSDT"),
            "mean_reversion": MeanReversionStrategy(symbol="BTCUSDT"),
            "breakout": BreakoutDetectorStrategy(symbol="BTCUSDT")
        }

    def allocate_capital(self, total_capital: Decimal) -> Dict[str, Decimal]:
        """Allocate capital based on regime."""
        regime = self.regime_detector.get_current_regime()

        if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND]:
            # 80% trend-following, 20% breakout
            return {
                "trend": total_capital * Decimal("0.80"),
                "mean_reversion": Decimal("0"),
                "breakout": total_capital * Decimal("0.20")
            }

        elif regime == MarketRegime.RANGE_BOUND:
            # 70% mean-reversion, 30% breakout (for range breaks)
            return {
                "trend": Decimal("0"),
                "mean_reversion": total_capital * Decimal("0.70"),
                "breakout": total_capital * Decimal("0.30")
            }

        else:
            # Reduce exposure in uncertain regimes
            return {
                "trend": total_capital * Decimal("0.30"),
                "mean_reversion": total_capital * Decimal("0.30"),
                "breakout": total_capital * Decimal("0.20")
            }
```

### Pattern 2: Dynamic Stop Loss Sizing

```python
def calculate_stop_distance(regime: MarketRegime, atr: Decimal) -> Decimal:
    """Adjust stop loss based on regime."""

    if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND]:
        # Wider stops in strong trends (let winners run)
        return atr * Decimal("2.5")

    elif regime in [MarketRegime.WEAK_UPTREND, MarketRegime.WEAK_DOWNTREND]:
        # Moderate stops in weak trends
        return atr * Decimal("1.5")

    elif regime == MarketRegime.RANGE_BOUND:
        # Tight stops in ranges (quick exits on breakout)
        return atr * Decimal("1.0")

    else:
        # Very tight stops in high volatility (protect capital)
        return atr * Decimal("0.75")
```

### Pattern 3: Regime-Filtered Signals

```python
def filter_signal_by_regime(signal: Signal, regime: MarketRegime) -> bool:
    """Accept or reject signal based on regime compatibility."""

    # Only take long breakouts in uptrend or range (not downtrend)
    if signal.side == "buy" and signal.reason.contains("breakout"):
        return regime in [
            MarketRegime.STRONG_UPTREND,
            MarketRegime.WEAK_UPTREND,
            MarketRegime.RANGE_BOUND
        ]

    # Only take short breakdowns in downtrend or range (not uptrend)
    if signal.side == "sell" and signal.reason.contains("breakdown"):
        return regime in [
            MarketRegime.STRONG_DOWNTREND,
            MarketRegime.WEAK_DOWNTREND,
            MarketRegime.RANGE_BOUND
        ]

    # Reject all signals in high volatility
    if regime == MarketRegime.HIGH_VOLATILITY:
        return False

    return True
```

## Performance Considerations

### Computational Cost

- **ADX Calculation**: O(n) with 14-period smoothing
- **Hurst Exponent**: O(n log n) with R/S analysis (most expensive)
- **Price Structure**: O(n) with swing detection

**Optimization Tips**:
- Cache ADX and Hurst calculations (only recalculate on new bar)
- Use incremental updates for rolling windows
- Limit Hurst lookback to 100-200 bars (diminishing returns beyond that)

### Update Frequency

- **Real-time**: Update on every bar (recommended)
- **Batch**: Update every N bars (for performance)

**Trade-off**: More frequent updates = more responsive but more CPU usage.

### Accuracy vs Lag

- **High Accuracy**: Longer ADX period (20), longer Hurst lookback (200)
- **Low Lag**: Shorter ADX period (10), shorter Hurst lookback (50)

**Recommendation**: Use standard parameters (ADX=14, Hurst=100) for balance.

## Backtesting Tips

1. **Validate Regime Classification**
   - Manually label historical regimes
   - Compare detector output to manual labels
   - Aim for >75% agreement

2. **Test Regime Transitions**
   - Track how often regimes change
   - Too frequent = overfitting (reduce sensitivity)
   - Too infrequent = lagging (increase sensitivity)

3. **Strategy Performance by Regime**
   - Break down backtest by regime
   - Confirm trend strategies work in TREND regimes
   - Confirm mean-reversion works in RANGE regimes

4. **Forward Testing**
   - Paper trade for 30-60 days
   - Track regime changes in real-time
   - Validate that transitions make intuitive sense

## Common Mistakes

### ❌ Mistake 1: Over-Relying on Single Indicator

**Wrong**: Using only ADX for regime detection
**Right**: Combine ADX + Hurst + Price Structure

### ❌ Mistake 2: Ignoring Regime Lag

**Wrong**: Assuming regime detector catches tops/bottoms
**Right**: Accept lag as trade-off for accuracy

### ❌ Mistake 3: Trading Every Regime Change

**Wrong**: Rotating portfolio on every regime shift
**Right**: Require sustained regime change (2-3 bars confirmation)

### ❌ Mistake 4: Not Adapting Parameters

**Wrong**: Using same parameters for all assets/timeframes
**Right**: Tune ADX, Hurst, and swing lookback per asset

## Advanced Topics

### Regime Strength Scoring

Add confidence scores to regimes:

```python
def calculate_regime_strength(adx, hurst, price_structure) -> Decimal:
    """Score regime conviction (0-100)."""

    score = Decimal("0")

    # ADX contribution (max 40 points)
    if adx > 40:
        score += Decimal("40")
    elif adx > 30:
        score += Decimal("30")
    elif adx > 25:
        score += Decimal("20")

    # Hurst contribution (max 30 points)
    if hurst > 0.65:
        score += Decimal("30")
    elif hurst > 0.55:
        score += Decimal("20")

    # Price structure contribution (max 30 points)
    if price_structure == "perfect":  # All HH/HL or all LH/LL
        score += Decimal("30")
    elif price_structure == "mostly_consistent":
        score += Decimal("20")

    return score

# Usage
strength = calculate_regime_strength(adx=32, hurst=0.68, price_structure="perfect")
if strength > 70:
    print("🔥 High-confidence regime - increase position size")
```

### Regime Duration Analysis

Track how long regimes persist:

```python
class RegimeTracker:
    def __init__(self):
        self.current_regime = None
        self.regime_start_time = None
        self.regime_durations = {}

    def update(self, new_regime, timestamp):
        if new_regime != self.current_regime:
            # Regime changed
            if self.current_regime is not None:
                duration = timestamp - self.regime_start_time
                self.regime_durations[self.current_regime] = duration

            self.current_regime = new_regime
            self.regime_start_time = timestamp

    def get_avg_duration(self, regime):
        """Get average duration for a regime type."""
        durations = [d for r, d in self.regime_durations.items() if r == regime]
        return sum(durations) / len(durations) if durations else 0

# Insight: If current regime duration >> average, regime change likely
```

### Machine Learning Enhancement

Use regime as a feature in ML models:

```python
features = {
    "regime": regime_detector.get_current_regime().value,
    "adx": adx_value,
    "hurst": hurst_value,
    "regime_duration": time_in_current_regime,
    "regime_changes_last_week": regime_change_count,
    ...
}

# ML model learns which strategies work best in which regimes
prediction = ml_model.predict(features)
```

## Troubleshooting

### Issue: Regime Changes Too Frequently

**Symptom**: Regime flips every 2-3 bars

**Solution**:
- Increase ADX period (14 → 20)
- Increase Hurst lookback (100 → 150)
- Add regime change confirmation (require 2-3 bars)

### Issue: Regime Detection Lags Too Much

**Symptom**: Detects trend after it's already halfway over

**Solution**:
- Decrease ADX period (14 → 10)
- Use leading indicators (momentum, volume)
- Accept faster response = more false signals

### Issue: Always Showing UNKNOWN

**Symptom**: Detector never classifies into meaningful regime

**Causes**:
- Insufficient data (need 100+ bars minimum)
- Thresholds too strict (ADX always below 25)

**Solution**: Lower thresholds or add more data

## Further Reading

- **ADX**: "New Concepts in Technical Trading Systems" (Wilder, 1978)
- **Hurst Exponent**: "Fractal Market Analysis" (Peters, 1994)
- **Regime Detection**: "Algorithmic Trading" (Chan, 2013)

## Summary

The Market Regime Detector is essential for:
- ✅ Adapting strategies to market conditions
- ✅ Improving risk management
- ✅ Increasing win rates through regime-aware trading
- ✅ Building robust multi-strategy portfolios

**Best used as**:
- Filter for other strategies (only trade compatible regimes)
- Portfolio allocation tool (rotate capital by regime)
- Risk management tool (adjust stops/sizes by regime)

**Not recommended for**:
- Standalone signal generation (use as filter, not primary signal)
- Ultra-short timeframes (<1 min - too noisy)
- Low-liquidity assets (regime changes may not be reliable)
