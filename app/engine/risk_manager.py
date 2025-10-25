"""
Risk management for live trading.

Handles all risk checks including:
- Daily loss limits
- Trade throttling
- Position sizing
- Trading hours
- Kill switch monitoring
"""

from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from dataclasses import dataclass
from loguru import logger

from app.constants import (
    KILL_SWITCH_FILE_PATH,
    DEFAULT_MAX_DAILY_LOSS_USD,
    DEFAULT_MAX_TRADES_PER_DAY,
    DEFAULT_MAX_POSITION_USD
)
from app.engine.types import Signal, Position


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    passed: bool
    reason: str = ""


class RiskManager:
    """
    Manages risk controls for live trading.

    Uses boolean returns instead of exceptions for control flow.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize risk manager.

        Args:
            config: Full configuration dict with 'risk' section containing:
                - max_daily_loss_usd (float)
                - max_trades_per_day (int)
                - max_position_usd (float)
                - trading_hours (dict with start/end keys)
                - halt (bool) - can be at risk.halt or top-level halt
                - kill_switch_file (str) - path to kill switch file
        """
        self.full_config = config  # Store full config to check top-level halt
        self.config = config.get("risk", {})

        # Risk limits (convert to Decimal for precise financial calculations)
        self.max_daily_loss = Decimal(str(self.config.get("max_daily_loss_usd", DEFAULT_MAX_DAILY_LOSS_USD)))
        self.max_trades_per_day = self.config.get("max_trades_per_day", DEFAULT_MAX_TRADES_PER_DAY)
        self.max_position_usd = Decimal(str(self.config.get("max_position_usd", DEFAULT_MAX_POSITION_USD)))
        self.trading_hours = self.config.get("trading_hours", {})

        # Kill switch file path (configurable, falls back to constant)
        self.kill_switch_file = self.config.get("kill_switch_file", KILL_SWITCH_FILE_PATH)

        # Tracking
        self.daily_trades = 0
        self.daily_pnl = Decimal("0")
        self.last_trade_time = None

        logger.info(
            f"RiskManager initialized | "
            f"MaxLoss=${self.max_daily_loss} | "
            f"MaxTrades={self.max_trades_per_day} | "
            f"MaxPos=${self.max_position_usd}"
        )

    def check_kill_switch(self) -> RiskCheckResult:
        """
        Check for kill switch activation.

        Checks:
        1. Configured kill switch file existence (risk.kill_switch_file)
        2. Top-level halt flag (halt)
        3. Risk-level halt flag (risk.halt)

        Returns:
            RiskCheckResult with passed=False if kill switch active
        """
        # Check configured kill switch file
        halt_flag = Path(self.kill_switch_file)
        if halt_flag.exists():
            return RiskCheckResult(
                passed=False,
                reason=f"Kill switch file detected: {self.kill_switch_file}"
            )

        # Check top-level halt flag (backward compatibility)
        if self.full_config.get("halt", False):
            return RiskCheckResult(
                passed=False,
                reason="Config halt=true (top-level)"
            )

        # Check risk-level halt flag
        if self.config.get("halt", False):
            return RiskCheckResult(
                passed=False,
                reason="Config risk.halt=true"
            )

        return RiskCheckResult(passed=True)

    def check_daily_loss(self, positions: Dict[str, Position]) -> RiskCheckResult:
        """
        Check daily loss limit.

        Args:
            positions: Current open positions

        Returns:
            RiskCheckResult with passed=False if loss limit exceeded
        """
        # Calculate unrealized P&L from open positions
        unrealized_pnl = sum(p.pnl for p in positions.values())
        total_pnl = self.daily_pnl + unrealized_pnl

        if total_pnl < -self.max_daily_loss:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily loss limit exceeded: ${total_pnl:.2f} < -${self.max_daily_loss}"
            )

        return RiskCheckResult(passed=True)

    def check_trade_throttle(self) -> RiskCheckResult:
        """
        Check trade throttle (max trades per day).

        Returns:
            RiskCheckResult with passed=False if max trades exceeded
        """
        if self.daily_trades >= self.max_trades_per_day:
            return RiskCheckResult(
                passed=False,
                reason=f"Max trades/day reached: {self.daily_trades}/{self.max_trades_per_day}"
            )

        return RiskCheckResult(passed=True)

    def check_position_size(self, signal: Signal) -> RiskCheckResult:
        """
        Check position size limits.

        Args:
            signal: Trading signal to validate

        Returns:
            RiskCheckResult with passed=False if position too large
        """
        # Estimate notional (signal.price is approximate)
        notional = signal.qty * signal.price

        if notional > self.max_position_usd:
            return RiskCheckResult(
                passed=False,
                reason=f"Position too large: ${notional:.2f} > ${self.max_position_usd}"
            )

        return RiskCheckResult(passed=True)

    def check_trading_hours(self) -> RiskCheckResult:
        """
        Check if within trading hours.

        Returns:
            RiskCheckResult with passed=False if outside trading hours
        """
        if not self.trading_hours:
            return RiskCheckResult(passed=True)  # No restrictions

        now = datetime.utcnow().time()
        start_str = self.trading_hours.get("start", "00:00")
        end_str = self.trading_hours.get("end", "23:59")

        # Parse HH:MM
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))

        start = datetime.utcnow().replace(hour=start_h, minute=start_m).time()
        end = datetime.utcnow().replace(hour=end_h, minute=end_m).time()

        # Handle midnight wrap-around (e.g., 22:00-02:00)
        if start <= end:
            # Normal range (e.g., 08:00-18:00)
            in_hours = start <= now <= end
        else:
            # Wrap-around range (e.g., 22:00-02:00)
            # Trading allowed if: now >= 22:00 OR now <= 02:00
            in_hours = now >= start or now <= end

        if not in_hours:
            return RiskCheckResult(
                passed=False,
                reason=f"Outside trading hours: {now} not in {start}-{end}"
            )

        return RiskCheckResult(passed=True)

    def check_all(self, signal: Signal, positions: Dict[str, Position]) -> RiskCheckResult:
        """
        Run all risk checks.

        Args:
            signal: Trading signal to validate
            positions: Current open positions

        Returns:
            RiskCheckResult with first failed check, or passed=True if all pass
        """
        checks = [
            self.check_kill_switch(),
            self.check_daily_loss(positions),
            self.check_trade_throttle(),
            self.check_position_size(signal),
            self.check_trading_hours()
        ]

        for check in checks:
            if not check.passed:
                return check

        return RiskCheckResult(passed=True)

    def record_trade(self):
        """Record a trade execution."""
        self.daily_trades += 1
        self.last_trade_time = datetime.utcnow()
        logger.debug(f"Trade recorded | Daily count: {self.daily_trades}")

    def update_daily_pnl(self, pnl: Decimal):
        """Update daily realized P&L."""
        self.daily_pnl += pnl
        logger.debug(f"Daily P&L updated: ${self.daily_pnl:.2f}")

    def reset_daily_counters(self):
        """Reset daily counters (call at start of new trading day)."""
        logger.info(
            f"Resetting daily counters | "
            f"Trades: {self.daily_trades} | "
            f"P&L: ${self.daily_pnl:.2f}"
        )
        self.daily_trades = 0
        self.daily_pnl = Decimal("0")
        self.last_trade_time = None
