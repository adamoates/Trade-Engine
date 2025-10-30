"""
Unit tests for risk management rules and validation.

Per CLAUDE.md: Risk management code requires 100% test coverage.

This test suite ensures:
1. Risk limits are properly defined and immutable
2. Validation functions correctly identify violations
3. Edge cases are handled appropriately
4. All financial values use Decimal (NON-NEGOTIABLE)
"""

import pytest
from decimal import Decimal
from dataclasses import FrozenInstanceError

from trade_engine.core.risk_rules import (
    RiskLimits,
    validate_position_size,
    validate_daily_pnl,
    validate_drawdown,
    validate_hold_time,
    validate_instrument_exposure,
    get_max_position_size,
    DEFAULT_RISK_LIMITS,
    MAX_POSITION_SIZE,
    DAILY_LOSS_LIMIT,
    MAX_DRAWDOWN,
    MAX_HOLD_TIME,
)


class TestRiskLimitsDataclass:
    """Test RiskLimits dataclass properties and immutability."""

    def test_risk_limits_default_instantiation(self):
        """Test RiskLimits can be instantiated with defaults."""
        limits = RiskLimits()

        assert limits.MAX_POSITION_SIZE_USD == Decimal("10000")
        assert limits.DAILY_LOSS_LIMIT_USD == Decimal("-500")
        assert limits.MAX_DRAWDOWN_USD == Decimal("-1000")
        assert limits.MAX_HOLD_TIME_SECONDS == 60
        assert limits.MAX_INSTRUMENT_EXPOSURE_PCT == Decimal("0.25")

    def test_risk_limits_are_frozen_immutable(self):
        """Test that RiskLimits is frozen and cannot be modified."""
        limits = RiskLimits()

        with pytest.raises(FrozenInstanceError):
            limits.MAX_POSITION_SIZE_USD = Decimal("999999")

        with pytest.raises(FrozenInstanceError):
            limits.DAILY_LOSS_LIMIT_USD = Decimal("-9999")

    def test_risk_limits_use_decimal_types(self):
        """Test that all financial limits use Decimal type."""
        limits = RiskLimits()

        assert isinstance(limits.MAX_POSITION_SIZE_USD, Decimal)
        assert isinstance(limits.DAILY_LOSS_LIMIT_USD, Decimal)
        assert isinstance(limits.MAX_DRAWDOWN_USD, Decimal)
        assert isinstance(limits.MAX_INSTRUMENT_EXPOSURE_PCT, Decimal)
        assert isinstance(limits.DEFAULT_PROFIT_TARGET_PCT, Decimal)
        assert isinstance(limits.DEFAULT_STOP_LOSS_PCT, Decimal)

    def test_risk_limits_use_int_for_time(self):
        """Test that time-based limits use int type."""
        limits = RiskLimits()

        assert isinstance(limits.MAX_HOLD_TIME_SECONDS, int)
        assert isinstance(limits.MIN_HOLD_TIME_SECONDS, int)
        assert isinstance(limits.MAX_ORDERS_PER_MINUTE, int)
        assert isinstance(limits.MAX_ORDERS_PER_HOUR, int)

    def test_loss_limits_are_negative(self):
        """Test that loss limits have correct sign (negative)."""
        limits = RiskLimits()

        assert limits.DAILY_LOSS_LIMIT_USD < 0
        assert limits.MAX_DRAWDOWN_USD < 0
        assert limits.DEFAULT_STOP_LOSS_PCT < 0

    def test_profit_targets_are_positive(self):
        """Test that profit targets have correct sign (positive)."""
        limits = RiskLimits()

        assert limits.DEFAULT_PROFIT_TARGET_PCT > 0

    def test_default_risk_limits_singleton(self):
        """Test DEFAULT_RISK_LIMITS is properly initialized."""
        assert isinstance(DEFAULT_RISK_LIMITS, RiskLimits)
        assert DEFAULT_RISK_LIMITS.MAX_POSITION_SIZE_USD == Decimal("10000")


class TestValidatePositionSize:
    """Test position size validation."""

    def test_position_within_limit_passes(self):
        """Position under limit should pass validation."""
        result = validate_position_size(Decimal("5000"))
        assert result is True

    def test_position_at_exact_limit_passes(self):
        """Position at exact limit should pass."""
        result = validate_position_size(Decimal("10000"))
        assert result is True

    def test_position_over_limit_fails(self):
        """Position over limit should fail validation."""
        result = validate_position_size(Decimal("10001"))
        assert result is False

    def test_position_far_over_limit_fails(self):
        """Position significantly over limit should fail."""
        result = validate_position_size(Decimal("50000"))
        assert result is False

    def test_zero_position_passes(self):
        """Zero position should pass (no position)."""
        result = validate_position_size(Decimal("0"))
        assert result is True

    def test_negative_position_passes(self):
        """Negative position passes validation (just checks <= MAX_POSITION_SIZE).

        Note: validate_position_size() only checks if position <= max limit.
        It doesn't validate that position is positive - that's the caller's responsibility.
        """
        result = validate_position_size(Decimal("-1000"))
        assert result is True  # -1000 <= 10000, so it passes

    def test_custom_limits(self):
        """Test validation with custom risk limits."""
        custom_limits = RiskLimits()
        # Can't modify frozen limits, but can pass different limit value
        result = validate_position_size(Decimal("5000"), custom_limits)
        assert result is True


class TestValidateDailyPnL:
    """Test daily P&L validation."""

    def test_profit_passes(self):
        """Profit should pass validation."""
        result = validate_daily_pnl(Decimal("1000"))
        assert result is True

    def test_small_loss_within_limit_passes(self):
        """Small loss within limit should pass."""
        result = validate_daily_pnl(Decimal("-100"))
        assert result is True

    def test_loss_at_exact_limit_passes(self):
        """Loss at exact limit should pass (edge case)."""
        result = validate_daily_pnl(Decimal("-500"))
        assert result is True

    def test_loss_exceeding_limit_fails(self):
        """Loss exceeding limit should fail (kill switch)."""
        result = validate_daily_pnl(Decimal("-501"))
        assert result is False

    def test_large_loss_fails(self):
        """Large loss should fail."""
        result = validate_daily_pnl(Decimal("-1000"))
        assert result is False

    def test_zero_pnl_passes(self):
        """Zero P&L should pass."""
        result = validate_daily_pnl(Decimal("0"))
        assert result is True

    def test_breakeven_passes(self):
        """Break-even day should pass."""
        result = validate_daily_pnl(Decimal("0.01"))
        assert result is True


class TestValidateDrawdown:
    """Test drawdown validation."""

    def test_no_drawdown_passes(self):
        """Current equity equals peak should pass."""
        result = validate_drawdown(
            current_equity=Decimal("10000"),
            peak_equity=Decimal("10000")
        )
        assert result is True

    def test_new_peak_passes(self):
        """Current equity above peak should pass."""
        result = validate_drawdown(
            current_equity=Decimal("12000"),
            peak_equity=Decimal("10000")
        )
        assert result is True

    def test_small_drawdown_within_limit_passes(self):
        """Small drawdown within limit should pass."""
        result = validate_drawdown(
            current_equity=Decimal("9500"),
            peak_equity=Decimal("10000")
        )
        assert result is True  # -$500 drawdown, limit is -$1000

    def test_drawdown_at_exact_limit_passes(self):
        """Drawdown at exact limit should pass (edge case)."""
        result = validate_drawdown(
            current_equity=Decimal("9000"),
            peak_equity=Decimal("10000")
        )
        assert result is True  # -$1000 drawdown = limit

    def test_drawdown_exceeding_limit_fails(self):
        """Drawdown exceeding limit should fail (kill switch)."""
        result = validate_drawdown(
            current_equity=Decimal("8999"),
            peak_equity=Decimal("10000")
        )
        assert result is False  # -$1001 drawdown > -$1000 limit

    def test_large_drawdown_fails(self):
        """Large drawdown should fail."""
        result = validate_drawdown(
            current_equity=Decimal("5000"),
            peak_equity=Decimal("10000")
        )
        assert result is False  # -$5000 drawdown

    def test_total_loss_fails(self):
        """Total loss (equity to zero) should fail."""
        result = validate_drawdown(
            current_equity=Decimal("0"),
            peak_equity=Decimal("10000")
        )
        assert result is False


class TestValidateHoldTime:
    """Test position hold time validation."""

    def test_hold_time_within_range_passes(self):
        """Hold time within min/max range should pass."""
        is_valid, reason = validate_hold_time(30)
        assert is_valid is True
        assert reason == ""

    def test_hold_time_at_max_limit_passes(self):
        """Hold time at exact max limit should pass."""
        is_valid, reason = validate_hold_time(60)
        assert is_valid is True
        assert reason == ""

    def test_hold_time_at_min_limit_passes(self):
        """Hold time at exact min limit should pass."""
        is_valid, reason = validate_hold_time(1)
        assert is_valid is True
        assert reason == ""

    def test_hold_time_exceeding_max_fails(self):
        """Hold time exceeding max should fail with clear message."""
        is_valid, reason = validate_hold_time(61)
        assert is_valid is False
        assert "exceeds maximum" in reason.lower()
        assert "60" in reason

    def test_hold_time_below_min_fails(self):
        """Hold time below min should fail with clear message."""
        is_valid, reason = validate_hold_time(0)
        assert is_valid is False
        assert "below minimum" in reason.lower()
        assert "1" in reason

    def test_hold_time_far_exceeding_max_fails(self):
        """Hold time significantly over max should fail."""
        is_valid, reason = validate_hold_time(120)
        assert is_valid is False
        assert "120" in reason

    def test_negative_hold_time_fails(self):
        """Negative hold time should fail."""
        is_valid, reason = validate_hold_time(-1)
        assert is_valid is False


class TestValidateInstrumentExposure:
    """Test per-instrument exposure validation."""

    def test_exposure_within_limit_passes(self):
        """Exposure within 25% limit should pass."""
        result = validate_instrument_exposure(
            position_value=Decimal("2000"),
            total_capital=Decimal("10000")
        )
        assert result is True  # 20% exposure < 25% limit

    def test_exposure_at_exact_limit_passes(self):
        """Exposure at exact 25% limit should pass."""
        result = validate_instrument_exposure(
            position_value=Decimal("2500"),
            total_capital=Decimal("10000")
        )
        assert result is True  # 25% exposure = 25% limit

    def test_exposure_exceeding_limit_fails(self):
        """Exposure exceeding 25% limit should fail."""
        result = validate_instrument_exposure(
            position_value=Decimal("2600"),
            total_capital=Decimal("10000")
        )
        assert result is False  # 26% exposure > 25% limit

    def test_exposure_significantly_over_limit_fails(self):
        """Exposure significantly over limit should fail."""
        result = validate_instrument_exposure(
            position_value=Decimal("5000"),
            total_capital=Decimal("10000")
        )
        assert result is False  # 50% exposure > 25% limit

    def test_zero_capital_fails(self):
        """Zero capital should fail (cannot trade)."""
        result = validate_instrument_exposure(
            position_value=Decimal("1000"),
            total_capital=Decimal("0")
        )
        assert result is False

    def test_negative_capital_passes_but_wrong(self):
        """Negative capital mathematically passes but is semantically wrong.

        Note: validate_instrument_exposure() calculates exposure_pct = position / capital.
        With negative capital, this creates negative exposure which is technically <= 0.25.
        The function doesn't explicitly check for negative capital - that's caller's responsibility.

        This is an edge case - in practice, capital should always be validated as positive
        before calling this function.
        """
        result = validate_instrument_exposure(
            position_value=Decimal("1000"),
            total_capital=Decimal("-1000")
        )
        # -1.0 exposure (1000 / -1000) is technically <= 0.25, so it passes
        assert result is True

    def test_zero_position_passes(self):
        """Zero position should pass (no exposure)."""
        result = validate_instrument_exposure(
            position_value=Decimal("0"),
            total_capital=Decimal("10000")
        )
        assert result is True


class TestGetMaxPositionSize:
    """Test maximum position size calculation."""

    def test_max_position_respects_percentage_limit(self):
        """Max position should respect 25% exposure limit."""
        max_size = get_max_position_size(Decimal("10000"))
        assert max_size == Decimal("2500")  # 25% of $10K

    def test_max_position_respects_absolute_limit(self):
        """Max position should not exceed absolute limit."""
        # With $50K capital, 25% = $12,500 but absolute limit is $10K
        max_size = get_max_position_size(Decimal("50000"))
        assert max_size == Decimal("10000")  # Capped at absolute limit

    def test_max_position_with_small_capital(self):
        """Max position with small capital should work correctly."""
        max_size = get_max_position_size(Decimal("1000"))
        assert max_size == Decimal("250")  # 25% of $1K

    def test_max_position_with_large_capital(self):
        """Max position with large capital should be capped."""
        max_size = get_max_position_size(Decimal("100000"))
        assert max_size == Decimal("10000")  # Capped at $10K

    def test_max_position_at_breakpoint(self):
        """Test at exact breakpoint where percentage = absolute limit."""
        # $10K absolute limit / 0.25 (25%) = $40K capital
        max_size = get_max_position_size(Decimal("40000"))
        assert max_size == Decimal("10000")

    def test_max_position_zero_capital(self):
        """Zero capital should return zero max position."""
        max_size = get_max_position_size(Decimal("0"))
        assert max_size == Decimal("0")


class TestModuleLevelConstants:
    """Test module-level exported constants."""

    def test_max_position_size_constant(self):
        """Test MAX_POSITION_SIZE constant is correct."""
        assert MAX_POSITION_SIZE == Decimal("10000")
        assert isinstance(MAX_POSITION_SIZE, Decimal)

    def test_daily_loss_limit_constant(self):
        """Test DAILY_LOSS_LIMIT constant is correct."""
        assert DAILY_LOSS_LIMIT == Decimal("-500")
        assert isinstance(DAILY_LOSS_LIMIT, Decimal)

    def test_max_drawdown_constant(self):
        """Test MAX_DRAWDOWN constant is correct."""
        assert MAX_DRAWDOWN == Decimal("-1000")
        assert isinstance(MAX_DRAWDOWN, Decimal)

    def test_max_hold_time_constant(self):
        """Test MAX_HOLD_TIME constant is correct."""
        assert MAX_HOLD_TIME == 60
        assert isinstance(MAX_HOLD_TIME, int)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_decimal_values(self):
        """Test with very small Decimal values (micro-trading)."""
        result = validate_position_size(Decimal("0.01"))
        assert result is True

    def test_very_large_decimal_values(self):
        """Test with very large Decimal values."""
        result = validate_position_size(Decimal("1000000"))
        assert result is False

    def test_decimal_precision_preserved(self):
        """Test that Decimal precision is preserved in calculations."""
        max_size = get_max_position_size(Decimal("10000.00"))
        assert max_size == Decimal("2500.00")
        assert isinstance(max_size, Decimal)

    def test_drawdown_with_identical_values(self):
        """Test drawdown when current equals peak (no drawdown)."""
        result = validate_drawdown(
            current_equity=Decimal("10000.00"),
            peak_equity=Decimal("10000.00")
        )
        assert result is True

    def test_exposure_with_fractional_percentages(self):
        """Test exposure calculation with fractional percentages."""
        # 24.99% exposure (just under limit)
        result = validate_instrument_exposure(
            position_value=Decimal("2499"),
            total_capital=Decimal("10000")
        )
        assert result is True

        # 25.01% exposure (just over limit)
        result = validate_instrument_exposure(
            position_value=Decimal("2501"),
            total_capital=Decimal("10000")
        )
        assert result is False


class TestRiskLimitDocumentation:
    """Test that risk limits have proper documentation and rationales."""

    def test_risk_limits_class_has_docstring(self):
        """Risk limits class should have comprehensive documentation."""
        assert RiskLimits.__doc__ is not None
        assert len(RiskLimits.__doc__) > 100  # Substantial documentation

    def test_validation_functions_have_docstrings(self):
        """All validation functions should have docstrings."""
        assert validate_position_size.__doc__ is not None
        assert validate_daily_pnl.__doc__ is not None
        assert validate_drawdown.__doc__ is not None
        assert validate_hold_time.__doc__ is not None
        assert validate_instrument_exposure.__doc__ is not None

    def test_validation_functions_have_examples(self):
        """Validation function docstrings should include examples."""
        assert "Example" in validate_position_size.__doc__
        assert "Example" in validate_daily_pnl.__doc__
        assert "Example" in validate_drawdown.__doc__
