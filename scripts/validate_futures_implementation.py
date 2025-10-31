#!/usr/bin/env python3
"""
Validate Perpetual Futures Implementation.

Tests all components without requiring live API connections or database.
This is a smoke test to ensure all imports work and basic logic is sound.
"""

import sys
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that all new modules can be imported."""
    print("=" * 60)
    print("TEST 1: Module Imports")
    print("=" * 60)

    try:
        from trade_engine.services.data.funding_rate_service import FundingRateService
        print("✓ FundingRateService imported successfully")
    except Exception as e:
        print(f"✗ Failed to import FundingRateService: {e}")
        return False

    try:
        from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
        print("✓ FuturesRiskManager imported successfully")
    except Exception as e:
        print(f"✗ Failed to import FuturesRiskManager: {e}")
        return False

    try:
        from trade_engine.services.trading.position_manager import PositionManager
        print("✓ PositionManager imported successfully")
    except Exception as e:
        print(f"✗ Failed to import PositionManager: {e}")
        return False

    print()
    return True


def test_funding_rate_service():
    """Test FundingRateService basic functionality."""
    print("=" * 60)
    print("TEST 2: Funding Rate Service")
    print("=" * 60)

    from trade_engine.services.data.funding_rate_service import FundingRateService

    service = FundingRateService()

    # Test funding cost calculation
    cost = service.calculate_funding_cost(
        position_size=Decimal("0.5"),
        entry_price=Decimal("50000"),
        funding_rate=Decimal("0.0001"),
        periods=1
    )

    expected = Decimal("2.50")
    if cost == expected:
        print(f"✓ Funding cost calculation: {cost} (expected {expected})")
    else:
        print(f"✗ Funding cost calculation: {cost} (expected {expected})")
        return False

    # Test multi-period calculation
    daily_cost = service.calculate_funding_cost(
        position_size=Decimal("1.0"),
        entry_price=Decimal("50000"),
        funding_rate=Decimal("0.0001"),
        periods=3  # 24 hours
    )

    expected_daily = Decimal("15.00")
    if daily_cost == expected_daily:
        print(f"✓ Daily funding cost: {daily_cost} (expected {expected_daily})")
    else:
        print(f"✗ Daily funding cost: {daily_cost} (expected {expected_daily})")
        return False

    print()
    return True


def test_futures_risk_manager():
    """Test FuturesRiskManager basic functionality."""
    print("=" * 60)
    print("TEST 3: Futures Risk Manager")
    print("=" * 60)

    from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager

    config = {
        "risk": {
            "max_daily_loss_usd": 500,
            "max_trades_per_day": 50,
            "max_position_usd": 10000,
        }
    }

    risk = FuturesRiskManager(config=config, max_leverage=5)

    # Test leverage validation
    result = risk.validate_leverage(3)
    if result.passed:
        print("✓ Leverage validation: 3x accepted")
    else:
        print(f"✗ Leverage validation failed: {result.reason}")
        return False

    result = risk.validate_leverage(10)
    if not result.passed:
        print("✓ Leverage validation: 10x rejected (exceeds 5x max)")
    else:
        print("✗ Leverage validation: 10x should be rejected")
        return False

    # Test liquidation price calculation
    liq_price = risk.calculate_liquidation_price(
        entry_price=Decimal("50000"),
        leverage=5,
        side="long"
    )

    expected_liq = Decimal("40200.00")
    if liq_price == expected_liq:
        print(f"✓ Liquidation price (long, 5x): ${liq_price} (expected ${expected_liq})")
    else:
        print(f"✗ Liquidation price: ${liq_price} (expected ${expected_liq})")
        return False

    # Test margin health check
    margin_check = risk.check_margin_health(
        account_balance=Decimal("10000"),
        maintenance_margin=Decimal("5000"),
        unrealized_pnl=Decimal("0")
    )

    if margin_check["action"] == "ok":
        print(f"✓ Margin health: {margin_check['action']} (ratio: {margin_check['margin_ratio']})")
    else:
        print(f"✗ Margin health check failed: {margin_check}")
        return False

    # Test position validation
    validation = risk.validate_position_with_leverage(
        balance=Decimal("1000"),
        price=Decimal("50000"),
        size=Decimal("0.1"),
        leverage=5
    )

    if validation.passed:
        print("✓ Position validation: 0.1 BTC @ 5x leverage accepted")
    else:
        print(f"✗ Position validation failed: {validation.reason}")
        return False

    print()
    return True


def test_position_manager_instantiation():
    """Test PositionManager can be instantiated."""
    print("=" * 60)
    print("TEST 4: Position Manager Instantiation")
    print("=" * 60)

    from trade_engine.services.trading.position_manager import PositionManager

    # We can't fully test PositionManager without broker/database
    # But we can verify the class loads and has expected methods

    expected_methods = [
        'open_position',
        'close_position',
        'monitor_positions',
        '_emergency_close_all',
        '_reduce_largest_position'
    ]

    for method in expected_methods:
        if hasattr(PositionManager, method):
            print(f"✓ PositionManager.{method} exists")
        else:
            print(f"✗ PositionManager.{method} not found")
            return False

    print()
    return True


def test_database_methods():
    """Test that database methods are available."""
    print("=" * 60)
    print("TEST 5: Database Methods")
    print("=" * 60)

    from trade_engine.db.postgres_adapter import PostgresDatabase

    expected_methods = [
        'log_funding_event',
        'log_pnl_snapshot',
        'get_funding_history',
        'get_equity_curve'
    ]

    for method in expected_methods:
        if hasattr(PostgresDatabase, method):
            print(f"✓ PostgresDatabase.{method} exists")
        else:
            print(f"✗ PostgresDatabase.{method} not found")
            return False

    print()
    return True


def test_decimal_precision():
    """Test that Decimal precision is maintained."""
    print("=" * 60)
    print("TEST 6: Decimal Precision (NON-NEGOTIABLE)")
    print("=" * 60)

    from trade_engine.services.data.funding_rate_service import FundingRateService
    from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager

    service = FundingRateService()

    # Test that results are Decimal, not float
    result = service.calculate_funding_cost(
        position_size=Decimal("0.123"),
        entry_price=Decimal("45678.90"),
        funding_rate=Decimal("0.000123"),
        periods=1
    )

    if isinstance(result, Decimal):
        print(f"✓ Funding cost returns Decimal: {type(result).__name__}")
    else:
        print(f"✗ Funding cost returns {type(result).__name__} (should be Decimal)")
        return False

    # Test quantization (2 decimal places for USD)
    if len(str(result).split('.')[-1]) == 2:
        print(f"✓ Result quantized to 2 decimals: {result}")
    else:
        print(f"✗ Result not quantized: {result}")
        return False

    # Test liquidation price
    config = {"risk": {"max_daily_loss_usd": 500, "max_trades_per_day": 50, "max_position_usd": 10000}}
    risk = FuturesRiskManager(config=config, max_leverage=5)

    liq_price = risk.calculate_liquidation_price(
        entry_price=Decimal("12345.6789"),
        leverage=3,
        side="long"
    )

    if isinstance(liq_price, Decimal):
        print(f"✓ Liquidation price returns Decimal: {type(liq_price).__name__}")
    else:
        print(f"✗ Liquidation price returns {type(liq_price).__name__} (should be Decimal)")
        return False

    print()
    return True


def test_safety_limits():
    """Test that safety limits are enforced."""
    print("=" * 60)
    print("TEST 7: Safety Limits (NON-NEGOTIABLE)")
    print("=" * 60)

    from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager

    config = {
        "risk": {
            "max_daily_loss_usd": 500,
            "max_trades_per_day": 50,
            "max_position_usd": 10000,
        }
    }

    risk = FuturesRiskManager(config=config, max_leverage=5)

    # Test position exceeds hard limit
    result = risk.validate_position_with_leverage(
        balance=Decimal("20000"),
        price=Decimal("50000"),
        size=Decimal("1.0"),  # $50k notional, exceeds $10k limit
        leverage=5
    )

    if not result.passed and "NON-NEGOTIABLE" in result.reason:
        print("✓ Hard position limit enforced: $10,000 max")
    else:
        print(f"✗ Hard limit not enforced: {result}")
        return False

    # Test daily loss limit
    check = risk.can_open_position(
        balance=Decimal("1000"),
        price=Decimal("50000"),
        size=Decimal("0.01"),
        leverage=3,
        current_pnl=Decimal("-600")  # Exceeds -$500 limit
    )

    if not check["allowed"] and "Daily loss" in check["reason"]:
        print("✓ Daily loss limit enforced: -$500 max")
    else:
        print(f"✗ Daily loss limit not enforced: {check}")
        return False

    # Test kill switch
    risk.trigger_kill_switch("Test")

    check = risk.can_open_position(
        balance=Decimal("10000"),
        price=Decimal("50000"),
        size=Decimal("0.01"),
        leverage=3
    )

    if not check["allowed"] and "Kill switch" in check["reason"]:
        print("✓ Kill switch enforced when active")
    else:
        print(f"✗ Kill switch not enforced: {check}")
        return False

    print()
    return True


def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("PERPETUAL FUTURES IMPLEMENTATION VALIDATION")
    print("=" * 60 + "\n")

    tests = [
        ("Module Imports", test_imports),
        ("Funding Rate Service", test_funding_rate_service),
        ("Futures Risk Manager", test_futures_risk_manager),
        ("Position Manager", test_position_manager_instantiation),
        ("Database Methods", test_database_methods),
        ("Decimal Precision", test_decimal_precision),
        ("Safety Limits", test_safety_limits),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"✗ {name} failed with exception: {e}")
            results.append((name, False))

    # Print summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:10} | {name}")

    print("-" * 60)
    print(f"Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All validation tests passed!")
        print("✅ Implementation is working correctly")
        print("\nNext steps:")
        print("1. Review PR #31")
        print("2. Run on Binance testnet with real API keys")
        print("3. 24-hour stability test")
        return 0
    else:
        print("\n⚠️  Some validation tests failed")
        print("Please review the errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
