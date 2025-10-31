"""
Broker Connectivity Test Suite

Tests connectivity and authentication with real broker APIs:
- Binance.us Spot (production only, no testnet)
- Kraken Futures (demo environment available)

SAFETY FEATURES:
- Read-only operations only (balance checks, account info)
- NO order placement unless explicitly enabled
- Clear warnings before any API calls
- Graceful handling of missing credentials

Usage:
    # Test with available credentials (read-only, safe)
    python examples/test_brokers_connectivity.py

    # Test specific broker
    python examples/test_brokers_connectivity.py --broker binance
    python examples/test_brokers_connectivity.py --broker kraken

    # Test with order placement (DANGEROUS - use demo only!)
    python examples/test_brokers_connectivity.py --broker kraken --enable-orders
"""

import sys
import os
import argparse
from decimal import Decimal
from loguru import logger

sys.path.insert(0, 'src')

from trade_engine.adapters.brokers.binance_us import BinanceUSSpotBroker, BinanceUSError
from trade_engine.adapters.brokers.kraken import KrakenFuturesBroker, KrakenError


class BrokerTestResult:
    """Test result for a broker."""
    def __init__(self, broker_name: str):
        self.broker_name = broker_name
        self.credentials_found = False
        self.connection_successful = False
        self.authentication_successful = False
        self.balance_retrieved = False
        self.error_message = None
        self.balance = None

    def __str__(self):
        status = "✅ PASS" if self.connection_successful else "❌ FAIL"
        return f"{self.broker_name}: {status}"


def test_binance_us(enable_orders: bool = False) -> BrokerTestResult:
    """
    Test Binance.us spot broker connectivity.

    Args:
        enable_orders: If True, test order placement (DANGEROUS!)

    Returns:
        BrokerTestResult with test outcomes
    """
    result = BrokerTestResult("Binance.us Spot")

    print("\n" + "=" * 80)
    print("🧪 Testing Binance.us Spot Broker")
    print("=" * 80)

    # Check for credentials
    api_key = os.getenv("BINANCE_US_API_KEY")
    api_secret = os.getenv("BINANCE_US_API_SECRET")

    if not api_key or not api_secret:
        logger.warning("❌ Binance.us credentials not found")
        logger.info("   Set BINANCE_US_API_KEY and BINANCE_US_API_SECRET to test")
        result.error_message = "Credentials not found"
        return result

    result.credentials_found = True
    logger.info("✅ Credentials found")

    # Initialize broker
    try:
        logger.info("Initializing broker...")
        broker = BinanceUSSpotBroker()
        result.connection_successful = True
        logger.info("✅ Broker initialized successfully")
    except BinanceUSError as e:
        logger.error(f"❌ Failed to initialize broker: {e}")
        result.error_message = str(e)
        return result
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        result.error_message = str(e)
        return result

    # Test authentication by getting account info
    try:
        logger.info("Testing authentication (fetching account info)...")
        # Use internal _request method to test auth
        account_info = broker._request(
            "GET",
            "/api/v3/account",
            params={},
            signed=True
        )
        result.authentication_successful = True
        logger.info("✅ Authentication successful")

        # Get balance
        if "balances" in account_info:
            usdt_balance = None
            for balance in account_info["balances"]:
                if balance["asset"] == "USDT":
                    free = Decimal(balance["free"])
                    locked = Decimal(balance["locked"])
                    usdt_balance = free + locked
                    break

            if usdt_balance is not None:
                result.balance_retrieved = True
                result.balance = usdt_balance
                logger.info(f"✅ Balance retrieved: ${usdt_balance} USDT")
            else:
                logger.warning("⚠️  USDT balance not found in account")

    except BinanceUSError as e:
        logger.error(f"❌ Authentication failed: {e}")
        result.error_message = str(e)
        return result
    except Exception as e:
        logger.error(f"❌ Unexpected error during authentication: {e}")
        result.error_message = str(e)
        return result

    # Test with breakout detector (simulated data, no real orders)
    if not enable_orders:
        logger.info("\n📊 Testing breakout detector integration (no orders)...")
        try:
            from trade_engine.domain.strategies.alpha_breakout_detector import (
                BreakoutSetupDetector,
                BreakoutConfig
            )
            from trade_engine.core.types import Bar

            # Initialize strategy
            config = BreakoutConfig(
                volume_spike_threshold=Decimal("2.0"),
                sr_lookback_bars=25,
                position_size_usd=Decimal("100")  # Small position for testing
            )
            strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

            # Process a few bars (not enough to generate signals)
            for i in range(10):
                bar = Bar(
                    timestamp=1000 + i,
                    open=Decimal("50000"),
                    high=Decimal("50100"),
                    low=Decimal("49900"),
                    close=Decimal("50000"),
                    volume=Decimal("100")
                )
                signals = strategy.on_bar(bar)

            logger.info("✅ Breakout detector integration successful")
            logger.info(f"   Strategy processed 10 bars (no signals expected)")

        except Exception as e:
            logger.error(f"❌ Breakout detector integration failed: {e}")
    else:
        logger.warning("⚠️  Order placement testing not recommended for Binance.us (no testnet)")
        logger.warning("   Skipping order tests to prevent real trades")

    # Summary
    print("\n📊 Binance.us Test Summary:")
    print(f"   Credentials: {'✅' if result.credentials_found else '❌'}")
    print(f"   Connection: {'✅' if result.connection_successful else '❌'}")
    print(f"   Authentication: {'✅' if result.authentication_successful else '❌'}")
    print(f"   Balance: {'✅' if result.balance_retrieved else '❌'}")
    if result.balance is not None:
        print(f"   USDT Balance: ${result.balance}")

    return result


def test_kraken_futures(enable_orders: bool = False) -> BrokerTestResult:
    """
    Test Kraken Futures broker connectivity (DEMO environment).

    Args:
        enable_orders: If True, test order placement in demo

    Returns:
        BrokerTestResult with test outcomes
    """
    result = BrokerTestResult("Kraken Futures (Demo)")

    print("\n" + "=" * 80)
    print("🧪 Testing Kraken Futures Broker (DEMO)")
    print("=" * 80)

    # Check for demo credentials
    api_key = os.getenv("KRAKEN_DEMO_API_KEY")
    api_secret = os.getenv("KRAKEN_DEMO_API_SECRET")

    if not api_key or not api_secret:
        logger.warning("❌ Kraken demo credentials not found")
        logger.info("   Set KRAKEN_DEMO_API_KEY and KRAKEN_DEMO_API_SECRET to test")
        logger.info("   Get demo credentials at: https://demo-futures.kraken.com/")
        result.error_message = "Credentials not found"
        return result

    result.credentials_found = True
    logger.info("✅ Credentials found")

    # Initialize broker (demo mode)
    try:
        logger.info("Initializing broker (DEMO environment)...")
        broker = KrakenFuturesBroker(demo=True)
        result.connection_successful = True
        logger.info("✅ Broker initialized successfully")
    except KrakenError as e:
        logger.error(f"❌ Failed to initialize broker: {e}")
        result.error_message = str(e)
        return result
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        result.error_message = str(e)
        return result

    # Test authentication by getting account info
    try:
        logger.info("Testing authentication (fetching account info)...")
        # Use internal _request method to test auth
        account_info = broker._request("GET", "/accounts")
        result.authentication_successful = True
        logger.info("✅ Authentication successful")

        # Get balance (demo account)
        if "accounts" in account_info and account_info["accounts"]:
            # Kraken returns marginBalance in the account
            for account in account_info["accounts"]:
                if "marginBalance" in account:
                    balance = Decimal(str(account["marginBalance"]))
                    result.balance_retrieved = True
                    result.balance = balance
                    logger.info(f"✅ Balance retrieved: ${balance} (demo)")
                    break

    except KrakenError as e:
        logger.error(f"❌ Authentication failed: {e}")
        result.error_message = str(e)
        return result
    except Exception as e:
        logger.error(f"❌ Unexpected error during authentication: {e}")
        result.error_message = str(e)
        return result

    # Test with breakout detector
    logger.info("\n📊 Testing breakout detector integration...")
    try:
        from trade_engine.domain.strategies.alpha_breakout_detector import (
            BreakoutSetupDetector,
            BreakoutConfig
        )
        from trade_engine.core.types import Bar

        # Initialize strategy
        config = BreakoutConfig(
            volume_spike_threshold=Decimal("2.0"),
            sr_lookback_bars=25,
            position_size_usd=Decimal("100")  # Small position for testing
        )
        strategy = BreakoutSetupDetector(symbol="PF_XBTUSD", config=config)

        # Process bars
        for i in range(10):
            bar = Bar(
                timestamp=1000 + i,
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50000"),
                volume=Decimal("100")
            )
            signals = strategy.on_bar(bar)

        logger.info("✅ Breakout detector integration successful")
        logger.info(f"   Strategy processed 10 bars (no signals expected)")

        # Test order placement if enabled (DEMO only - safe)
        if enable_orders:
            logger.info("\n📤 Testing order placement (DEMO - safe)...")
            logger.warning("⚠️  This will place a real order in the DEMO environment")
            logger.info("   (No real money at risk)")

            try:
                # Small test order
                order_id = broker.buy(
                    symbol="PF_XBTUSD",
                    qty=Decimal("1"),  # 1 contract
                    sl=None,
                    tp=None
                )
                logger.info(f"✅ Order placed successfully: {order_id}")
                logger.info("   (This was a demo order - no real money)")

            except KrakenError as e:
                logger.warning(f"⚠️  Order placement failed (may be expected): {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error during order placement: {e}")

    except Exception as e:
        logger.error(f"❌ Breakout detector integration failed: {e}")

    # Summary
    print("\n📊 Kraken Futures Test Summary:")
    print(f"   Credentials: {'✅' if result.credentials_found else '❌'}")
    print(f"   Connection: {'✅' if result.connection_successful else '❌'}")
    print(f"   Authentication: {'✅' if result.authentication_successful else '❌'}")
    print(f"   Balance: {'✅' if result.balance_retrieved else '❌'}")
    if result.balance is not None:
        print(f"   Demo Balance: ${result.balance}")

    return result


def main():
    """Run broker connectivity tests."""
    parser = argparse.ArgumentParser(
        description="Test broker connectivity and integration with breakout detector"
    )
    parser.add_argument(
        "--broker",
        choices=["binance", "kraken", "all"],
        default="all",
        help="Which broker to test"
    )
    parser.add_argument(
        "--enable-orders",
        action="store_true",
        help="Enable order placement testing (KRAKEN DEMO ONLY)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🔌 Broker Connectivity & Integration Test Suite")
    print("=" * 80)
    print("\n📋 Test Plan:")
    print("   1. Check for API credentials")
    print("   2. Initialize broker connection")
    print("   3. Test authentication")
    print("   4. Retrieve account balance")
    print("   5. Test breakout detector integration")
    if args.enable_orders:
        print("   6. Test order placement (DEMO ONLY)")
    print("\n⚠️  Safety: Read-only operations unless --enable-orders specified")
    print("=" * 80)

    results = []

    # Test Binance.us
    if args.broker in ["binance", "all"]:
        result = test_binance_us(enable_orders=False)  # Never enable orders for Binance.us
        results.append(result)

    # Test Kraken
    if args.broker in ["kraken", "all"]:
        result = test_kraken_futures(enable_orders=args.enable_orders)
        results.append(result)

    # Final summary
    print("\n" + "=" * 80)
    print("📊 Final Test Summary")
    print("=" * 80)

    for result in results:
        print(f"\n{result.broker_name}:")
        if result.error_message:
            print(f"   Status: ❌ FAILED")
            print(f"   Error: {result.error_message}")
        elif result.authentication_successful:
            print(f"   Status: ✅ PASSED")
            print(f"   Connection: ✅")
            print(f"   Authentication: ✅")
            if result.balance_retrieved:
                print(f"   Balance: ${result.balance}")
        else:
            print(f"   Status: ⚠️  PARTIAL")
            print(f"   Some tests failed")

    # Exit code
    all_passed = all(r.authentication_successful for r in results if r.credentials_found)
    any_credentials = any(r.credentials_found for r in results)

    print("\n" + "=" * 80)
    if all_passed and any_credentials:
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nBrokers are ready for use with breakout detector strategy!")
        sys.exit(0)
    elif any_credentials:
        print("⚠️  SOME TESTS PASSED")
        print("=" * 80)
        print("\nSome brokers are ready, others need credentials")
        sys.exit(0)
    else:
        print("❌ NO CREDENTIALS FOUND")
        print("=" * 80)
        print("\nSet environment variables to test broker connectivity:")
        print("\nBinance.us:")
        print("  export BINANCE_US_API_KEY='your_key'")
        print("  export BINANCE_US_API_SECRET='your_secret'")
        print("\nKraken Futures Demo:")
        print("  export KRAKEN_DEMO_API_KEY='your_demo_key'")
        print("  export KRAKEN_DEMO_API_SECRET='your_demo_secret'")
        print("  Get demo credentials: https://demo-futures.kraken.com/")
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )

    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Tests failed with error: {e}")
        sys.exit(1)
