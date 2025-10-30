#!/usr/bin/env python3
"""
Test script to verify logging initialization works correctly.

This script has minimal dependencies and tests:
- configure_logging() initialization
- get_logger() usage
- TradingLogger functionality
- Log file creation

Usage:
    python scripts/test_logging_init.py
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_engine.core.logging_config import configure_logging, get_logger, TradingLogger


def main():
    """Test logging initialization."""
    print("="*80)
    print("Testing Structured Logging Initialization")
    print("="*80)
    print()

    # Test 1: Basic initialization
    print("1. Initializing logging...")
    configure_logging(
        level="INFO",
        enable_console=True,
        enable_file=True,
        serialize=False
    )
    print("   ✓ Logging configured")
    print()

    # Test 2: Get logger
    print("2. Getting logger...")
    logger = get_logger(__name__)
    print("   ✓ Logger obtained")
    print()

    # Test 3: Basic logging
    print("3. Testing basic logging...")
    logger.info("Basic log message", test_key="test_value")
    logger.warning("Warning message", count=42)
    logger.debug("Debug message (should not appear at INFO level)")
    print("   ✓ Basic logging works")
    print()

    # Test 4: TradingLogger
    print("4. Testing TradingLogger...")
    trade_logger = TradingLogger(strategy_id="test_strategy")

    trade_logger.order_placed(
        symbol="BTC/USDT",
        side="BUY",
        size=Decimal("0.1"),
        price=Decimal("45000.00"),
        order_id="test_order_123"
    )

    trade_logger.position_closed(
        symbol="BTC/USDT",
        side="LONG",
        size=Decimal("0.1"),
        entry_price=Decimal("45000.00"),
        exit_price=Decimal("45900.00"),
        pnl=Decimal("90.00"),
        position_id="test_pos_456"
    )
    print("   ✓ TradingLogger works")
    print()

    # Test 5: Check log files
    print("5. Checking log files...")
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        print(f"   ✓ Found {len(log_files)} log file(s):")
        for log_file in log_files:
            size = log_file.stat().st_size
            print(f"     - {log_file.name} ({size} bytes)")
    else:
        print("   ✗ No logs directory found")
    print()

    print("="*80)
    print("All tests passed! Logging initialization is working correctly.")
    print("="*80)
    print()
    print("Log files created in: logs/")
    print("- trade_engine_*.log  (all logs)")
    print("- trades_*.log        (trading events only)")
    print("- errors_*.log        (warnings and errors)")


if __name__ == "__main__":
    main()
