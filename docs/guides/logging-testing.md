# Testing the Logging Initialization

This document explains how to test the structured logging system after PR #21.

## Prerequisites

Activate the virtual environment with dependencies installed:

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Or install dependencies if not done
pip install -r requirements.txt
```

## Quick Test

Run the logging test script (no heavy dependencies):

```bash
python scripts/test_logging_init.py
```

**Expected output**:
```
================================================================================
Testing Structured Logging Initialization
================================================================================

1. Initializing logging...
   ✓ Logging configured

2. Getting logger...
   ✓ Logger obtained

3. Testing basic logging...
   ✓ Basic logging works

4. Testing TradingLogger...
   ✓ TradingLogger works

5. Checking log files...
   ✓ Found 3 log file(s):
     - trade_engine_YYYY-MM-DD_HH-MM-SS.log (XXX bytes)
     - trades_YYYY-MM-DD_HH-MM-SS.log (XXX bytes)
     - errors_YYYY-MM-DD_HH-MM-SS.log (XXX bytes)

================================================================================
All tests passed! Logging initialization is working correctly.
================================================================================

Log files created in: logs/
- trade_engine_*.log  (all logs)
- trades_*.log        (trading events only)
- errors_*.log        (warnings and errors)
```

## Test Updated Demo Scripts

### Multi-Factor Screener
```bash
python scripts/demo_multi_factor_screener.py
```

Should initialize logging and run the screener demo.

### Full System Demo (Quick Mode)
```bash
python scripts/dev/demo_full_system_simple.py --quick
```

Should initialize logging and run simulation.

### L2 Integration Demo (Dry Run)
```bash
python scripts/dev/demo_l2_integration.py --symbol BTCUSDT --duration 10 --dry-run
```

Should initialize logging, create log files in `logs/`, and run L2 demo.

## Verify Log Files

After running any demo with file logging enabled, check:

```bash
# List log files
ls -lh logs/

# View all logs
tail -f logs/trade_engine_*.log

# View trading events only
tail -f logs/trades_*.log

# View errors/warnings
tail -f logs/errors_*.log
```

## Test Log Analysis (JSON Mode)

Run a demo with JSON logging enabled:

```bash
# Set environment variable
export TRADE_ENGINE_LOG_JSON=true

# Run demo
python scripts/test_logging_init.py

# Analyze logs with jq
cat logs/trade_engine_*.log | jq '.record.extra'
cat logs/trades_*.log | jq 'select(.record.extra.event == "order_placed")'
```

## Unit Tests

Run the logging unit tests:

```bash
# All logging tests
pytest tests/unit/core/test_logging_config.py -v

# Specific test
pytest tests/unit/core/test_logging_config.py::TestLoggingConfiguration::test_configure_logging_creates_log_dir -v
```

**Expected**: 21 tests pass

## Troubleshooting

### "ModuleNotFoundError: No module named 'loguru'"
**Solution**: Activate virtual environment and install dependencies:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "PermissionError: Failed to create log directory"
**Solution**: Check write permissions on project directory:
```bash
ls -ld logs/
chmod u+w logs/  # If needed
```

### "No log files created"
**Cause**: Script may have `enable_file=False`

**Solution**: Check the `configure_logging()` call in the script:
```python
configure_logging(
    level="INFO",
    enable_console=True,
    enable_file=True,  # Must be True for file logging
    serialize=False
)
```

### Logs directory not found
**Solution**: The `logs/` directory is created automatically by `configure_logging()` when `enable_file=True`.

If it's not being created, the initialization may not have been called. Check that:
1. `configure_logging()` is called in `main()`
2. `main()` is actually being executed
3. No exceptions occurred during initialization

## Clean Up

Remove test log files:

```bash
rm -rf logs/
```

The directory will be recreated automatically on next run with file logging enabled.
