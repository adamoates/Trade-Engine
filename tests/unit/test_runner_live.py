"""Unit tests for LiveRunner risk management."""
import os
import pytest
from pathlib import Path
from datetime import datetime, time
from unittest.mock import Mock, patch, MagicMock
from app.engine.runner_live import LiveRunner, RiskViolation, KillSwitchActivated
from app.engine.types import Signal, Position


class TestKillSwitchChecks:
    """Test kill switch activation detection."""

    def test_kill_switch_detects_file_flag(self, tmp_path):
        """Test kill switch activates when /tmp/mft_halt.flag exists."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()
        config = {"mode": "paper", "symbols": ["BTCUSDT"], "timeframe": "5m"}

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # Create kill switch file in temp path (mock the Path check)
        halt_flag = tmp_path / "mft_halt.flag"
        halt_flag.touch()

        # ACT & ASSERT
        with patch("app.engine.runner_live.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with pytest.raises(KillSwitchActivated, match="File flag detected"):
                runner._check_kill_switch()

    def test_kill_switch_detects_config_halt(self):
        """Test kill switch activates when config halt=true."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()
        config = {
            "mode": "paper",
            "symbols": ["BTCUSDT"],
            "timeframe": "5m",
            "halt": True  # Kill switch enabled in config
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ACT & ASSERT
        with patch("app.engine.runner_live.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            with pytest.raises(KillSwitchActivated, match="Config halt=true"):
                runner._check_kill_switch()

    def test_kill_switch_passes_when_not_activated(self):
        """Test kill switch check passes when not activated."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()
        config = {"mode": "paper", "halt": False}

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ACT & ASSERT (should not raise)
        with patch("app.engine.runner_live.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            runner._check_kill_switch()  # Should pass without exception


class TestDailyLossChecks:
    """Test daily loss limit enforcement."""

    def test_daily_loss_blocks_when_limit_exceeded(self):
        """Test that trading stops when daily loss limit is exceeded."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_daily_loss_usd": 20}  # $20 max loss
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_pnl = -15.0  # Already lost $15 today

        # Mock broker positions with -$10 unrealized loss
        mock_broker.positions.return_value = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side="long",
                qty=0.001,
                entry_price=50000.0,
                current_price=49000.0,
                pnl=-10.0,  # -$10 unrealized
                pnl_pct=-2.0
            )
        }

        # ACT & ASSERT
        # Total: -$15 (daily) + -$10 (unrealized) = -$25, exceeds -$20 limit
        with pytest.raises(RiskViolation, match="Daily loss limit hit"):
            runner._check_daily_loss()

    def test_daily_loss_passes_within_limit(self):
        """Test that trading continues when within daily loss limit."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_daily_loss_usd": 50}
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_pnl = -10.0  # Lost $10 today

        # Mock positions with -$5 unrealized loss
        mock_broker.positions.return_value = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side="long",
                qty=0.001,
                entry_price=50000.0,
                current_price=49500.0,
                pnl=-5.0,
                pnl_pct=-1.0
            )
        }

        # ACT & ASSERT (should not raise)
        # Total: -$10 + -$5 = -$15, within -$50 limit
        runner._check_daily_loss()

    def test_daily_loss_with_profit_passes(self):
        """Test that profitable days pass daily loss check."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {"mode": "paper", "risk": {"max_daily_loss_usd": 20}}

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_pnl = 10.0  # Made $10 profit today

        mock_broker.positions.return_value = {}  # No open positions

        # ACT & ASSERT (should not raise)
        runner._check_daily_loss()


class TestTradeThrottle:
    """Test trade throttle (max trades per day)."""

    def test_throttle_blocks_when_max_trades_reached(self):
        """Test that trading stops when max daily trades reached."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_trades_per_day": 10}
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_trades = 10  # Already made 10 trades

        # ACT & ASSERT
        with pytest.raises(RiskViolation, match="Max trades/day reached: 10/10"):
            runner._check_trade_throttle()

    def test_throttle_passes_below_limit(self):
        """Test that trading continues when below max trades."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_trades_per_day": 10}
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_trades = 5  # Only 5 trades so far

        # ACT & ASSERT (should not raise)
        runner._check_trade_throttle()

    def test_throttle_blocks_at_exact_limit(self):
        """Test that trading stops at exactly the limit."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {"mode": "paper", "risk": {"max_trades_per_day": 5}}

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_trades = 5  # Exactly at limit

        # ACT & ASSERT
        with pytest.raises(RiskViolation, match="Max trades/day reached"):
            runner._check_trade_throttle()


class TestPositionSizeChecks:
    """Test position size limit enforcement."""

    def test_position_size_blocks_oversized_trade(self):
        """Test that oversized positions are blocked."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_position_usd": 100}  # Max $100 per position
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # Signal for $150 position (exceeds limit)
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.003,  # 0.003 BTC
            price=50000.0,  # $50k per BTC
            sl=49000.0,
            tp=51000.0,
            reason="Test signal"
        )
        # Notional: 0.003 * 50000 = $150

        # ACT & ASSERT
        with pytest.raises(RiskViolation, match="Position too large: \\$150.00 > \\$100"):
            runner._check_position_size(signal)

    def test_position_size_passes_within_limit(self):
        """Test that position size check passes when within limit."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {"mode": "paper", "risk": {"max_position_usd": 200}}

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # Signal for $50 position (within limit)
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.001,
            price=50000.0,
            sl=None,
            tp=None,
            reason="Test"
        )
        # Notional: 0.001 * 50000 = $50

        # ACT & ASSERT (should not raise)
        runner._check_position_size(signal)


class TestTradingHoursChecks:
    """Test trading hours restriction enforcement."""

    def test_trading_hours_blocks_outside_hours(self):
        """Test that trading is blocked outside allowed hours."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {
                "trading_hours": {
                    "start": "09:00",  # 9am UTC
                    "end": "17:00"     # 5pm UTC
                }
            }
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ACT & ASSERT
        # Mock current time to 8am UTC (before trading hours)
        with patch("app.engine.runner_live.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 8, 30, 0)  # 8:30am UTC
            mock_datetime.utcnow.return_value = mock_now

            with pytest.raises(RiskViolation, match="Outside trading hours"):
                runner._check_trading_hours()

    def test_trading_hours_passes_within_hours(self):
        """Test that trading continues during allowed hours."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {
                "trading_hours": {
                    "start": "09:00",
                    "end": "17:00"
                }
            }
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ACT & ASSERT
        # Mock current time to 12pm UTC (within trading hours)
        with patch("app.engine.runner_live.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 1, 12, 0, 0)  # 12:00pm UTC
            mock_datetime.utcnow.return_value = mock_now

            runner._check_trading_hours()  # Should not raise

    def test_trading_hours_passes_when_not_configured(self):
        """Test that trading is allowed when no hours restriction configured."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {}  # No trading_hours configured
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)

        # ACT & ASSERT (should not raise at any time)
        runner._check_trading_hours()


class TestExecuteSignal:
    """Test signal execution with risk checks."""

    def test_execute_signal_runs_all_risk_checks(self):
        """Test that _execute_signal runs all risk checks before execution."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {
                "max_daily_loss_usd": 100,
                "max_trades_per_day": 20,
                "max_position_usd": 200
            }
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_trades = 0
        runner.daily_pnl = 0.0

        # Mock broker
        mock_broker.positions.return_value = {}
        mock_broker.buy.return_value = "order_12345"

        # Create signal
        from app.engine.types import Bar
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.001,
            price=50000.0,
            sl=49000.0,
            tp=51000.0,
            reason="Test signal"
        )
        bar = Bar(
            timestamp=int(datetime.now().timestamp() * 1000),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            gap_flag=False,
            zero_vol_flag=False
        )

        # ACT
        runner._execute_signal(signal, bar)

        # ASSERT
        mock_broker.buy.assert_called_once_with("BTCUSDT", 0.001, 49000.0, 51000.0)
        assert runner.daily_trades == 1  # Trade counter incremented

    def test_execute_signal_blocked_by_daily_loss(self):
        """Test that signal execution is blocked by daily loss limit."""
        # ARRANGE
        mock_strategy = Mock()
        mock_data = Mock()
        mock_broker = Mock()

        config = {
            "mode": "paper",
            "risk": {"max_daily_loss_usd": 10}
        }

        runner = LiveRunner(mock_strategy, mock_data, mock_broker, config)
        runner.daily_pnl = -15.0  # Already exceeded limit

        mock_broker.positions.return_value = {}

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.001,
            price=50000.0,
            sl=None,
            tp=None,
            reason="Test"
        )

        from app.engine.types import Bar
        bar = Bar(
            timestamp=int(datetime.now().timestamp() * 1000),
            open=50000.0,
            high=50000.0,
            low=50000.0,
            close=50000.0,
            volume=100.0
        )

        # ACT & ASSERT
        with pytest.raises(RiskViolation, match="Daily loss limit hit"):
            runner._execute_signal(signal, bar)

        # Broker should NOT be called
        mock_broker.buy.assert_not_called()
