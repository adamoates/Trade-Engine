# 4-Hour Live Trading POC - Implementation Plan

## Objective
Demonstrate the trading bot can achieve $1.50/hour profit rate over 4 hours with $500 capital on Binance Testnet.

**Target**: $6 profit in 4 hours (1.2% return)

## Timeline
- **Setup & Development**: 3-4 hours
- **Live Test Execution**: 4 hours
- **Analysis & Reporting**: 30 minutes

## Architecture Components Needed

### 1. Live Data Stream ✅ (In Progress)
- WebSocket connection to Binance for real-time 5m candles
- Graceful reconnection handling
- Candle aggregation and validation

### 2. Position Manager (New)
- Track open positions
- Calculate unrealized P&L
- Position sizing logic
- Entry/exit price tracking

### 3. Simple Strategy (Use Existing)
- Moving Average Crossover (simplest, most reliable)
- Entry: Fast MA crosses above Slow MA (bullish)
- Exit: Fast MA crosses below Slow MA or stop loss hit

### 4. Trading Runner (New)
- Main event loop
- Wait for candle close
- Generate signals from strategy
- Execute trades via Binance broker
- Track performance metrics
- Periodic reporting

### 5. Performance Tracker (New)
- Real-time P&L calculation
- Win rate tracking
- Hourly performance breakdown
- JSON export for stakeholders

## Configuration

```yaml
capital: $500
max_position_size: $150 (30%)
stop_loss: 1%
take_profit: 1.5%
symbols: [BTCUSDT, ETHUSDT]
timeframe: 5m
strategy: ma_crossover (9/21)
```

## Exit Conditions
1. **Success**: P&L >= $6.00
2. **Failure**: P&L <= -$15.00 (3% max loss)
3. **Time**: 4 hours elapsed

## Risk Management
- Max 30% capital per position
- 1% stop loss per trade
- Max 3 concurrent positions
- Auto-stop if daily loss > $15

## Deliverables
1. Live trading logs (timestamped)
2. Performance JSON report
3. Trade-by-trade breakdown
4. Hourly P&L chart
5. Final stakeholder summary

## Development Priority
1. ✅ Data stream (WebSocket)
2. Position manager
3. Trading runner with MA strategy
4. End-to-end testing
5. 4-hour live run

## Success Criteria
- Bot runs for full 4 hours without crashes
- All trades logged and tracked
- Final report generated
- Preferably: $6+ profit achieved
