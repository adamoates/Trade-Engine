"""
Audit logging for live trading.

Writes structured JSON logs for compliance and debugging.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any
from loguru import logger

from trade_engine.core.constants import AUDIT_LOG_DIR, AUDIT_LOG_PREFIX, DATE_FORMAT_YYYY_MM_DD
from trade_engine.core.engine.types import Bar, Signal


class AuditLogger:
    """
    Structured audit logger for trading events.

    Writes JSON lines to daily log files for:
    - Compliance tracking
    - Debugging
    - Performance analysis
    - Trade reconstruction
    """

    def __init__(self, log_dir: str = AUDIT_LOG_DIR):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory for audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Current log file (updated daily)
        self._log_file_path = self._get_log_file_path()

        logger.info(f"AuditLogger initialized | Log file: {self._log_file_path}")

    def _get_log_file_path(self) -> Path:
        """Get current log file path (daily rotation)."""
        today = datetime.utcnow().strftime(DATE_FORMAT_YYYY_MM_DD)
        return self.log_dir / f"{AUDIT_LOG_PREFIX}_{today}.jsonl"

    def _write(self, event: str, **kwargs: Any):
        """
        Write audit log entry.

        Args:
            event: Event type (bar_received, signal_generated, etc.)
            **kwargs: Event data
        """
        # Check if we need to rotate log file (new day)
        current_path = self._get_log_file_path()
        if current_path != self._log_file_path:
            logger.info(f"Rotating audit log | New file: {current_path}")
            self._log_file_path = current_path

        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **kwargs
        }

        try:
            with open(self._log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")
        except IOError as e:
            logger.error(f"Failed to write audit log: {e}")

    # ========== Bar Events ==========

    def log_bar_received(self, bar: Bar):
        """Log completed bar reception."""
        self._write("bar_received", bar=self._bar_to_dict(bar))

    def log_bar_skipped(self, bar: Bar, reason: str):
        """Log skipped bar (zero volume, etc.)."""
        self._write("bar_skipped", reason=reason, bar=self._bar_to_dict(bar))

    def log_bar_warning(self, bar: Bar, reason: str):
        """Log bar quality warning (gap, etc.)."""
        self._write("bar_warning", reason=reason, bar=self._bar_to_dict(bar))

    # ========== Signal Events ==========

    def log_signal_generated(self, signal: Signal, bar: Bar):
        """Log strategy signal generation."""
        self._write(
            "signal_generated",
            signal=self._signal_to_dict(signal),
            bar=self._bar_to_dict(bar)
        )

    def log_risk_block(self, signal: Signal, reason: str):
        """Log signal blocked by risk check."""
        self._write(
            "risk_block",
            signal=self._signal_to_dict(signal),
            reason=reason
        )

    # ========== Order Events ==========

    def log_order_placed(self, signal: Signal, order_id: str):
        """Log successful order placement."""
        self._write(
            "order_placed",
            signal=self._signal_to_dict(signal),
            order_id=order_id
        )

    # ========== Error Events ==========

    def log_strategy_error(self, error: str, bar: Bar):
        """Log strategy execution error."""
        self._write(
            "strategy_error",
            error=error,
            bar=self._bar_to_dict(bar)
        )

    def log_execution_error(self, signal: Signal, error: str):
        """Log order execution error."""
        self._write(
            "execution_error",
            signal=self._signal_to_dict(signal),
            error=error
        )

    def log_broker_error(self, signal: Signal, error: str):
        """Log broker API error."""
        self._write(
            "broker_error",
            signal=self._signal_to_dict(signal),
            error=error
        )

    # ========== Lifecycle Events ==========

    def log_shutdown(self, balance: float, positions: int):
        """Log graceful shutdown."""
        self._write(
            "shutdown",
            balance=balance,
            positions=positions
        )

    def log_emergency_shutdown(self, positions_closed: int):
        """Log emergency shutdown."""
        self._write(
            "emergency_shutdown",
            positions_closed=positions_closed
        )

    # ========== Helper Methods ==========

    @staticmethod
    def _bar_to_dict(bar: Bar) -> dict:
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

    @staticmethod
    def _signal_to_dict(signal: Signal) -> dict:
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
