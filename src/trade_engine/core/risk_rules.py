"""
Risk management rules and limits.

This module defines hard-coded risk limits that protect against catastrophic losses.
These limits are NON-NEGOTIABLE and should only be modified with extreme caution.

All financial values use Decimal for precision (NON-NEGOTIABLE per CLAUDE.md).

Key Philosophy:
- Position sizing prevents over-concentration
- Daily loss limits trigger kill switch before account destruction
- Drawdown limits protect against trending losses
- Time stops prevent holding positions too long in fast markets
- Per-instrument limits prevent correlation risk

These limits are enforced by RiskManager and cannot be overridden during live trading.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Final


@dataclass(frozen=True)
class RiskLimits:
    """
    Trading risk limits (frozen dataclass - immutable).

    These limits are configured for the initial trading phase with $10K capital.
    All values use Decimal for financial precision.

    Adjustments should only be made:
    1. After 60+ days of successful paper trading
    2. When increasing capital (scale proportionally)
    3. With documented justification in git commit message

    NEVER adjust limits to "squeeze in" a trade that exceeds them.
    """

    # ========== Position Sizing ==========
    MAX_POSITION_SIZE_USD: Final[Decimal] = Decimal("10000")
    """
    Maximum position value in USD.

    Rationale: Limits single-trade exposure to 100% of starting capital.
    For $10K account, one position maxes out the account.

    Scale with account size:
    - $10K account → $10K max position (100%)
    - $50K account → $25K max position (50%)
    - $100K account → $40K max position (40%)
    """

    MAX_INSTRUMENT_EXPOSURE_PCT: Final[Decimal] = Decimal("0.25")
    """
    Maximum exposure to single instrument (as fraction of total capital).

    Rationale: Prevents over-concentration in one market.
    With 25% limit, you can hold max 4 different positions.

    Example (for $10K account):
    - BTCUSDT position: $2,500 max (25%)
    - ETHUSDT position: $2,500 max (25%)
    - Total: $5,000 across both (50% of capital)
    """

    # ========== Loss Limits (Kill Switch Triggers) ==========
    DAILY_LOSS_LIMIT_USD: Final[Decimal] = Decimal("-500")
    """
    Maximum loss allowed in a single day (NEGATIVE value).

    Triggers kill switch to prevent further trading.

    Rationale: -$500 = 5% drawdown on $10K account.
    This is aggressive but appropriate for high-frequency strategy.
    Prevents "revenge trading" after bad streak.

    Reset: Daily at midnight UTC.
    """

    MAX_DRAWDOWN_USD: Final[Decimal] = Decimal("-1000")
    """
    Maximum drawdown from peak equity (NEGATIVE value).

    Triggers kill switch and requires manual review before resuming.

    Rationale: -$1,000 = 10% drawdown from peak equity.
    If you build account to $12K then lose back to $11K = kill switch.

    Reset: Manual only (after analysis and corrective action).
    """

    # ========== Time-Based Limits ==========
    MAX_HOLD_TIME_SECONDS: Final[int] = 60
    """
    Maximum time to hold a position (seconds).

    Time-based stop loss (exits after timeout regardless of P&L).

    Rationale: L2 imbalance is a short-term edge (5-60 second window).
    Holding longer exposes you to different market dynamics.
    Forces rapid win/loss realization.

    Exceptions: None - this is a hard limit for the L2 strategy.
    """

    MIN_HOLD_TIME_SECONDS: Final[int] = 1
    """
    Minimum time to hold a position (seconds).

    Prevents micro-scalping that could trigger exchange rate limits.

    Rationale: Gives the market time to move.
    Reduces order spam and potential exchange penalties.
    """

    # ========== Order Rate Limits ==========
    MAX_ORDERS_PER_MINUTE: Final[int] = 10
    """
    Maximum order placements per minute.

    Prevents order spam and exchange rate limit violations.

    Rationale: 10 orders/min = 1 order every 6 seconds (reasonable for MFT).
    Binance limit is 1200 orders/min, but we stay well below that.
    """

    MAX_ORDERS_PER_HOUR: Final[int] = 200
    """
    Maximum order placements per hour.

    Additional safeguard against runaway strategy.

    Rationale: 200 orders/hour = ~3.3 orders/minute average.
    If hitting this limit, strategy logic likely has a bug.
    """

    # ========== Profit Targets & Stop Losses ==========
    DEFAULT_PROFIT_TARGET_PCT: Final[Decimal] = Decimal("0.2")
    """
    Default take-profit percentage (0.2% = 20 basis points).

    Strategy-specific, can be overridden by individual strategies.

    Rationale: L2 imbalance edge is small but frequent.
    20 bps is achievable in seconds with strong imbalance.
    """

    DEFAULT_STOP_LOSS_PCT: Final[Decimal] = Decimal("-0.15")
    """
    Default stop-loss percentage (-0.15% = -15 basis points).

    Strategy-specific, can be overridden by individual strategies.

    Rationale: Tighter than profit target (1.33:1 risk/reward ratio).
    Accounts for slippage and rapid reversals in L2 data.
    """

    # ========== Capital Allocation ==========
    MIN_ACCOUNT_BALANCE_USD: Final[Decimal] = Decimal("100")
    """
    Minimum account balance to continue trading.

    If balance falls below this, kill switch triggers.

    Rationale: Below $100, position sizes become too small to profit
    after fees (Binance futures: 0.04% taker fee).
    """

    RESERVED_BALANCE_PCT: Final[Decimal] = Decimal("0.05")
    """
    Percentage of balance to reserve (not available for trading).

    Safety buffer for fees, slippage, and emergency situations.

    Rationale: 5% reserve on $10K = $500 buffer.
    Ensures you can always close positions and pay fees.
    """


# ========== Risk Rule Validation ==========

def validate_position_size(position_value_usd: Decimal, limits: RiskLimits = RiskLimits()) -> bool:
    """
    Validate position size against max limit.

    Args:
        position_value_usd: Position value in USD (must be Decimal)
        limits: Risk limits to check against

    Returns:
        True if position size is within limits

    Example:
        >>> validate_position_size(Decimal("5000"))
        True
        >>> validate_position_size(Decimal("15000"))
        False
    """
    return position_value_usd <= limits.MAX_POSITION_SIZE_USD


def validate_daily_pnl(daily_pnl_usd: Decimal, limits: RiskLimits = RiskLimits()) -> bool:
    """
    Validate daily P&L against loss limit.

    Args:
        daily_pnl_usd: Daily P&L in USD (NEGATIVE for loss, must be Decimal)
        limits: Risk limits to check against

    Returns:
        True if daily P&L is above loss limit (less negative)
        False if loss limit breached (triggers kill switch)

    Example:
        >>> validate_daily_pnl(Decimal("100"))  # Profit
        True
        >>> validate_daily_pnl(Decimal("-300"))  # Loss but within limit
        True
        >>> validate_daily_pnl(Decimal("-600"))  # Loss exceeds limit
        False
    """
    return daily_pnl_usd >= limits.DAILY_LOSS_LIMIT_USD


def validate_drawdown(current_equity: Decimal, peak_equity: Decimal,
                      limits: RiskLimits = RiskLimits()) -> bool:
    """
    Validate drawdown against max limit.

    Args:
        current_equity: Current account equity (must be Decimal)
        peak_equity: Highest equity reached (must be Decimal)
        limits: Risk limits to check against

    Returns:
        True if drawdown is within limits
        False if max drawdown exceeded (triggers kill switch)

    Example:
        >>> validate_drawdown(Decimal("9500"), Decimal("10000"))
        True  # -$500 drawdown (within -$1000 limit)
        >>> validate_drawdown(Decimal("8500"), Decimal("10000"))
        False  # -$1500 drawdown (exceeds -$1000 limit)
    """
    drawdown = current_equity - peak_equity
    return drawdown >= limits.MAX_DRAWDOWN_USD


def validate_hold_time(hold_time_seconds: int, limits: RiskLimits = RiskLimits()) -> tuple[bool, str]:
    """
    Validate position hold time.

    Args:
        hold_time_seconds: Time position has been held (seconds)
        limits: Risk limits to check against

    Returns:
        (is_valid, reason)
        - is_valid: True if hold time is within limits
        - reason: Explanation if invalid

    Example:
        >>> validate_hold_time(30)
        (True, "")
        >>> validate_hold_time(70)
        (False, "Hold time 70s exceeds max 60s")
    """
    if hold_time_seconds < limits.MIN_HOLD_TIME_SECONDS:
        return False, f"Hold time {hold_time_seconds}s below minimum {limits.MIN_HOLD_TIME_SECONDS}s"

    if hold_time_seconds > limits.MAX_HOLD_TIME_SECONDS:
        return False, f"Hold time {hold_time_seconds}s exceeds maximum {limits.MAX_HOLD_TIME_SECONDS}s"

    return True, ""


def validate_instrument_exposure(position_value: Decimal, total_capital: Decimal,
                                 limits: RiskLimits = RiskLimits()) -> bool:
    """
    Validate single-instrument exposure as percentage of capital.

    Args:
        position_value: Position value in USD (must be Decimal)
        total_capital: Total account capital (must be Decimal)
        limits: Risk limits to check against

    Returns:
        True if exposure is within per-instrument limit

    Example:
        >>> validate_instrument_exposure(Decimal("2000"), Decimal("10000"))
        True  # 20% exposure (within 25% limit)
        >>> validate_instrument_exposure(Decimal("3000"), Decimal("10000"))
        False  # 30% exposure (exceeds 25% limit)
    """
    if total_capital == 0:
        return False  # Cannot trade with zero capital

    exposure_pct = position_value / total_capital
    return exposure_pct <= limits.MAX_INSTRUMENT_EXPOSURE_PCT


def get_max_position_size(total_capital: Decimal, limits: RiskLimits = RiskLimits()) -> Decimal:
    """
    Calculate maximum allowed position size.

    Takes the minimum of:
    1. MAX_POSITION_SIZE_USD (absolute limit)
    2. MAX_INSTRUMENT_EXPOSURE_PCT * total_capital (percentage limit)

    Args:
        total_capital: Total account capital (must be Decimal)
        limits: Risk limits to use

    Returns:
        Maximum position size in USD (Decimal)

    Example:
        >>> get_max_position_size(Decimal("10000"))
        Decimal('2500')  # 25% of $10K = $2,500
        >>> get_max_position_size(Decimal("50000"))
        Decimal('10000')  # Capped at $10K absolute limit
    """
    # Percentage-based limit
    pct_limit = total_capital * limits.MAX_INSTRUMENT_EXPOSURE_PCT

    # Return minimum of absolute limit and percentage limit
    return min(limits.MAX_POSITION_SIZE_USD, pct_limit)


# ========== Module Constants ==========

# Default risk limits instance (use throughout the application)
DEFAULT_RISK_LIMITS = RiskLimits()

# Export commonly used limits as module-level constants
MAX_POSITION_SIZE = DEFAULT_RISK_LIMITS.MAX_POSITION_SIZE_USD
DAILY_LOSS_LIMIT = DEFAULT_RISK_LIMITS.DAILY_LOSS_LIMIT_USD
MAX_DRAWDOWN = DEFAULT_RISK_LIMITS.MAX_DRAWDOWN_USD
MAX_HOLD_TIME = DEFAULT_RISK_LIMITS.MAX_HOLD_TIME_SECONDS
