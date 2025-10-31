# Logging Guide

Comprehensive guide to the Trade Engine logging system.

## Overview

The Trade Engine uses a structured logging system designed to scale from local development to production. All logs are JSON-formatted with consistent fields for:

- **Post-trade analysis**: Review trading decisions and performance
- **Debugging**: Trace issues with full context
- **Compliance**: Immutable audit trail of all trades
- **Monitoring**: Real-time alerts and dashboards

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Trade Engine Application                   │
├─────────────────────────────────────────────────────────────┤
│  Modules use:                                                │
│  - get_logger(__name__) for general logging                 │
│  - TradingLogger() for standardized trading events          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Loguru + Structlog        │
         │   (JSON formatter)          │
         └──────────┬──────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐     ┌──────────────────┐
│   Console     │     │   Log Files       │
│   (stderr)    │     │   logs/           │
│               │     │   ├── trade_engine_*.log  (all)
│   Dev: Pretty │     │   ├── trades_*.log       (trading only)
│   Prod: JSON  │     │   └── errors_*.log       (warnings+)
└───────────────┘     └──────────────────┘
```

### Phase Roadmap

**Phase 0-2 (Current)**: Local JSON logs
- Files rotated daily, kept for 90 days
- Manual analysis with jq/grep
- Trading logs separated for audit

**Phase 3**: Centralized logging
- Push logs to Postgres/TimescaleDB
- Build Grafana dashboards
- Real-time Slack/Telegram alerts

**Phase 4**: Event-sourced ledger
- Kafka + Postgres for immutable trade log
- Compliance snapshots to S3
- Full trade replay capability

## Quick Start

### Initialization

**IMPORTANT**: You must explicitly initialize logging at application startup:

```python
from trade_engine.core.logging_config import configure_logging
import os

# In main.py or application entry point
if __name__ == "__main__":
    configure_logging(
        level=os.getenv("TRADE_ENGINE_LOG_LEVEL", "INFO"),
        serialize=os.getenv("TRADE_ENGINE_LOG_JSON", "false").lower() == "true"
    )
    # ... start application
```

### Basic Logging

```python
from trade_engine.core.logging_config import get_logger

logger = get_logger(__name__)

# General logs (any module)
logger.debug("Calculating signals", symbol="BTC/USDT", count=5)
logger.info("Strategy initialized", strategy_id="l2_imbalance_v1")
logger.warning("API rate limit approaching", remaining=10, limit=100)
logger.error("Order rejected", error="Insufficient funds", order_id="12345")
```

### Trading Event Logging

For standardized trading events, use `TradingLogger`:

```python
from decimal import Decimal
from trade_engine.core.logging_config import TradingLogger

# Initialize with optional strategy ID
trade_logger = TradingLogger(strategy_id="l2_imbalance_v1")

# Order placed
trade_logger.order_placed(
    symbol="BTC/USDT",
    side="BUY",
    size=Decimal("0.1"),
    price=Decimal("45000.00"),
    order_type="LIMIT",
    order_id="order_123"
)

# Order filled
trade_logger.order_filled(
    symbol="BTC/USDT",
    side="BUY",
    size=Decimal("0.1"),
    fill_price=Decimal("45000.00"),
    order_id="order_123",
    commission=Decimal("4.50")
)

# Order cancelled
trade_logger.order_cancelled(
    symbol="BTC/USDT",
    side="BUY",
    order_id="order_123",
    reason="User requested cancellation"
)

# Position opened
trade_logger.position_opened(
    symbol="BTC/USDT",
    side="LONG",
    size=Decimal("0.1"),
    entry_price=Decimal("45000.00"),
    position_id="pos_456"
)

# Position closed
trade_logger.position_closed(
    symbol="BTC/USDT",
    side="LONG",
    size=Decimal("0.1"),
    entry_price=Decimal("45000.00"),
    exit_price=Decimal("45900.00"),
    pnl=Decimal("90.00"),
    position_id="pos_456"
)

# Risk events
trade_logger.risk_limit_breached(
    limit_type="daily_loss",
    current_value=Decimal("-520"),
    limit_value=Decimal("-500"),
    action="KILL_SWITCH_TRIGGERED"
)

trade_logger.kill_switch_triggered(
    reason="Daily loss limit breached",
    metric_value=Decimal("-520"),
    limit_value=Decimal("-500")
)

# PnL updates
trade_logger.pnl_update(
    symbol="BTC/USDT",
    realized_pnl=Decimal("90.00"),
    unrealized_pnl=Decimal("15.00"),
    total_pnl=Decimal("105.00")
)
```

## Configuration

### Development (Default)

```python
from trade_engine.core.logging_config import configure_logging

configure_logging(
    level="DEBUG",
    enable_console=True,
    enable_file=True,
    serialize=False  # Human-readable console output
)
```

### Production

```python
configure_logging(
    level="INFO",
    enable_console=True,
    enable_file=True,
    serialize=True,  # JSON format for parsing
    rotation="1 day",
    retention="90 days",
    compression="zip"
)
```

### Environment Variables

Set logging behavior via environment:

```bash
# Log level
export TRADE_ENGINE_LOG_LEVEL=INFO

# Log directory
export TRADE_ENGINE_LOG_DIR=/var/log/trade-engine

# Enable JSON format
export TRADE_ENGINE_LOG_JSON=true
```

## Log Formats

### Console Output (Development)

```
2025-10-29 20:45:30.123 | INFO     | trade_engine.domain.strategies.alpha_l2_imbalance:generate_signals:145 | Signal generated
```

### JSON Output (Production)

```json
{
  "text": "order_placed",
  "record": {
    "time": {
      "repr": "2025-10-29 20:45:30.123456+00:00",
      "timestamp": 1730229930.123456
    },
    "level": {
      "name": "INFO",
      "no": 20
    },
    "message": "order_placed",
    "extra": {
      "event": "order_placed",
      "symbol": "BTC/USDT",
      "side": "BUY",
      "size": "0.1",
      "price": "45000.00",
      "order_type": "LIMIT",
      "order_id": "order_123",
      "strategy_id": "l2_imbalance_v1"
    }
  }
}
```

**Note**: Loguru automatically adds timestamps, so `TradingLogger` does not add redundant timestamp fields.

## Log Files

### `logs/trade_engine_*.log`

All application logs (DEBUG+). Use for debugging and development.

```bash
# View recent logs
tail -f logs/trade_engine_2025-10-29.log

# Search for specific symbol
cat logs/trade_engine_*.log | jq 'select(.symbol == "BTC/USDT")'

# Count errors by type
cat logs/trade_engine_*.log | jq -r 'select(.level == "error") | .error' | sort | uniq -c
```

### `logs/trades_*.log`

Trading events only (INFO+). For compliance and trade analysis.

```bash
# All trades for a symbol
cat logs/trades_*.log | jq 'select(.symbol == "BTC/USDT")'

# Calculate realized PnL
cat logs/trades_*.log | jq 'select(.event == "position_closed") | .pnl' | paste -sd+ | bc

# Order fill rate
orders_placed=$(cat logs/trades_*.log | jq 'select(.event == "order_placed")' | wc -l)
orders_filled=$(cat logs/trades_*.log | jq 'select(.event == "order_filled")' | wc -l)
echo "Fill rate: $(echo "scale=2; $orders_filled / $orders_placed * 100" | bc)%"
```

### `logs/errors_*.log`

Errors and warnings only (WARNING+). Monitor for issues.

```bash
# Recent errors
tail -f logs/errors_*.log

# Group errors by type
cat logs/errors_*.log | jq -r '.error' | sort | uniq -c | sort -rn

# Critical events (kill switch, risk breaches)
cat logs/errors_*.log | jq 'select(.level == "critical")'
```

## Best Practices

### 1. Always Use Structured Fields

❌ **Bad**: String interpolation

```python
logger.info(f"Order placed: {symbol} {side} {size}")
```

✅ **Good**: Structured fields

```python
logger.info("order_placed", symbol=symbol, side=side, size=size)
```

### 2. Use Decimal for All Financial Values

❌ **Bad**: Float

```python
logger.info("pnl_update", pnl=90.5)  # Loses precision!
```

✅ **Good**: Decimal (automatically converted to string)

```python
logger.info("pnl_update", pnl=Decimal("90.50"))
```

### 3. Include Relevant Context

Always include:
- `symbol` for market data/orders
- `order_id` for orders
- `position_id` for positions
- `strategy_id` for strategies

```python
logger.info(
    "order_filled",
    symbol="BTC/USDT",
    order_id="order_123",
    strategy_id="l2_imbalance_v1",
    fill_price=Decimal("45000.00")
)
```

### 4. Choose Appropriate Log Levels

- **DEBUG**: Detailed flow, calculations, internal state
- **INFO**: Normal operations, trades, signals
- **WARNING**: Issues that don't stop execution (rate limits, retries)
- **ERROR**: Failures (order rejection, API errors)
- **CRITICAL**: System failures (kill switch, database down)

### 5. Log Before and After Critical Operations

```python
logger.info("Placing order", symbol=symbol, side=side, size=size)
try:
    result = broker.place_order(symbol, side, size)
    logger.info("Order placed", order_id=result.order_id)
except Exception as e:
    logger.error("Order failed", error=str(e))
    raise
```

## Analysis Examples

### Calculate Daily PnL

```bash
cat logs/trades_*.log | \
  jq -r 'select(.event == "position_closed") |
    [.timestamp[:10], .pnl] | @tsv' | \
  awk '{sum[$1] += $2} END {for (d in sum) print d, sum[d]}' | \
  sort
```

### Find Slippage Issues

```bash
cat logs/trades_*.log | \
  jq 'select(.event == "order_filled" and .order_type == "MARKET") |
    {symbol, expected: .price, actual: .fill_price,
     slippage: (((.fill_price | tonumber) / (.price | tonumber) - 1) * 100)}'
```

### Monitor Fill Times

```bash
# Correlate order_placed and order_filled by order_id
cat logs/trades_*.log | \
  jq -s 'group_by(.order_id) |
    map(select(length == 2) |
      {order_id: .[0].order_id,
       duration: (.[1].timestamp - .[0].timestamp)})'
```

## Alerts (Phase 3+)

Configure alerts for critical events:

```yaml
alerts:
  - name: "Kill Switch Triggered"
    condition: level == "critical" AND event == "kill_switch_triggered"
    channel: slack
    priority: high

  - name: "Daily Loss Approaching Limit"
    condition: event == "pnl_update" AND total_pnl < -400
    channel: telegram
    priority: medium

  - name: "Order Rejection Rate High"
    condition: count(event == "order_rejected") / count(event == "order_placed") > 0.1
    window: 1h
    channel: slack
    priority: medium
```

## Compliance

### Audit Trail Requirements

The `logs/trades_*.log` file provides an immutable audit trail:

1. **Retention**: 90 days (configurable)
2. **Compression**: Old logs compressed to save space
3. **Integrity**: Logs are append-only (do not modify)
4. **Backup**: Recommended to copy to S3/cold storage monthly

### Regulatory Reports

Generate compliance reports:

```bash
# All trades in date range
cat logs/trades_2025-10-*.log | \
  jq 'select(.event | contains("order") or contains("position"))' \
  > compliance_report_oct_2025.json

# Trade blotter (chronological)
cat logs/trades_*.log | \
  jq -r 'select(.event == "order_filled") |
    [.timestamp, .symbol, .side, .size, .fill_price, .commission] | @csv' \
  > trade_blotter.csv
```

## Troubleshooting

### Logs Not Appearing

1. Check log level: `export TRADE_ENGINE_LOG_LEVEL=DEBUG`
2. Verify log directory exists: `mkdir -p logs`
3. Check permissions: `ls -la logs/`

### JSON Parse Errors

If logs contain invalid JSON, it's likely a crash mid-write. Check:

```bash
# Find incomplete JSON
cat logs/trade_engine_*.log | jq . 2>&1 | grep "parse error"

# View last complete entry
tac logs/trade_engine_2025-10-29.log | grep -m1 "^{" | jq .
```

### High Disk Usage

```bash
# Check log sizes
du -sh logs/

# Clean old logs (keeps 90 days by default)
find logs/ -name "*.log.zip" -mtime +90 -delete

# Compress current logs manually
gzip logs/trade_engine_2025-09-*.log
```

## Performance

Structured logging adds minimal overhead:

- **File I/O**: ~0.1ms per log entry (buffered)
- **JSON serialization**: ~0.01ms per entry
- **Total**: < 0.2ms per log (negligible vs. trading latency)

Tips:
- Use `DEBUG` level only in development
- Avoid logging in tight loops (> 1000 Hz)
- Use sampling for high-frequency data (log every Nth tick)

## Future Enhancements

### Phase 3: Centralized Logging

```python
# Push logs to Postgres
from trade_engine.core.logging_config import configure_postgres_sink

configure_postgres_sink(
    connection_string="postgresql://localhost/trading_logs",
    table="logs",
    batch_size=100
)
```

### Phase 4: Event Sourcing

```python
# Event-sourced trade ledger
from trade_engine.core.event_store import TradeEventStore

event_store = TradeEventStore(kafka_brokers=["localhost:9092"])
event_store.log_order_placed(...)  # Immutable, replayable
```

## Support

For issues or questions:
- Check this guide first
- Review logs with `jq` for structured queries
- Consult CLAUDE.md for project guidelines
