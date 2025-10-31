# Strategy Configuration Examples

This document provides complete configuration examples for all alpha strategies in the trading engine.

## Table of Contents

1. [Volume RVOL Strategy](#volume-rvol-strategy)
2. [Open Interest + Funding Rate Strategy](#open-interest--funding-rate-strategy)
3. [Regime Detector Strategy](#regime-detector-strategy)
4. [Breakout Detector Strategy](#breakout-detector-strategy)
5. [Multi-Strategy Portfolio](#multi-strategy-portfolio)
6. [Environment Variables](#environment-variables)

---

## Volume RVOL Strategy

### Conservative Configuration (Fewer, High-Quality Signals)

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_volume_rvol import (
    VolumeRVOLStrategy,
    VolumeRVOLConfig
)

config = VolumeRVOLConfig(
    # RVOL Detection
    rvol_threshold=Decimal("3.0"),  # Require 3× volume spike (conservative)
    lookback_bars=30,  # Longer lookback for stability

    # Signal Generation
    price_change_threshold=Decimal("0.01"),  # 1% price move required
    min_volume_absolute=Decimal("1000000"),  # Min $1M volume (filter low-liquidity)

    # Position Sizing
    position_size_usd=Decimal("1000"),  # $1K per trade
    risk_pct=Decimal("0.01"),  # 1% risk

    # Stop Loss / Take Profit
    atr_multiplier_sl=Decimal("2.0"),  # Wider stops (2× ATR)
    atr_multiplier_tp=Decimal("4.0")  # 2:1 R:R
)

strategy = VolumeRVOLStrategy(symbol="BTCUSDT", config=config)
```

### Aggressive Configuration (More Signals, Tighter Stops)

```python
config = VolumeRVOLConfig(
    # RVOL Detection
    rvol_threshold=Decimal("1.5"),  # Lower threshold for more signals
    lookback_bars=10,  # Shorter lookback (more responsive)

    # Signal Generation
    price_change_threshold=Decimal("0.003"),  # 0.3% price move
    min_volume_absolute=Decimal("0"),  # No minimum volume filter

    # Position Sizing
    position_size_usd=Decimal("500"),  # Smaller size (more signals)
    risk_pct=Decimal("0.005"),  # 0.5% risk per trade

    # Stop Loss / Take Profit
    atr_multiplier_sl=Decimal("1.0"),  # Tight stops (1× ATR)
    atr_multiplier_tp=Decimal("2.0")  # 2:1 R:R
)

strategy = VolumeRVOLStrategy(symbol="ETHUSDT", config=config)
```

### Scalping Configuration (Short-Term)

```python
config = VolumeRVOLConfig(
    # RVOL Detection
    rvol_threshold=Decimal("2.5"),  # Moderate threshold
    lookback_bars=15,  # Short lookback for fast markets

    # Signal Generation
    price_change_threshold=Decimal("0.002"),  # 0.2% minimum move
    min_volume_absolute=Decimal("0"),

    # Position Sizing
    position_size_usd=Decimal("2000"),  # Larger size for scalping
    risk_pct=Decimal("0.005"),  # 0.5% risk (tight)

    # Stop Loss / Take Profit
    atr_multiplier_sl=Decimal("0.75"),  # Very tight stops
    atr_multiplier_tp=Decimal("1.5")  # Quick profits
)

strategy = VolumeRVOLStrategy(symbol="BTCUSDT", config=config)
```

---

## Open Interest + Funding Rate Strategy

### Conservative Configuration (High-Conviction Signals)

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_open_interest_funding import (
    OpenInterestFundingStrategy,
    OpenInterestFundingConfig
)

config = OpenInterestFundingConfig(
    # Open Interest Thresholds
    oi_increase_threshold=Decimal("0.08"),  # 8% OI increase (conservative)
    oi_decrease_threshold=Decimal("-0.08"),  # 8% OI decrease
    oi_lookback_hours=6,  # Longer lookback (smoother signals)

    # Funding Rate Thresholds
    funding_positive_min=Decimal("0.0002"),  # 0.02% minimum positive
    funding_positive_max=Decimal("0.0008"),  # 0.08% extreme (lower threshold)
    funding_negative_min=Decimal("-0.0002"),  # -0.02% minimum negative
    funding_negative_max=Decimal("-0.0008"),  # -0.08% extreme

    # Price Change Threshold
    price_change_threshold=Decimal("0.015"),  # 1.5% price move required

    # Position Sizing
    position_size_usd=Decimal("2000"),  # $2K per trade
    risk_pct=Decimal("0.01"),  # 1% risk

    # Stop Loss / Take Profit
    sl_pct=Decimal("0.025"),  # 2.5% stop
    tp_pct=Decimal("0.05")  # 5% target (2:1 R:R)
)

strategy = OpenInterestFundingStrategy(symbol="BTCUSDT", config=config)
```

### Moderate Configuration (Balanced)

```python
config = OpenInterestFundingConfig(
    # Open Interest Thresholds
    oi_increase_threshold=Decimal("0.05"),  # 5% OI increase (standard)
    oi_decrease_threshold=Decimal("-0.05"),
    oi_lookback_hours=4,  # 4 hours (default)

    # Funding Rate Thresholds
    funding_positive_min=Decimal("0.0001"),  # 0.01% per 8h
    funding_positive_max=Decimal("0.0010"),  # 0.10% extreme
    funding_negative_min=Decimal("-0.0001"),
    funding_negative_max=Decimal("-0.0010"),

    # Price Change Threshold
    price_change_threshold=Decimal("0.01"),  # 1% price move

    # Position Sizing
    position_size_usd=Decimal("1000"),
    risk_pct=Decimal("0.01"),

    # Stop Loss / Take Profit
    sl_pct=Decimal("0.02"),  # 2% stop
    tp_pct=Decimal("0.04")  # 4% target
)

strategy = OpenInterestFundingStrategy(symbol="ETHUSDT", config=config)
```

### Crypto Futures Configuration (High Volatility)

```python
config = OpenInterestFundingConfig(
    # Open Interest Thresholds
    oi_increase_threshold=Decimal("0.07"),  # 7% (crypto moves fast)
    oi_decrease_threshold=Decimal("-0.07"),
    oi_lookback_hours=4,

    # Funding Rate Thresholds
    funding_positive_min=Decimal("0.0002"),
    funding_positive_max=Decimal("0.0015"),  # 0.15% (higher extreme for crypto)
    funding_negative_min=Decimal("-0.0002"),
    funding_negative_max=Decimal("-0.0015"),

    # Price Change Threshold
    price_change_threshold=Decimal("0.015"),  # 1.5% (crypto volatility)

    # Position Sizing
    position_size_usd=Decimal("1500"),
    risk_pct=Decimal("0.015"),  # 1.5% risk (higher volatility)

    # Stop Loss / Take Profit
    sl_pct=Decimal("0.03"),  # 3% stop (wider for crypto)
    tp_pct=Decimal("0.06")  # 6% target
)

strategy = OpenInterestFundingStrategy(symbol="BTCUSDT", config=config)
```

---

## Regime Detector Strategy

### Standard Configuration

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_regime_detector import (
    RegimeDetectorStrategy,
    RegimeDetectorConfig
)

config = RegimeDetectorConfig(
    # ADX Calculation
    adx_period=14,  # Standard ADX period
    adx_trend_threshold=Decimal("25"),  # ADX > 25 = trending
    adx_weak_threshold=Decimal("20"),  # ADX < 20 = ranging

    # Hurst Exponent Calculation
    hurst_lookback=100,  # 100 bars for Hurst
    hurst_trend_threshold=Decimal("0.55"),  # H > 0.55 = trending
    hurst_mean_revert_threshold=Decimal("0.45"),  # H < 0.45 = mean-revert

    # Price Structure
    swing_lookback=10,  # 10 bars for swing detection

    # Volatility Detection
    atr_period=14,
    atr_volatility_multiplier=Decimal("2.0"),  # ATR > 2× avg = high vol

    # Signal Generation (optional)
    emit_signals_on_change=False,  # Don't generate signals (use as filter only)
    position_size_usd=Decimal("1000")
)

regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT", config=config)
```

### High-Sensitivity Configuration (Faster Response)

```python
config = RegimeDetectorConfig(
    # ADX Calculation
    adx_period=10,  # Shorter period (more responsive)
    adx_trend_threshold=Decimal("22"),  # Lower threshold
    adx_weak_threshold=Decimal("18"),

    # Hurst Exponent
    hurst_lookback=50,  # Shorter lookback (faster)
    hurst_trend_threshold=Decimal("0.52"),  # Lower trend threshold
    hurst_mean_revert_threshold=Decimal("0.48"),

    # Price Structure
    swing_lookback=7,  # Shorter swing detection

    # Volatility Detection
    atr_period=10,
    atr_volatility_multiplier=Decimal("1.5"),  # Lower volatility threshold

    # Signal Generation
    emit_signals_on_change=True,  # Generate signals on regime change
    position_size_usd=Decimal("500")
)

regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT", config=config)
```

### Low-Sensitivity Configuration (Smoother, Less False Changes)

```python
config = RegimeDetectorConfig(
    # ADX Calculation
    adx_period=20,  # Longer period (smoother)
    adx_trend_threshold=Decimal("28"),  # Higher threshold
    adx_weak_threshold=Decimal("22"),

    # Hurst Exponent
    hurst_lookback=200,  # Longer lookback (more stable)
    hurst_trend_threshold=Decimal("0.58"),  # Higher trend threshold
    hurst_mean_revert_threshold=Decimal("0.42"),

    # Price Structure
    swing_lookback=15,  # Longer swing detection

    # Volatility Detection
    atr_period=20,
    atr_volatility_multiplier=Decimal("2.5"),  # Higher volatility threshold

    # Signal Generation
    emit_signals_on_change=False,  # Filter only
    position_size_usd=Decimal("2000")
)

regime_detector = RegimeDetectorStrategy(symbol="BTCUSDT", config=config)
```

---

## Breakout Detector Strategy

### Day Trading Configuration

```python
from decimal import Decimal
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutDetectorStrategy,
    BreakoutDetectorConfig
)

config = BreakoutDetectorConfig(
    # Consolidation Detection
    consolidation_bars_min=12,  # 12 bars minimum (1 hour if 5-min bars)
    consolidation_bars_max=72,  # 6 hours maximum
    range_pct_threshold=Decimal("0.02"),  # 2% range for consolidation

    # Volume Confirmation
    volume_spike_threshold=Decimal("1.5"),  # 1.5× volume required

    # MACD Settings
    macd_fast=12,
    macd_slow=26,
    macd_signal=9,

    # Filters
    rsi_overbought=75,  # Less strict (allow more signals)
    rsi_oversold=25,
    min_confidence=Decimal("0.40"),  # Lower confidence threshold

    # Position Sizing
    position_size_usd=Decimal("1000"),
    risk_pct=Decimal("0.01"),

    # Risk Management
    sl_pct=Decimal("0.015"),  # 1.5% stop
    tp_pct=Decimal("0.03")  # 3% target
)

strategy = BreakoutDetectorStrategy(symbol="BTCUSDT", config=config)
```

---

## Multi-Strategy Portfolio

### Complete Portfolio Configuration

```python
from decimal import Decimal
from typing import Dict
from trade_engine.domain.strategies.alpha_regime_detector import RegimeDetectorStrategy
from trade_engine.domain.strategies.alpha_breakout_detector import BreakoutDetectorStrategy
from trade_engine.domain.strategies.alpha_volume_rvol import VolumeRVOLStrategy
from trade_engine.domain.strategies.alpha_open_interest_funding import OpenInterestFundingStrategy

class TradingPortfolio:
    """Complete multi-strategy trading portfolio."""

    def __init__(self, symbol: str, total_capital: Decimal):
        self.symbol = symbol
        self.total_capital = total_capital

        # Regime Detector (filter)
        self.regime = RegimeDetectorStrategy(symbol=symbol)

        # Alpha Strategies
        self.strategies = {
            "breakout": BreakoutDetectorStrategy(symbol=symbol),
            "volume": VolumeRVOLStrategy(symbol=symbol),
            "oi_funding": OpenInterestFundingStrategy(symbol=symbol)
        }

    def allocate_capital(self) -> Dict[str, Decimal]:
        """Allocate capital based on regime."""
        from trade_engine.domain.strategies.alpha_regime_detector import MarketRegime

        regime = self.regime.get_current_regime()

        if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND]:
            # 60% trend-following, 20% volume, 20% OI
            return {
                "breakout": self.total_capital * Decimal("0.60"),
                "volume": self.total_capital * Decimal("0.20"),
                "oi_funding": self.total_capital * Decimal("0.20")
            }

        elif regime == MarketRegime.RANGE_BOUND:
            # Reduce trend-following in ranges
            return {
                "breakout": self.total_capital * Decimal("0.30"),
                "volume": self.total_capital * Decimal("0.30"),
                "oi_funding": self.total_capital * Decimal("0.40")
            }

        else:
            # Conservative allocation in uncertain regimes
            return {
                "breakout": self.total_capital * Decimal("0.30"),
                "volume": self.total_capital * Decimal("0.30"),
                "oi_funding": self.total_capital * Decimal("0.30")
            }

# Usage
portfolio = TradingPortfolio(
    symbol="BTCUSDT",
    total_capital=Decimal("10000")
)

# Get current allocation
allocation = portfolio.allocate_capital()
print(f"Breakout: ${allocation['breakout']}")
print(f"Volume: ${allocation['volume']}")
print(f"OI+Funding: ${allocation['oi_funding']}")
```

---

## Environment Variables

### Required for Live Trading

```bash
# Binance API (for derivatives data)
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"

# Kraken API (for derivatives data)
export KRAKEN_API_KEY="your_api_key_here"
export KRAKEN_API_SECRET="your_api_secret_here"

# Database (for trade persistence)
export DATABASE_URL="postgresql://user:password@localhost:5432/trading_db"

# Logging
export LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
export LOG_FILE="logs/trading.log"

# Risk Management
export MAX_POSITION_SIZE_USD="10000"
export MAX_DAILY_LOSS_USD="500"
export MAX_DRAWDOWN_USD="1000"

# Strategy Selection
export ENABLE_BREAKOUT_STRATEGY="true"
export ENABLE_VOLUME_STRATEGY="true"
export ENABLE_OI_FUNDING_STRATEGY="true"
export ENABLE_REGIME_DETECTOR="true"
```

### Configuration File (.env)

```ini
# .env file (place in project root)

# API Credentials
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
KRAKEN_API_KEY=your_key
KRAKEN_API_SECRET=your_secret

# Trading Symbols
PRIMARY_SYMBOL=BTCUSDT
SECONDARY_SYMBOLS=ETHUSDT,BNBUSDT

# Risk Management
MAX_POSITION_SIZE_USD=10000
MAX_DAILY_LOSS_USD=500
MAX_DRAWDOWN_USD=1000
POSITION_SIZE_PCT=0.01

# Strategy Parameters
RVOL_THRESHOLD=2.0
OI_THRESHOLD=0.05
ADX_THRESHOLD=25
HURST_THRESHOLD=0.55

# Execution
EXECUTION_MODE=simulated  # simulated | paper | live
UPDATE_INTERVAL_SECONDS=300
ENABLE_EMAIL_ALERTS=true
ALERT_EMAIL=your_email@example.com
```

### Loading Configuration

```python
import os
from decimal import Decimal
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access configuration
api_key = os.getenv("BINANCE_API_KEY")
max_position = Decimal(os.getenv("MAX_POSITION_SIZE_USD", "10000"))
rvol_threshold = Decimal(os.getenv("RVOL_THRESHOLD", "2.0"))

# Validate required variables
required_vars = ["BINANCE_API_KEY", "BINANCE_API_SECRET"]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")
```

---

## Configuration by Market Type

### Cryptocurrency (High Volatility)

```python
# Crypto requires wider stops and higher thresholds
crypto_params = {
    "rvol_threshold": Decimal("2.5"),  # Higher baseline volume
    "oi_threshold": Decimal("0.07"),  # Larger OI moves
    "sl_pct": Decimal("0.03"),  # 3% stops
    "tp_pct": Decimal("0.06"),  # 6% targets
    "funding_extreme": Decimal("0.0015")  # 0.15% extreme
}
```

### Stock Index Futures (Moderate Volatility)

```python
# Stock indices are more stable
stock_params = {
    "rvol_threshold": Decimal("2.0"),
    "oi_threshold": Decimal("0.04"),  # Smaller OI moves
    "sl_pct": Decimal("0.015"),  # 1.5% stops
    "tp_pct": Decimal("0.03"),  # 3% targets
    "funding_extreme": Decimal("0.0005")  # 0.05% extreme
}
```

### Commodities (Low to Moderate Volatility)

```python
# Commodities vary widely by type
commodity_params = {
    "rvol_threshold": Decimal("2.0"),
    "oi_threshold": Decimal("0.03"),  # Very stable OI
    "sl_pct": Decimal("0.02"),  # 2% stops
    "tp_pct": Decimal("0.04"),  # 4% targets
    "funding_extreme": Decimal("0.0003")  # 0.03% extreme
}
```

---

## Best Practices

### 1. Start Conservative

Begin with conservative configurations and gradually increase aggressiveness as you gain confidence:

```python
# Week 1-2: Very conservative
config = VolumeRVOLConfig(rvol_threshold=Decimal("3.5"))

# Week 3-4: Conservative
config = VolumeRVOLConfig(rvol_threshold=Decimal("3.0"))

# Week 5+: Moderate (only if performance is good)
config = VolumeRVOLConfig(rvol_threshold=Decimal("2.5"))
```

### 2. Backtest All Configurations

Before deploying any configuration, backtest it:

```python
# Run 60-90 day backtest minimum
# Validate across multiple market conditions
# Check key metrics: win rate, profit factor, max drawdown
```

### 3. Use Paper Trading

Paper trade for 30-60 days before live trading:

```python
# Set execution mode to paper
EXECUTION_MODE="paper"

# Track performance in real-time without risk
```

### 4. Monitor and Adjust

Continuously monitor strategy performance and adjust parameters:

```python
# Weekly review checklist:
# - Win rate by strategy
# - Signal frequency
# - Average R:R
# - Max drawdown
# - Regime classification accuracy
```

---

## Summary

- **Conservative configs**: Fewer signals, higher quality, wider stops
- **Aggressive configs**: More signals, tighter stops, higher risk
- **Crypto**: Higher thresholds, wider stops (volatility)
- **Stocks**: Lower thresholds, tighter stops (stability)
- **Always backtest** before deploying new configurations
- **Start conservative** and gradually increase aggression
- **Paper trade** for 30-60 days minimum
