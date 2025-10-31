"""Tests for futures risk manager."""

import pytest
from decimal import Decimal
from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager


class TestFuturesRiskManager:
    """Test futures risk manager functionality."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return {
            "risk": {
                "max_daily_loss_usd": 500,
                "max_trades_per_day": 50,
                "max_position_usd": 10000,
            }
        }

    @pytest.fixture
    def risk_manager(self, config):
        """Create risk manager instance."""
        return FuturesRiskManager(config=config, max_leverage=5)

    def test_validate_leverage_valid(self, risk_manager):
        """Test leverage validation with valid leverage."""
        result = risk_manager.validate_leverage(3)
        assert result.passed is True

    def test_validate_leverage_at_max(self, risk_manager):
        """Test leverage validation at maximum."""
        result = risk_manager.validate_leverage(5)
        assert result.passed is True

    def test_validate_leverage_exceeds_max(self, risk_manager):
        """Test leverage validation exceeding maximum."""
        result = risk_manager.validate_leverage(10)
        assert result.passed is False
        assert "exceeds maximum" in result.reason

    def test_validate_leverage_zero(self, risk_manager):
        """Test leverage validation with zero."""
        result = risk_manager.validate_leverage(0)
        assert result.passed is False

    def test_validate_leverage_negative(self, risk_manager):
        """Test leverage validation with negative value."""
        result = risk_manager.validate_leverage(-1)
        assert result.passed is False

    def test_calculate_liquidation_price_long(self, risk_manager):
        """Test liquidation price calculation for long position."""
        liq_price = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("50000"),
            leverage=5,
            side="long",
            maintenance_margin_rate=Decimal("0.004"),
        )

        # Long liq = 50000 * (1 - 0.2 + 0.004) = 50000 * 0.804 = 40200
        assert liq_price == Decimal("40200.00")

    def test_calculate_liquidation_price_short(self, risk_manager):
        """Test liquidation price calculation for short position."""
        liq_price = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("50000"),
            leverage=5,
            side="short",
            maintenance_margin_rate=Decimal("0.004"),
        )

        # Short liq = 50000 * (1 + 0.2 - 0.004) = 50000 * 1.196 = 59800
        assert liq_price == Decimal("59800.00")

    def test_calculate_liquidation_price_high_leverage(self, risk_manager):
        """Test liquidation price with higher leverage."""
        liq_price = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("50000"), leverage=10, side="long"
        )

        # Long liq = 50000 * (1 - 0.1 + 0.004) = 50000 * 0.904 = 45200
        assert liq_price == Decimal("45200.00")

    def test_check_margin_health_healthy(self, risk_manager):
        """Test margin health check with healthy margin."""
        result = risk_manager.check_margin_health(
            account_balance=Decimal("10000"),
            maintenance_margin=Decimal("5000"),
            unrealized_pnl=Decimal("0"),
        )

        # Margin ratio = 10000 / 5000 = 2.0 (healthy)
        assert result["action"] == "ok"
        assert result["margin_ratio"] == Decimal("2.0")

    def test_check_margin_health_warning(self, risk_manager):
        """Test margin health check with low margin (warning level)."""
        result = risk_manager.check_margin_health(
            account_balance=Decimal("10000"),
            maintenance_margin=Decimal("9000"),
            unrealized_pnl=Decimal("0"),
        )

        # Margin ratio = 10000 / 9000 = 1.111 (< 1.15 buffer)
        assert result["action"] == "reduce_position"
        assert "buffer" in result["reason"]

    def test_check_margin_health_critical(self, risk_manager):
        """Test margin health check with critical margin."""
        result = risk_manager.check_margin_health(
            account_balance=Decimal("10000"),
            maintenance_margin=Decimal("11000"),
            unrealized_pnl=Decimal("0"),
        )

        # Margin ratio = 10000 / 11000 = 0.909 (< 1.0, liquidation imminent)
        assert result["action"] == "liquidate_all"
        assert "liquidation imminent" in result["reason"]

    def test_check_margin_health_with_unrealized_loss(self, risk_manager):
        """Test margin health with unrealized loss."""
        result = risk_manager.check_margin_health(
            account_balance=Decimal("10000"),
            maintenance_margin=Decimal("5000"),
            unrealized_pnl=Decimal("-4000"),
        )

        # Equity = 10000 - 4000 = 6000
        # Margin ratio = 6000 / 5000 = 1.2 (above buffer, healthy)
        assert result["action"] == "ok"

    def test_check_margin_health_no_positions(self, risk_manager):
        """Test margin health with no open positions."""
        result = risk_manager.check_margin_health(
            account_balance=Decimal("10000"),
            maintenance_margin=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )

        assert result["action"] == "ok"
        assert result["margin_ratio"] is None

    def test_validate_position_with_leverage_valid(self, risk_manager):
        """Test position validation with valid parameters."""
        result = risk_manager.validate_position_with_leverage(
            balance=Decimal("1000"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=5,
        )

        # Notional = 50000 * 0.1 = 5000
        # Required margin = 5000 / 5 = 1000 (exactly what we have)
        assert result.passed is True

    def test_validate_position_with_leverage_insufficient_margin(self, risk_manager):
        """Test position validation with insufficient margin."""
        result = risk_manager.validate_position_with_leverage(
            balance=Decimal("500"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=5,
        )

        # Required margin = 5000 / 5 = 1000 (need 1000, have 500)
        assert result.passed is False
        assert "Insufficient margin" in result.reason

    def test_validate_position_exceeds_hard_limit(self, risk_manager):
        """Test position validation exceeding hard limit."""
        result = risk_manager.validate_position_with_leverage(
            balance=Decimal("5000"),
            price=Decimal("50000"),
            size=Decimal("1.0"),
            leverage=5,
        )

        # Notional = 50000 * 1.0 = 50000 (exceeds $10k hard limit)
        assert result.passed is False
        assert "NON-NEGOTIABLE" in result.reason

    def test_can_open_position_all_checks_pass(self, risk_manager):
        """Test opening position when all checks pass."""
        result = risk_manager.can_open_position(
            balance=Decimal("2000"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=3,
        )

        # Notional = 5000, required margin = 1666.67, have 2000
        assert result["allowed"] is True
        assert "passed" in result["reason"]

    def test_can_open_position_kill_switch_active(self, risk_manager):
        """Test opening position with kill switch active."""
        risk_manager.kill_switch_active = True

        result = risk_manager.can_open_position(
            balance=Decimal("2000"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=3,
        )

        assert result["allowed"] is False
        assert "Kill switch" in result["reason"]

    def test_can_open_position_excessive_leverage(self, risk_manager):
        """Test opening position with excessive leverage."""
        result = risk_manager.can_open_position(
            balance=Decimal("2000"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=10,  # Exceeds max of 5
        )

        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

    def test_can_open_position_daily_loss_exceeded(self, risk_manager):
        """Test opening position when daily loss limit exceeded."""
        result = risk_manager.can_open_position(
            balance=Decimal("2000"),
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=3,
            current_pnl=Decimal("-600"),  # Exceeds -500 limit
        )

        assert result["allowed"] is False
        assert "Daily loss" in result["reason"]
        assert risk_manager.kill_switch_active is True

    def test_can_open_position_drawdown_exceeded(self, risk_manager):
        """Test opening position when drawdown limit exceeded."""
        result = risk_manager.can_open_position(
            balance=Decimal("3000"),  # Sufficient for margin (need 1666.67 for position)
            price=Decimal("50000"),
            size=Decimal("0.1"),
            leverage=3,
            current_pnl=Decimal("0"),
            peak_equity=Decimal("4000"),  # Drawdown = 1000 (exceeds 500 limit)
        )

        assert result["allowed"] is False
        assert "Drawdown" in result["reason"]
        assert risk_manager.kill_switch_active is True

    def test_trigger_kill_switch(self, risk_manager):
        """Test kill switch triggering."""
        assert risk_manager.kill_switch_active is False

        risk_manager.trigger_kill_switch("Test reason")

        assert risk_manager.kill_switch_active is True

    def test_liquidation_price_precision(self, risk_manager):
        """Test liquidation price is properly quantized."""
        liq_price = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("45678.12345"),
            leverage=3,
            side="long",
        )

        # Result should be quantized to 2 decimal places
        assert str(liq_price).count(".") == 1
        assert len(str(liq_price).split(".")[1]) == 2
