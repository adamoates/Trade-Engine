# Trading Strategies

This directory contains documentation for all implemented trading strategies.

## 🎯 Primary Strategy

### [L2 Order Book Imbalance](l2-imbalance.md)
**Status**: Production-ready | **Type**: Scalping | **Timeframe**: Sub-minute

The primary strategy for crypto futures trading using Level 2 order book analysis.
- Buy signal: Bid/Ask volume ratio > 3.0x (strong buying pressure)
- Sell signal: Bid/Ask volume ratio < 0.33x (strong selling pressure)
- Target: $50-100/day on $10K capital
- Win rate: 52-58% (target 55%+)

## 📊 Secondary Strategies

### [Breakout Detector](breakout-detector.md)
**Status**: Production-ready | **Type**: Breakout | **Timeframe**: Multi-day

7-factor breakout setup detection with comprehensive confirmation signals.
- Identifies high-probability breakout setups
- Combines price action, volume, and technical indicators
- 919 tests, high coverage

### [Open Interest & Funding](open-interest-funding.md)
**Status**: Production-ready | **Type**: Derivatives | **Timeframe**: Hourly+

Analyzes derivatives market structure for trading signals.
- Open interest analysis
- Funding rate tracking
- Liquidation cascade detection

### [Regime Detector](regime-detector.md)
**Status**: Production-ready | **Type**: Market Classification | **Timeframe**: Multi-bar

Classifies market regime to adapt strategy parameters.
- Trending vs ranging detection
- Volatility regime classification
- Strategy adaptation logic

### [Volume RVOL](volume-rvol.md)
**Status**: Production-ready | **Type**: Volume Analysis | **Timeframe**: Intraday

Relative volume analysis for confirmation signals.
- RVOL calculation and thresholds
- Volume spike detection
- Integration with other strategies

### [Multi-Factor Screener](multi-factor-screener.md)
**Status**: Production-ready | **Type**: Stock Screening | **Timeframe**: Daily

7-factor stock screening for equity trading opportunities.
- Breakout, volume, MA, MACD, RSI, gain, market cap factors
- Identifies stocks with confluent signals
- Yahoo Finance integration

## 🔧 Strategy Configuration

### [Configuration Examples](configuration-examples.md)
Real-world configuration examples for all strategies.
- JSON/YAML configuration formats
- Parameter tuning guidelines
- Multi-strategy portfolios

### [Spot-Only Trading](spot-only-trading.md)
Trading on spot exchanges without margin/shorting.
- Automatic short signal filtering
- Long-only mode configuration
- Binance.us integration

## 📈 Strategy Comparison

| Strategy | Type | Timeframe | Win Rate | Risk/Reward | Complexity |
|----------|------|-----------|----------|-------------|------------|
| L2 Imbalance | Scalping | <1 min | 55%+ | 1.33:1 | High |
| Breakout Detector | Breakout | Multi-day | TBD | TBD | Medium |
| Open Interest | Derivatives | Hourly+ | TBD | TBD | Medium |
| Regime Detector | Classification | Multi-bar | N/A | N/A | Low |
| Volume RVOL | Volume | Intraday | N/A | N/A | Low |
| Multi-Factor | Screening | Daily | TBD | TBD | Low |

## 🎓 Learning Path

**New to algorithmic trading?**
1. Start with [Multi-Factor Screener](multi-factor-screener.md) - Easiest to understand
2. Learn [Breakout Detector](breakout-detector.md) - Classic pattern recognition
3. Study [L2 Imbalance](l2-imbalance.md) - Advanced order book analysis

**Ready to trade?**
1. Paper trade for 60 days minimum (NON-NEGOTIABLE)
2. Verify win rate >50% and profit factor >1.0
3. Start with micro-capital ($100-500) for 30 days
4. Scale up gradually after proven success

## 🔬 Backtesting Strategies

All strategies can be backtested using the backtesting engine:

```bash
# Backtest L2 strategy
python scripts/backtest_l2_strategy.py

# Backtest with custom config
python scripts/backtest_strategy.py --strategy breakout --config config.yaml
```

See [data pipeline documentation](../data/pipeline-overview.md) for data preparation.

## ⚠️ Risk Management

All strategies are subject to hard risk limits (NON-NEGOTIABLE):
- **Max Position Size**: $10,000
- **Daily Loss Limit**: -$500 (triggers kill switch)
- **Max Drawdown**: -$1,000 (triggers kill switch)
- **Position Hold Time**: 60 seconds max (L2 strategy)

See [CLAUDE.md](../../.claude/CLAUDE.md) for complete risk management rules.

## 📚 Further Reading

- [Strategy implementation patterns](../../.claude/CLAUDE.md#strategy-implementation-pattern)
- [Data pipeline for strategies](../data/pipeline-overview.md)
- [Broker integration](../brokers/)
- [Backtesting guide](../data/fixtures.md)

---

**Remember**: No strategy is guaranteed to be profitable. Always paper trade first and never risk more than you can afford to lose.
