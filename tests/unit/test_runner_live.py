"""Unit tests for LiveRunner and RiskManager."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from trade_engine.core.engine.runner_live import LiveRunner
from trade_engine.core.engine.risk_manager import RiskManager, RiskCheckResult
from trade_engine.core.engine.types import Signal, Position


class TestRiskManager:
    """Test RiskManager risk checks."""

    def test_kill_switch_detects_file_flag(self, tmp_path):
        """Test kill switch activates when file flag exists."""
        # ARRANGE
        config = {"risk": {}}
        risk_manager = RiskManager(config)

        # ACT & ASSERT
        with patch("trade_engine.core.engine.risk_manager.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            result = risk_manager.check_kill_switch()

            assert result.passed is False
            assert "Kill switch file detected" in result.reason

    def test_kill_switch_detects_config_halt(self):
        """Test kill switch activates when config halt=true."""
        # ARRANGE
        config = {"risk": {"halt": True}}
        risk_manager = RiskManager(config)

        # ACT
        with patch("trade_engine.core.engine.risk_manager.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = risk_manager.check_kill_switch()

            # ASSERT
            assert result.passed is False
            assert "risk.halt=true" in result.reason

    def test_kill_switch_passes_when_inactive(self):
        """Test kill switch passes when not activated."""
        # ARRANGE
        config = {"risk": {}}
        risk_manager = RiskManager(config)

        # ACT
        with patch("trade_engine.core.engine.risk_manager.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = risk_manager.check_kill_switch()

            # ASSERT
            assert result.passed is True
            assert result.reason == ""


class TestDailyLossLimit:
    """Test daily loss limit enforcement."""

    def test_blocks_trade_when_loss_limit_exceeded(self):
        """Test daily loss limit blocks trades when exceeded."""
        # ARRANGE
        config = {"risk": {"max_daily_loss_usd": 100}}
        risk_manager = RiskManager(config)
        risk_manager.daily_pnl = -120  # Already lost $120

        positions = {}  # No open positions

        # ACT
        result = risk_manager.check_daily_loss(positions)

        # ASSERT
        assert result.passed is False
        assert "Daily loss limit exceeded" in result.reason
        assert "$-120" in result.reason  # Format is $-120.00

    def test_allows_trade_within_loss_limit(self):
        """Test daily loss limit allows trades within limit."""
        # ARRANGE
        config = {"risk": {"max_daily_loss_usd": 100}}
        risk_manager = RiskManager(config)
        risk_manager.daily_pnl = -50  # Lost $50, still ok

        positions = {}

        # ACT
        result = risk_manager.check_daily_loss(positions)

        # ASSERT
        assert result.passed is True

    def test_includes_unrealized_pnl_in_loss_calculation(self):
        """Test daily loss includes unrealized P&L from open positions."""
        # ARRANGE
        config = {"risk": {"max_daily_loss_usd": 100}}
        risk_manager = RiskManager(config)
        risk_manager.daily_pnl = -60  # Realized loss: $60

        # Open position with -$50 unrealized loss = -$110 total
        positions = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side="long",
                qty=0.001,
                entry_price=50000.0,
                current_price=48000.0,
                pnl=-50.0,  # -$50 unrealized
                pnl_pct=-4.0
            )
        }

        # ACT
        result = risk_manager.check_daily_loss(positions)

        # ASSERT (total -$110 > -$100 limit)
        assert result.passed is False


class TestTradeThrottle:
    """Test trade throttle (max trades/day) enforcement."""

    def test_blocks_trade_when_max_trades_reached(self):
        """Test trade throttle blocks when max trades/day reached."""
        # ARRANGE
        config = {"risk": {"max_trades_per_day": 20}}
        risk_manager = RiskManager(config)
        risk_manager.daily_trades = 20  # Already hit limit

        # ACT
        result = risk_manager.check_trade_throttle()

        # ASSERT
        assert result.passed is False
        assert "Max trades/day reached: 20/20" in result.reason

    def test_allows_trade_under_limit(self):
        """Test trade throttle allows trades under limit."""
        # ARRANGE
        config = {"risk": {"max_trades_per_day": 20}}
        risk_manager = RiskManager(config)
        risk_manager.daily_trades = 10  # Still have room

        # ACT
        result = risk_manager.check_trade_throttle()

        # ASSERT
        assert result.passed is True


class TestPositionSizing:
    """Test position size limit enforcement."""

    def test_blocks_oversized_position(self):
        """Test position sizing blocks trades that are too large."""
        # ARRANGE
        config = {"risk": {"max_position_usd": 1000}}
        risk_manager = RiskManager(config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.05,  # 0.05 BTC
            price=50000.0,  # = $2500 notional (too large)
            reason="test"
        )

        # ACT
        result = risk_manager.check_position_size(signal)

        # ASSERT
        assert result.passed is False
        assert "Position too large" in result.reason
        assert "$2500" in result.reason

    def test_allows_acceptable_position_size(self):
        """Test position sizing allows trades within limit."""
        # ARRANGE
        config = {"risk": {"max_position_usd": 1000}}
        risk_manager = RiskManager(config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.01,  # 0.01 BTC
            price=50000.0,  # = $500 notional (ok)
            reason="test"
        )

        # ACT
        result = risk_manager.check_position_size(signal)

        # ASSERT
        assert result.passed is True


class TestTradingHours:
    """Test trading hours restriction."""

    def test_allows_trading_when_no_hours_restriction(self):
        """Test trading hours allows all trades when not configured."""
        # ARRANGE
        config = {"risk": {}}  # No trading_hours restriction
        risk_manager = RiskManager(config)

        # ACT
        result = risk_manager.check_trading_hours()

        # ASSERT
        assert result.passed is True

    def test_blocks_trade_outside_hours(self):
        """Test trading hours blocks trades outside configured window."""
        # ARRANGE
        config = {"risk": {"trading_hours": {"start": "09:00", "end": "17:00"}}}
        risk_manager = RiskManager(config)

        # ACT - Mock current time to be 20:00 (outside hours)
        with patch("trade_engine.core.engine.risk_manager.datetime") as mock_dt:
            mock_dt.utcnow.return_value.time.return_value = __import__("datetime").time(20, 0)
            mock_dt.utcnow.return_value.replace.return_value.time.side_effect = [
                __import__("datetime").time(9, 0),  # start
                __import__("datetime").time(17, 0)  # end
            ]
            result = risk_manager.check_trading_hours()

            # ASSERT
            assert result.passed is False
            assert "Outside trading hours" in result.reason


class TestLiveRunner:
    """Test LiveRunner orchestration."""

    def test_runner_initializes_with_risk_manager(self):
        """Test LiveRunner creates RiskManager and AuditLogger."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()
        config = {"mode": "paper", "symbols": ["BTCUSDT"], "timeframe": "5m"}

        # ACT
        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ASSERT
        assert runner.risk_manager is not None
        assert runner.audit_logger is not None
        assert isinstance(runner.risk_manager, RiskManager)

    def test_runner_delegates_risk_checks(self):
        """Test LiveRunner delegates risk checks to RiskManager."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()
        mock_broker.positions.return_value = {}

        config = {"mode": "paper"}
        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.01,
            price=50000.0,
            reason="test"
        )

        # Mock risk manager to block trade
        runner.risk_manager.check_all = Mock(return_value=RiskCheckResult(
            passed=False,
            reason="Test block"
        ))

        # Create a mock bar
        from trade_engine.core.engine.types import Bar
        bar = Bar(
            timestamp=1609459200000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0
        )

        # ACT
        runner._execute_signal(signal, bar)

        # ASSERT - broker should NOT be called
        mock_broker.buy.assert_not_called()
        mock_broker.sell.assert_not_called()
