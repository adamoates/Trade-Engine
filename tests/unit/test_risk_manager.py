"""
Unit tests for RiskManager.

Tests critical risk controls including:
- Daily loss limits
- Trade throttling
- Position sizing
- Trading hours (including midnight wrap-around)
- Kill switch activation
"""

import pytest
from decimal import Decimal
from datetime import datetime, time
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.engine.risk_manager import RiskManager, RiskCheckResult
from app.engine.types import Signal, Position


class TestRiskManagerInit:
    """Test RiskManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        config = {"risk": {}}
        rm = RiskManager(config)

        assert rm.max_daily_loss == Decimal("100")  # DEFAULT_MAX_DAILY_LOSS_USD
        assert rm.max_trades_per_day == 20  # DEFAULT_MAX_TRADES_PER_DAY
        assert rm.max_position_usd == Decimal("1000")  # DEFAULT_MAX_POSITION_USD
        assert rm.daily_trades == 0
        assert rm.daily_pnl == Decimal("0")

    def test_init_with_custom_limits(self):
        """Test initialization with custom risk limits."""
        config = {
            "risk": {
                "max_daily_loss_usd": 200,
                "max_trades_per_day": 20,
                "max_position_usd": 5000,
            }
        }
        rm = RiskManager(config)

        assert rm.max_daily_loss == Decimal("200")
        assert rm.max_trades_per_day == 20
        assert rm.max_position_usd == Decimal("5000")


class TestKillSwitch:
    """Test kill switch functionality."""

    def test_kill_switch_file_exists(self, tmp_path):
        """Test kill switch triggers when file exists."""
        config = {"risk": {}}
        rm = RiskManager(config)

        # Mock KILL_SWITCH_FILE_PATH to temp file
        kill_file = tmp_path / "kill_switch.flag"
        kill_file.touch()

        with patch("app.engine.risk_manager.KILL_SWITCH_FILE_PATH", str(kill_file)):
            result = rm.check_kill_switch()

        assert result.passed is False
        assert "Kill switch file detected" in result.reason

    def test_kill_switch_config_halt(self):
        """Test kill switch triggers from config halt flag."""
        config = {"risk": {"halt": True}}
        rm = RiskManager(config)

        result = rm.check_kill_switch()

        assert result.passed is False
        assert "Config halt=true" in result.reason

    def test_kill_switch_not_active(self, tmp_path):
        """Test kill switch allows trading when not active."""
        config = {"risk": {"halt": False}}
        rm = RiskManager(config)

        # Mock KILL_SWITCH_FILE_PATH to non-existent file
        kill_file = tmp_path / "kill_switch.flag"

        with patch("app.engine.risk_manager.KILL_SWITCH_FILE_PATH", str(kill_file)):
            result = rm.check_kill_switch()

        assert result.passed is True


class TestDailyLossLimit:
    """Test daily loss limit enforcement."""

    def test_daily_loss_under_limit(self):
        """Test passes when daily loss is under limit."""
        config = {"risk": {"max_daily_loss_usd": 500}}
        rm = RiskManager(config)
        rm.daily_pnl = Decimal("-300")  # $300 loss

        positions = {}  # No open positions
        result = rm.check_daily_loss(positions)

        assert result.passed is True

    def test_daily_loss_exceeds_limit(self):
        """Test fails when daily loss exceeds limit."""
        config = {"risk": {"max_daily_loss_usd": 500}}
        rm = RiskManager(config)
        rm.daily_pnl = Decimal("-600")  # $600 loss (exceeds $500 limit)

        positions = {}
        result = rm.check_daily_loss(positions)

        assert result.passed is False
        assert "Daily loss limit exceeded" in result.reason

    def test_daily_loss_with_unrealized_pnl(self):
        """Test includes unrealized P&L from open positions."""
        config = {"risk": {"max_daily_loss_usd": 500}}
        rm = RiskManager(config)
        rm.daily_pnl = Decimal("-300")  # $300 realized loss

        # Open position with $250 unrealized loss
        position = Position(
            symbol="BTCUSDT",
            side="long",
            qty=Decimal("0.01"),
            entry_price=Decimal("50000"),
            current_price=Decimal("48000"),
            pnl=Decimal("-250"),  # Unrealized loss
            pnl_pct=Decimal("-4.0"),
        )
        positions = {"BTCUSDT": position}

        # Total: -300 (realized) + -250 (unrealized) = -550 (exceeds -500 limit)
        result = rm.check_daily_loss(positions)

        assert result.passed is False
        assert "Daily loss limit exceeded" in result.reason


class TestTradeThrottle:
    """Test trade throttle (max trades per day)."""

    def test_trade_count_under_limit(self):
        """Test passes when trade count is under limit."""
        config = {"risk": {"max_trades_per_day": 50}}
        rm = RiskManager(config)
        rm.daily_trades = 30

        result = rm.check_trade_throttle()

        assert result.passed is True

    def test_trade_count_at_limit(self):
        """Test fails when trade count reaches limit."""
        config = {"risk": {"max_trades_per_day": 50}}
        rm = RiskManager(config)
        rm.daily_trades = 50

        result = rm.check_trade_throttle()

        assert result.passed is False
        assert "Max trades/day reached" in result.reason

    def test_trade_count_exceeds_limit(self):
        """Test fails when trade count exceeds limit."""
        config = {"risk": {"max_trades_per_day": 50}}
        rm = RiskManager(config)
        rm.daily_trades = 55

        result = rm.check_trade_throttle()

        assert result.passed is False


class TestPositionSize:
    """Test position size limits."""

    def test_position_under_limit(self):
        """Test passes when position size is under limit."""
        config = {"risk": {"max_position_usd": 10000}}
        rm = RiskManager(config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=Decimal("0.1"),  # 0.1 BTC
            price=Decimal("50000"),  # $50k/BTC = $5k notional
        )

        result = rm.check_position_size(signal)

        assert result.passed is True

    def test_position_exceeds_limit(self):
        """Test fails when position size exceeds limit."""
        config = {"risk": {"max_position_usd": 10000}}
        rm = RiskManager(config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=Decimal("0.5"),  # 0.5 BTC
            price=Decimal("50000"),  # $50k/BTC = $25k notional (exceeds $10k limit)
        )

        result = rm.check_position_size(signal)

        assert result.passed is False
        assert "Position too large" in result.reason


class TestTradingHours:
    """Test trading hours enforcement (including midnight wrap-around)."""

    def test_no_trading_hours_restriction(self):
        """Test passes when no trading hours configured."""
        config = {"risk": {}}
        rm = RiskManager(config)

        result = rm.check_trading_hours()

        assert result.passed is True

    def test_normal_hours_inside_range(self):
        """Test passes when inside normal trading hours (08:00-18:00)."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "08:00",
                    "end": "18:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to 12:00 (inside 08:00-18:00)
        mock_now = datetime(2025, 1, 15, 12, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is True

    def test_normal_hours_outside_range(self):
        """Test fails when outside normal trading hours (08:00-18:00)."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "08:00",
                    "end": "18:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to 20:00 (outside 08:00-18:00)
        mock_now = datetime(2025, 1, 15, 20, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is False
        assert "Outside trading hours" in result.reason

    def test_overnight_hours_before_midnight(self):
        """Test passes when inside overnight range (22:00-02:00) before midnight."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "22:00",
                    "end": "02:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to 23:00 (inside 22:00-02:00 range, before midnight)
        mock_now = datetime(2025, 1, 15, 23, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is True

    def test_overnight_hours_after_midnight(self):
        """Test passes when inside overnight range (22:00-02:00) after midnight."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "22:00",
                    "end": "02:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to 01:00 (inside 22:00-02:00 range, after midnight)
        mock_now = datetime(2025, 1, 15, 1, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is True

    def test_overnight_hours_outside_range(self):
        """Test fails when outside overnight range (22:00-02:00)."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "22:00",
                    "end": "02:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to 10:00 (outside 22:00-02:00 range)
        mock_now = datetime(2025, 1, 15, 10, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is False
        assert "Outside trading hours" in result.reason

    def test_overnight_hours_at_start_boundary(self):
        """Test passes when exactly at start boundary of overnight range."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "22:00",
                    "end": "02:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to exactly 22:00
        mock_now = datetime(2025, 1, 15, 22, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is True

    def test_overnight_hours_at_end_boundary(self):
        """Test passes when exactly at end boundary of overnight range."""
        config = {
            "risk": {
                "trading_hours": {
                    "start": "22:00",
                    "end": "02:00",
                }
            }
        }
        rm = RiskManager(config)

        # Mock current time to exactly 02:00
        mock_now = datetime(2025, 1, 15, 2, 0, 0)
        with patch("app.engine.risk_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = mock_now
            result = rm.check_trading_hours()

        assert result.passed is True


class TestCheckAll:
    """Test combined risk checks."""

    def test_all_checks_pass(self, tmp_path):
        """Test passes when all risk checks pass."""
        config = {
            "risk": {
                "halt": False,
                "max_daily_loss_usd": 500,
                "max_trades_per_day": 50,
                "max_position_usd": 10000,
            }
        }
        rm = RiskManager(config)
        rm.daily_trades = 10
        rm.daily_pnl = Decimal("-100")

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=Decimal("0.1"),
            price=Decimal("50000"),
        )
        positions = {}

        # Mock kill switch file to not exist
        kill_file = tmp_path / "kill_switch.flag"
        with patch("app.engine.risk_manager.KILL_SWITCH_FILE_PATH", str(kill_file)):
            result = rm.check_all(signal, positions)

        assert result.passed is True

    def test_kill_switch_fails_first(self, tmp_path):
        """Test returns kill switch failure first (highest priority)."""
        config = {"risk": {"halt": True}}  # Kill switch active
        rm = RiskManager(config)

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=Decimal("0.1"),
            price=Decimal("50000"),
        )
        positions = {}

        result = rm.check_all(signal, positions)

        assert result.passed is False
        assert "halt" in result.reason.lower()

    def test_daily_loss_fails(self, tmp_path):
        """Test returns daily loss failure when exceeded."""
        config = {
            "risk": {
                "halt": False,
                "max_daily_loss_usd": 500,
            }
        }
        rm = RiskManager(config)
        rm.daily_pnl = Decimal("-600")  # Exceeds limit

        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=Decimal("0.1"),
            price=Decimal("50000"),
        )
        positions = {}

        kill_file = tmp_path / "kill_switch.flag"
        with patch("app.engine.risk_manager.KILL_SWITCH_FILE_PATH", str(kill_file)):
            result = rm.check_all(signal, positions)

        assert result.passed is False
        assert "Daily loss limit exceeded" in result.reason


class TestRecordTrade:
    """Test trade recording."""

    def test_record_trade_increments_counter(self):
        """Test recording a trade increments counter."""
        config = {"risk": {}}
        rm = RiskManager(config)

        assert rm.daily_trades == 0

        rm.record_trade()

        assert rm.daily_trades == 1
        assert rm.last_trade_time is not None

    def test_record_multiple_trades(self):
        """Test recording multiple trades."""
        config = {"risk": {}}
        rm = RiskManager(config)

        rm.record_trade()
        rm.record_trade()
        rm.record_trade()

        assert rm.daily_trades == 3


class TestUpdateDailyPnL:
    """Test daily P&L tracking."""

    def test_update_daily_pnl_positive(self):
        """Test updating P&L with profit."""
        config = {"risk": {}}
        rm = RiskManager(config)

        rm.update_daily_pnl(Decimal("50"))

        assert rm.daily_pnl == Decimal("50")

    def test_update_daily_pnl_negative(self):
        """Test updating P&L with loss."""
        config = {"risk": {}}
        rm = RiskManager(config)

        rm.update_daily_pnl(Decimal("-30"))

        assert rm.daily_pnl == Decimal("-30")

    def test_update_daily_pnl_accumulates(self):
        """Test P&L accumulates across multiple updates."""
        config = {"risk": {}}
        rm = RiskManager(config)

        rm.update_daily_pnl(Decimal("50"))
        rm.update_daily_pnl(Decimal("-30"))
        rm.update_daily_pnl(Decimal("20"))

        assert rm.daily_pnl == Decimal("40")


class TestResetDailyCounters:
    """Test daily counter reset."""

    def test_reset_daily_counters(self):
        """Test resetting daily counters."""
        config = {"risk": {}}
        rm = RiskManager(config)

        # Set some values
        rm.daily_trades = 25
        rm.daily_pnl = Decimal("150")
        rm.last_trade_time = datetime.utcnow()

        # Reset
        rm.reset_daily_counters()

        assert rm.daily_trades == 0
        assert rm.daily_pnl == Decimal("0")
        assert rm.last_trade_time is None
