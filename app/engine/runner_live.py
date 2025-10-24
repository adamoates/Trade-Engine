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
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from loguru import logger

from app.engine.types import DataFeed, Broker, Strategy, Bar, Signal, Position


class RiskViolation(Exception):
    """Risk limit exceeded."""
    pass


class KillSwitchActivated(Exception):
    """Kill switch triggered."""
    pass


class LiveRunner:
    """
    Bar-close live trading engine.

    Runs strategy on live bar feed with risk controls.
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

        # Risk tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_trade_time = None

        # Audit log
        self.audit_log_path = Path(f"logs/audit_{self._today()}.jsonl")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

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
            sys.exit(130)  # Standard SIGINT exit code

        except KillSwitchActivated as e:
            logger.critical(f"🛑 KILL SWITCH: {e}")
            self._emergency_shutdown()
            sys.exit(1)

        except Exception as e:
            logger.exception(f"❌ Unexpected error: {e}")
            self._emergency_shutdown()
            sys.exit(1)

    def _process_bar(self, bar: Bar):
        """
        Process single bar.

        Args:
            bar: Completed, validated bar
        """
        logger.info(f"📊 {bar}")

        # Log bar
        self._log("bar_received", bar=self._bar_to_dict(bar))

        # Check kill switch
        self._check_kill_switch()

        # Skip bars with quality issues
        if bar.zero_vol_flag:
            logger.warning(f"⚠️ Skipping zero-volume bar: {bar.datetime}")
            self._log("bar_skipped", reason="zero_volume", bar=self._bar_to_dict(bar))
            return

        if bar.gap_flag:
            logger.warning(f"⚠️ Gap detected in bar: {bar.datetime}")
            self._log("bar_warning", reason="gap_detected", bar=self._bar_to_dict(bar))

        # Update strategy state
        try:
            signals = self.strategy.on_bar(bar)
        except Exception as e:
            logger.exception(f"❌ Strategy error: {e}")
            self._log("strategy_error", error=str(e), bar=self._bar_to_dict(bar))
            return

        # No signals, done
        if not signals:
            return

        logger.info(f"🎯 Strategy generated {len(signals)} signal(s)")

        # Execute each signal (with risk checks)
        for signal in signals:
            try:
                self._execute_signal(signal, bar)
            except RiskViolation as e:
                logger.warning(f"⚠️ Risk block: {e}")
                self._log("risk_block", signal=self._signal_to_dict(signal), reason=str(e))
            except Exception as e:
                logger.exception(f"❌ Execution error: {e}")
                self._log("execution_error", signal=self._signal_to_dict(signal), error=str(e))

    def _execute_signal(self, signal: Signal, bar: Bar):
        """
        Execute signal with risk checks.

        Args:
            signal: Signal from strategy
            bar: Current bar (for logging)

        Raises:
            RiskViolation: If risk check fails
        """
        logger.info(f"  {signal}")
        self._log("signal_generated", signal=self._signal_to_dict(signal), bar=self._bar_to_dict(bar))

        # Risk checks
        self._check_daily_loss()
        self._check_trade_throttle()
        self._check_position_size(signal)
        self._check_trading_hours()

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
                raise ValueError(f"Invalid signal side: {signal.side}")

            logger.success(f"✅ Executed {signal.side.upper()} | Order ID: {order_id}")
            self._log("order_placed", signal=self._signal_to_dict(signal), order_id=order_id)

            # Update tracking
            self.daily_trades += 1
            self.last_trade_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"❌ Broker error: {e}")
            self._log("broker_error", signal=self._signal_to_dict(signal), error=str(e))
            raise

    # ========== Risk Checks ==========

    def _check_kill_switch(self):
        """
        Check for kill switch activation.

        Checks:
        1. /tmp/mft_halt.flag file
        2. config.halt flag (if config supports reload)

        Raises:
            KillSwitchActivated: If kill switch detected
        """
        # File flag
        halt_flag = Path("/tmp/mft_halt.flag")
        if halt_flag.exists():
            raise KillSwitchActivated("File flag detected: /tmp/mft_halt.flag")

        # Config flag (future: support hot-reload)
        if self.config.get("halt", False):
            raise KillSwitchActivated("Config halt=true")

    def _check_daily_loss(self):
        """
        Check daily loss limit.

        Raises:
            RiskViolation: If daily loss exceeds max
        """
        max_loss = self.config.get("risk", {}).get("max_daily_loss_usd", 100)

        # Get current positions P&L
        positions = self.broker.positions()
        unrealized_pnl = sum(p.pnl for p in positions.values())

        total_pnl = self.daily_pnl + unrealized_pnl

        if total_pnl < -max_loss:
            raise RiskViolation(f"Daily loss limit hit: ${total_pnl:.2f} < -${max_loss}")

    def _check_trade_throttle(self):
        """
        Check trade throttle (max trades per day).

        Raises:
            RiskViolation: If max trades exceeded
        """
        max_trades = self.config.get("risk", {}).get("max_trades_per_day", 20)

        if self.daily_trades >= max_trades:
            raise RiskViolation(f"Max trades/day reached: {self.daily_trades}/{max_trades}")

    def _check_position_size(self, signal: Signal):
        """
        Check position size limits.

        Raises:
            RiskViolation: If position too large
        """
        max_position = self.config.get("risk", {}).get("max_position_usd", 1000)

        # Estimate notional (signal.price is approximate)
        notional = signal.qty * signal.price

        if notional > max_position:
            raise RiskViolation(
                f"Position too large: ${notional:.2f} > ${max_position}"
            )

    def _check_trading_hours(self):
        """
        Check if within trading hours.

        Raises:
            RiskViolation: If outside trading hours
        """
        trading_hours = self.config.get("risk", {}).get("trading_hours", {})
        if not trading_hours:
            return  # No restrictions

        now = datetime.utcnow().time()
        start_str = trading_hours.get("start", "00:00")
        end_str = trading_hours.get("end", "23:59")

        # Parse HH:MM
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))

        start = datetime.utcnow().replace(hour=start_h, minute=start_m).time()
        end = datetime.utcnow().replace(hour=end_h, minute=end_m).time()

        if not (start <= now <= end):
            raise RiskViolation(f"Outside trading hours: {now} not in {start}-{end}")

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

        self._log("shutdown", balance=balance, positions=len(positions))

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

            self._log("emergency_shutdown", positions_closed=len(positions))

        except Exception as e:
            logger.exception(f"❌ Emergency shutdown failed: {e}")

        logger.critical("🛑 Emergency shutdown complete")

    # ========== Logging ==========

    def _log(self, event: str, **kwargs):
        """
        Write to audit log (JSON lines).

        Args:
            event: Event type (bar_received, signal_generated, etc.)
            **kwargs: Event data
        """
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **kwargs
        }

        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(log_entry, default=str) + "\n")

    def _bar_to_dict(self, bar: Bar) -> dict:
        """Convert Bar to dict for logging."""
        return {
            "timestamp": bar.timestamp,
            "datetime": bar.datetime.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "gap_flag": bar.gap_flag,
            "zero_vol_flag": bar.zero_vol_flag
        }

    def _signal_to_dict(self, signal: Signal) -> dict:
        """Convert Signal to dict for logging."""
        return {
            "symbol": signal.symbol,
            "side": signal.side,
            "qty": signal.qty,
            "price": signal.price,
            "sl": signal.sl,
            "tp": signal.tp,
            "reason": signal.reason
        }

    @staticmethod
    def _today() -> str:
        """Get today's date (YYYY-MM-DD)."""
        return datetime.utcnow().strftime("%Y-%m-%d")


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
    with open(args.config) as f:
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
