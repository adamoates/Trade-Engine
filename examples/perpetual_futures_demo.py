"""
Demo: Perpetual Futures Trading with Full Risk Management.

Shows complete integration of all components:
- Funding rate tracking
- Futures risk management
- Position lifecycle
- Database logging

IMPORTANT: This runs on Binance testnet by default.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv
from loguru import logger

from trade_engine.adapters.brokers.binance import BinanceFuturesBroker
from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.services.trading.position_manager import PositionManager
from trade_engine.db.postgres_adapter import PostgresDatabase


def main():
    """Run perpetual futures demo."""

    # Load environment variables
    load_dotenv()

    # Initialize components
    logger.info("=== Initializing Perpetual Futures Trading System ===")

    # 1. Database
    db = PostgresDatabase(database_url=os.getenv("DATABASE_URL"))
    logger.info("✓ Database initialized")

    # 2. Broker (testnet mode)
    broker = BinanceFuturesBroker(testnet=True)
    logger.info("✓ Broker initialized (testnet)")

    # 3. Funding service
    funding = FundingRateService(database=db, testnet=True)
    logger.info("✓ Funding rate service initialized (testnet)")

    # 4. Risk manager
    risk_config = {
        "risk": {
            "max_daily_loss_usd": 500,
            "max_trades_per_day": 50,
            "max_position_usd": 10000,
        }
    }

    risk = FuturesRiskManager(
        config=risk_config,
        max_leverage=5,
        liquidation_buffer=Decimal("0.15"),
    )
    logger.info("✓ Risk manager initialized (5x max leverage, 15% buffer)")

    # 5. Position manager
    pm = PositionManager(
        broker=broker,
        risk_manager=risk,
        funding_service=funding,
        database=db,
    )
    logger.info("✓ Position manager initialized")

    logger.info("=== System Ready ===\n")

    # Demo: Open a position
    logger.info("📊 Opening long position on BTCUSDT...")

    result = pm.open_position(
        symbol="BTCUSDT",
        side="long",
        size=Decimal("0.001"),
        leverage=3,
        strategy="demo",
    )

    if result["success"]:
        # Convert funding rate to percentage using Decimal arithmetic
        funding_rate_pct = (result['funding_rate'] * Decimal("100")).quantize(Decimal("0.0001"))

        logger.info(
            f"✓ Position opened successfully\n"
            f"  Entry Price: ${result['entry_price']}\n"
            f"  Liquidation Price: ${result['liquidation_price']}\n"
            f"  Funding Rate: {result['funding_rate']} ({funding_rate_pct}%)\n"
            f"  Estimated Daily Funding: ${result['estimated_daily_funding']}"
        )
    else:
        logger.error(f"✗ Failed to open position: {result['reason']}")
        return

    # Monitor position
    logger.info("\n📈 Monitoring position...")
    pm.monitor_positions()

    # Check funding costs
    logger.info("\n💰 Funding Analysis:")
    funding_rate = funding.get_current_funding_rate("BTCUSDT")
    daily_cost = funding.estimate_daily_funding(
        "BTCUSDT", Decimal("0.001"), result["entry_price"]
    )

    # Convert funding rate to percentage using Decimal arithmetic
    current_funding_pct = (funding_rate * Decimal("100")).quantize(Decimal("0.0001"))

    logger.info(
        f"  Current Funding Rate: {funding_rate} ({current_funding_pct}%)\n"
        f"  Estimated Daily Cost: ${daily_cost}"
    )

    # Close position (for demo)
    logger.info("\n🔒 Closing position...")
    close_result = pm.close_position("BTCUSDT", reason="Demo completed")

    if close_result["success"]:
        logger.info(
            f"✓ Position closed\n"
            f"  Exit Price: ${close_result['exit_price']}\n"
            f"  P&L: ${close_result.get('pnl', 'N/A')}"
        )

    logger.info("\n=== Demo Complete! ===")
    logger.info(
        "\nNext steps:\n"
        "1. Check database for logged trades, positions, and PnL snapshots\n"
        "2. Review funding event history\n"
        "3. Analyze equity curve data\n"
        "4. Run 24-hour testnet simulation before live trading"
    )


if __name__ == "__main__":
    main()
