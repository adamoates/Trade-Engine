# Logging Initialization Guide

Quick reference for adding logging initialization to scripts and applications.

## Overview

The Trade Engine uses a structured logging system that must be explicitly initialized at application startup. This prevents module-level side effects and gives you full control over logging configuration.

## Pattern: Application Entry Points

Every script with `if __name__ == "__main__":` should initialize logging.

### Basic Pattern (No File Logging)

For simple demos and tools that don't need persistent logs:

```python
#!/usr/bin/env python3
from trade_engine.core.logging_config import configure_logging, get_logger


def main():
    # Initialize logging (first thing in main)
    configure_logging(
        level="INFO",
        enable_console=True,
        enable_file=False,  # No log files for simple demos
        serialize=False  # Human-readable output
    )

    logger = get_logger(__name__)
    logger.info("Application started")

    # ... rest of application logic


if __name__ == "__main__":
    main()
```

### Advanced Pattern (With File Logging)

For trading systems and long-running applications:

```python
#!/usr/bin/env python3
import os
from pathlib import Path
from trade_engine.core.logging_config import configure_logging, get_logger


def main():
    # Initialize logging with environment-based configuration
    configure_logging(
        level=os.getenv("TRADE_ENGINE_LOG_LEVEL", "INFO"),
        enable_console=True,
        enable_file=True,  # Create log files in logs/
        log_dir=Path("logs"),
        serialize=os.getenv("TRADE_ENGINE_LOG_JSON", "false").lower() == "true",
        rotation="1 day",
        retention="90 days"
    )

    logger = get_logger(__name__)
    logger.info("Trading system started")

    # ... rest of application logic


if __name__ == "__main__":
    main()
```

### Pattern: Classes and Modules

For classes and modules that will use the logger:

```python
from trade_engine.core.logging_config import get_logger

# Module-level logger (but don't configure here!)
logger = get_logger(__name__)


class MyTradingStrategy:
    def __init__(self):
        # Logger is already configured by main()
        logger.info("Strategy initialized")

    def execute(self):
        logger.info("Executing trade", symbol="BTC/USDT", size=0.1)
```

**Important**: Modules should call `get_logger()` but **never** call `configure_logging()`. Only the application entry point (`main()`) should configure logging.

## Pattern: Trading Event Logging

For standardized trading events (orders, positions, PnL):

```python
from decimal import Decimal
from trade_engine.core.logging_config import TradingLogger

# In your trading class
class MyTrader:
    def __init__(self):
        self.trade_logger = TradingLogger(strategy_id="my_strategy_v1")

    def place_order(self, symbol, side, size, price):
        # ... order placement logic ...

        self.trade_logger.order_placed(
            symbol=symbol,
            side=side,
            size=Decimal(str(size)),
            price=Decimal(str(price)),
            order_id=order_id
        )
```

## Configuration Options

### Log Levels

- **DEBUG**: Detailed flow, calculations, internal state (development only)
- **INFO**: Normal operations, trades, signals (default for production)
- **WARNING**: Issues that don't stop execution (rate limits, retries)
- **ERROR**: Failures (order rejection, API errors)
- **CRITICAL**: System failures (kill switch, database down)

### Environment Variables

Control logging via environment variables:

```bash
# Set log level
export TRADE_ENGINE_LOG_LEVEL=DEBUG

# Enable JSON format
export TRADE_ENGINE_LOG_JSON=true

# Set log directory
export TRADE_ENGINE_LOG_DIR=/var/log/trade-engine
```

Then in your code:

```python
import os
configure_logging(
    level=os.getenv("TRADE_ENGINE_LOG_LEVEL", "INFO"),
    serialize=os.getenv("TRADE_ENGINE_LOG_JSON", "false").lower() == "true",
    log_dir=Path(os.getenv("TRADE_ENGINE_LOG_DIR", "logs"))
)
```

### File Logging Options

```python
configure_logging(
    enable_file=True,           # Create log files
    log_dir=Path("logs"),       # Directory for logs
    rotation="1 day",           # When to rotate (1 day, 500 MB, etc.)
    retention="90 days",        # How long to keep old logs
    compression="zip",          # Compress old logs
    serialize=True              # JSON format (vs human-readable)
)
```

## Examples by Use Case

### Demo Scripts

Simple demos that don't need persistent logs:

```python
configure_logging(
    level="INFO",
    enable_console=True,
    enable_file=False,
    serialize=False
)
```

### Development/Testing

Verbose logging with files for debugging:

```python
configure_logging(
    level="DEBUG",
    enable_console=True,
    enable_file=True,
    serialize=False,  # Human-readable
    log_dir=Path("logs/dev")
)
```

### Paper Trading

Full logging with structured format for analysis:

```python
configure_logging(
    level="INFO",
    enable_console=True,
    enable_file=True,
    serialize=True,  # JSON for analysis
    rotation="1 day",
    retention="90 days"
)
```

### Live Trading

Production configuration with minimal console output:

```python
configure_logging(
    level="INFO",
    enable_console=True,
    enable_file=True,
    serialize=True,
    rotation="1 day",
    retention="90 days",
    compression="zip"
)
```

### Performance Benchmarks

Minimal logging to avoid skewing results:

```python
import os
os.environ['LOGURU_LEVEL'] = 'ERROR'  # Only errors

configure_logging(
    level="ERROR",
    enable_console=True,
    enable_file=False
)
```

## Migration Checklist

When adding logging to an existing script:

1. ✅ Import: `from trade_engine.core.logging_config import configure_logging, get_logger`
2. ✅ Initialize: Call `configure_logging()` at the start of `main()`
3. ✅ Replace: Change `from loguru import logger` to `logger = get_logger(__name__)`
4. ✅ Test: Run script and verify logs appear correctly
5. ✅ Optional: Convert trading events to use `TradingLogger`

## Common Mistakes

### ❌ Don't configure in modules

```python
# BAD - Don't do this in imported modules!
from trade_engine.core.logging_config import configure_logging

configure_logging(level="DEBUG")  # Will run on import!
```

### ❌ Don't configure multiple times

```python
# BAD - Configure once, not in every function!
def my_function():
    configure_logging(level="INFO")  # Don't do this!
```

### ✅ Do configure in main

```python
# GOOD - Configure once in main
def main():
    configure_logging(level="INFO")
    # ... rest of application

if __name__ == "__main__":
    main()
```

## See Also

- [Logging Guide](./logging-guide.md) - Complete logging documentation
- [CLAUDE.md](../../.claude/CLAUDE.md) - Project standards and rules
