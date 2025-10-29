"""
Live bar-close trading runner.

Orchestrates:
- Data feed (bar-close only)
- Strategy signal generation
- Risk checks
- Broker execution
- Audit logging

Usage:
    python -m app.engine.runner_live --config config/paper.yaml
"""

import sys
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from trade_engine.core.constants import EXIT_SUCCESS, EXIT_FAILURE, EXIT_SIGINT
from trade_engine.core.types import DataFeed, Broker, Strategy, Bar
from trade_engine.domain.risk.risk_manager import RiskManager
from trade_engine.services.audit.logger import AuditLogger


class LiveRunner:
    """
    Bar-close live trading engine.

    Runs strategy on live bar feed with risk controls.
    Follows Single Responsibility Principle - delegates to:
    - RiskManager for risk checks
    - AuditLogger for compliance logging
    - Strategy for signal generation
    - Broker for order execution
    """

    def __init__(
        self,
        strategy: Strategy,
        data: DataFeed,
        broker: Broker,
        config: Dict[str, Any]
    ):
        """
        Initialize runner.

        Args:
            strategy: Strategy instance
            data: Data feed instance
            broker: Broker instance
            config: Configuration dict (from YAML)
        """
        self.strategy = strategy
        self.data = data
        self.broker = broker
        self.config = config

        # Delegate responsibilities
        self.risk_manager = RiskManager(config)
        self.audit_logger = AuditLogger()

        logger.info(f"LiveRunner initialized | Mode: {config.get('mode', 'unknown')}")
        logger.info(f"Symbols: {config.get('symbols', [])} | Timeframe: {config.get('timeframe', '?')}")

    def run(self):
        """
        Main trading loop.

        Runs continuously:
        1. Wait for next bar
        2. Update strategy
        3. Check risk
        4. Execute signals
        5. Log everything
        """
        logger.info("🚀 Starting live trading loop...")

        try:
            for bar in self.data.candles():
                self._process_bar(bar)

        except KeyboardInterrupt:
            logger.warning("⚠️ Interrupted by user (Ctrl+C)")
            self._shutdown()
            sys.exit(EXIT_SIGINT)

        except Exception as e:
            logger.exception(f"❌ Unexpected error: {e}")
            self._emergency_shutdown()
            sys.exit(EXIT_FAILURE)

    def _process_bar(self, bar: Bar):
        """
        Process single bar.

        Args:
            bar: Completed, validated bar
        """
        logger.debug(f"Bar received: {bar}")
        self.audit_logger.log_bar_received(bar)

        # Check kill switch before processing
        kill_check = self.risk_manager.check_kill_switch()
        if not kill_check.passed:
            logger.critical(f"🛑 KILL SWITCH: {kill_check.reason}")
            self._emergency_shutdown()
            sys.exit(EXIT_FAILURE)

        # Skip bars with quality issues
        if bar.zero_vol_flag:
            logger.warning(f"Skipping zero-volume bar: {bar.datetime}")
            self.audit_logger.log_bar_skipped(bar, "zero_volume")
            return

        if bar.gap_flag:
            logger.warning(f"Gap detected in bar: {bar.datetime}")
            self.audit_logger.log_bar_warning(bar, "gap_detected")

        # Update strategy state
        try:
            signals = self.strategy.on_bar(bar)
        except Exception as e:
            logger.exception(f"Strategy error: {e}")
            self.audit_logger.log_strategy_error(str(e), bar)
            return

        # No signals, done
        if not signals:
            return

        logger.info(f"🎯 Strategy generated {len(signals)} signal(s)")

        # Execute each signal (with risk checks)
        for signal in signals:
            self._execute_signal(signal, bar)

    def _execute_signal(self, signal, bar: Bar):
        """
        Execute signal with risk checks.

        Args:
            signal: Signal from strategy
            bar: Current bar (for logging)
        """
        logger.info(f"Signal: {signal}")
        self.audit_logger.log_signal_generated(signal, bar)

        # Run all risk checks
        positions = self.broker.positions()
        risk_check = self.risk_manager.check_all(signal, positions)

        if not risk_check.passed:
            logger.warning(f"⚠️ Risk block: {risk_check.reason}")
            self.audit_logger.log_risk_block(signal, risk_check.reason)
            return

        # Execute via broker
        try:
            if signal.side == "buy":
                order_id = self.broker.buy(signal.symbol, signal.qty, signal.sl, signal.tp)
            elif signal.side == "sell":
                order_id = self.broker.sell(signal.symbol, signal.qty, signal.sl, signal.tp)
            elif signal.side == "close":
                self.broker.close_all(signal.symbol)
                order_id = "close_all"
            else:
                logger.error(f"Invalid signal side: {signal.side}")
                return

            logger.success(f"✅ Executed {signal.side.upper()} | Order ID: {order_id}")
            self.audit_logger.log_order_placed(signal, order_id)

            # Update risk tracking
            self.risk_manager.record_trade()

        except Exception as e:
            logger.error(f"❌ Broker error: {e}")
            self.audit_logger.log_broker_error(signal, str(e))

    # ========== Shutdown Handlers ==========

    def _shutdown(self):
        """
        Graceful shutdown.

        Logs final state, but does NOT close positions (user decision).
        """
        logger.info("🛑 Shutting down gracefully...")

        # Log final state
        positions = self.broker.positions()
        balance = self.broker.balance()

        logger.info(f"Final balance: ${balance:.2f}")
        logger.info(f"Open positions: {len(positions)}")
        for symbol, pos in positions.items():
            logger.info(f"  {pos}")

        self.audit_logger.log_shutdown(balance, len(positions))

        logger.info("✅ Shutdown complete")

    def _emergency_shutdown(self):
        """
        Emergency shutdown.

        Closes all positions and halts.
        """
        logger.critical("🚨 EMERGENCY SHUTDOWN")

        try:
            positions = self.broker.positions()
            for symbol in positions.keys():
                logger.warning(f"Closing position: {symbol}")
                self.broker.close_all(symbol)

            self.audit_logger.log_emergency_shutdown(len(positions))

        except Exception as e:
            logger.exception(f"❌ Emergency shutdown failed: {e}")

        logger.critical("🛑 Emergency shutdown complete")


# ========== CLI Entry Point ==========

def main():
    """
    CLI entry point.

    Usage:
        python -m app.engine.runner_live --config config/paper.yaml
    """
    import argparse
    import yaml

    ap = argparse.ArgumentParser(description="MFT Live Trading Runner")
    ap.add_argument("--config", type=Path, required=True, help="Config file (YAML)")
    args = ap.parse_args()

    # Load config
    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    if not config:
        logger.warning(f"Config file {args.config} is empty. Using default settings.")
        config = {}

    # TODO: Instantiate components from config
    # - DataFeed (BinanceFuturesDataFeed)
    # - Broker (BinanceFuturesBroker)
    # - Strategy (TrendingLiveStrategy)

    logger.info("⚠️ Runner ready, but missing DataFeed/Strategy implementations")
    logger.info("Next: Implement BinanceFuturesDataFeed and TrendingLiveStrategy")

    # runner = LiveRunner(strategy, data, broker, config)
    # runner.run()


if __name__ == "__main__":
    main()
