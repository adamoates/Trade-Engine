"""
Tests for structured logging configuration.

Validates logging behavior, JSON formatting, and trading event logging.
"""

import json
import tempfile
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from trade_engine.core.logging_config import (
    configure_logging,
    get_logger,
    TradingLogger,
    DecimalEncoder,
    decimal_processor
)


class TestDecimalHandling:
    """Test that Decimal types are handled correctly (NON-NEGOTIABLE)."""

    def test_decimal_encoder_converts_to_string(self):
        """Test DecimalEncoder converts Decimal to string."""
        data = {
            "price": Decimal("45000.50"),
            "size": Decimal("0.1"),
            "nested": {"pnl": Decimal("90.25")}
        }

        # Should not raise TypeError
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)

        # Verify values are strings (preserves precision)
        assert parsed["price"] == "45000.50"
        assert parsed["size"] == "0.1"
        assert parsed["nested"]["pnl"] == "90.25"

    def test_decimal_processor_converts_event_dict(self):
        """Test decimal_processor converts Decimals in event dict."""
        event_dict = {
            "message": "order_placed",
            "price": Decimal("45000.50"),
            "size": Decimal("0.1"),
            "count": 5  # Non-Decimal should pass through
        }

        result = decimal_processor(None, None, event_dict)

        assert result["price"] == "45000.50"
        assert result["size"] == "0.1"
        assert result["count"] == 5

    def test_decimal_preserves_precision(self):
        """CRITICAL: Document why Decimal is required for financial values."""
        # This test documents the requirement per CLAUDE.md

        # Decimal preserves exact precision
        price_decimal = Decimal("45000.50")
        assert str(price_decimal) == "45000.50"

        # Decimal arithmetic is exact
        result = Decimal("0.1") + Decimal("0.2")
        assert result == Decimal("0.3")  # Exact!

        # Float arithmetic has rounding errors
        result_float = 0.1 + 0.2
        assert result_float != 0.3  # 0.30000000000000004

        # This is why NON-NEGOTIABLE: all financial values must use Decimal


class TestLoggingConfiguration:
    """Test logging configuration options."""

    def setup_method(self):
        """Reset logger before each test to avoid pollution."""
        from loguru import logger
        logger.remove()

    def test_configure_logging_creates_log_dir(self):
        """Test that configure_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            configure_logging(
                level="INFO",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True
            )

            assert log_dir.exists()
            assert log_dir.is_dir()

    def test_configure_logging_respects_level(self):
        """Test that log level is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            configure_logging(
                level="ERROR",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True
            )

            logger = get_logger(__name__)

            # DEBUG and INFO should not appear
            # ERROR should appear
            # (We can't easily test this without parsing logs, so this is a smoke test)
            logger.debug("debug message")
            logger.info("info message")
            logger.error("error message")

    def test_get_logger_returns_bound_logger(self):
        """Test get_logger returns logger with module binding."""
        logger = get_logger("test_module")

        # Should not raise
        logger.info("test message")

    def test_configure_logging_creates_nested_log_dir(self):
        """Test that configure_logging creates nested log directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "nested" / "logs" / "deep"

            configure_logging(
                level="INFO",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True
            )

            assert log_dir.exists()
            assert log_dir.is_dir()

    def test_configure_logging_raises_on_permission_error(self):
        """Test that configure_logging raises PermissionError with clear message."""
        import stat

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory with no write permissions
            parent_dir = Path(tmpdir) / "readonly"
            parent_dir.mkdir()
            parent_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # Read + execute only

            log_dir = parent_dir / "logs"

            try:
                with pytest.raises(PermissionError, match="Failed to create log directory"):
                    configure_logging(
                        level="INFO",
                        log_dir=log_dir,
                        enable_console=False,
                        enable_file=True
                    )
            finally:
                # Restore permissions for cleanup
                parent_dir.chmod(stat.S_IRWXU)


class TestTradingLogger:
    """Test TradingLogger for standardized trading events."""

    def test_trading_logger_with_strategy_id(self):
        """Test TradingLogger includes strategy_id in context."""
        logger = TradingLogger(strategy_id="test_strategy")

        assert logger.strategy_id == "test_strategy"

    def test_order_placed_logs_correctly(self):
        """Test order_placed logs all required fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger(strategy_id="test")

            trade_logger.order_placed(
                symbol="BTC/USDT",
                side="BUY",
                size=Decimal("0.1"),
                price=Decimal("45000.00"),
                order_type="LIMIT",
                order_id="order_123"
            )

            # Verify logger.info was called
            mock_logger.info.assert_called_once()
            args = mock_logger.info.call_args

            # Check message
            assert args[0][0] == "order_placed"

            # Check context
            context = args[1]
            assert context["event"] == "order_placed"
            assert context["symbol"] == "BTC/USDT"
            assert context["side"] == "BUY"
            assert context["size"] == "0.1"  # Converted to string
            assert context["price"] == "45000.00"
            assert context["order_type"] == "LIMIT"
            assert context["order_id"] == "order_123"
            assert context["strategy_id"] == "test"

    def test_order_filled_logs_correctly(self):
        """Test order_filled logs all required fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.order_filled(
                symbol="BTC/USDT",
                side="BUY",
                size=Decimal("0.1"),
                fill_price=Decimal("45000.00"),
                order_id="order_123",
                commission=Decimal("4.50")
            )

            mock_logger.info.assert_called_once()
            context = mock_logger.info.call_args[1]

            assert context["event"] == "order_filled"
            assert context["fill_price"] == "45000.00"
            assert context["commission"] == "4.50"

    def test_order_cancelled_logs_correctly(self):
        """Test order_cancelled logs all required fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.order_cancelled(
                symbol="BTC/USDT",
                side="BUY",
                order_id="order_123",
                reason="User requested cancellation"
            )

            mock_logger.info.assert_called_once()
            context = mock_logger.info.call_args[1]

            assert context["event"] == "order_cancelled"
            assert context["symbol"] == "BTC/USDT"
            assert context["side"] == "BUY"
            assert context["order_id"] == "order_123"
            assert context["reason"] == "User requested cancellation"

    def test_position_opened_logs_correctly(self):
        """Test position_opened logs all required fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.position_opened(
                symbol="BTC/USDT",
                side="LONG",
                size=Decimal("0.1"),
                entry_price=Decimal("45000.00"),
                position_id="pos_456"
            )

            mock_logger.info.assert_called_once()
            context = mock_logger.info.call_args[1]

            assert context["event"] == "position_opened"
            assert context["entry_price"] == "45000.00"
            assert context["position_id"] == "pos_456"

    def test_position_closed_logs_correctly(self):
        """Test position_closed logs all required fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.position_closed(
                symbol="BTC/USDT",
                side="LONG",
                size=Decimal("0.1"),
                entry_price=Decimal("45000.00"),
                exit_price=Decimal("45900.00"),
                pnl=Decimal("90.00"),
                position_id="pos_456"
            )

            mock_logger.info.assert_called_once()
            context = mock_logger.info.call_args[1]

            assert context["event"] == "position_closed"
            assert context["pnl"] == "90.00"
            assert context["entry_price"] == "45000.00"
            assert context["exit_price"] == "45900.00"

    def test_risk_limit_breached_logs_warning(self):
        """Test risk_limit_breached logs as WARNING."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.risk_limit_breached(
                limit_type="daily_loss",
                current_value=Decimal("-520"),
                limit_value=Decimal("-500"),
                action="KILL_SWITCH_TRIGGERED"
            )

            mock_logger.warning.assert_called_once()
            context = mock_logger.warning.call_args[1]

            assert context["event"] == "risk_limit_breached"
            assert context["limit_type"] == "daily_loss"
            assert context["current_value"] == "-520"
            assert context["limit_value"] == "-500"

    def test_kill_switch_triggered_logs_critical(self):
        """Test kill_switch_triggered logs as CRITICAL."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.kill_switch_triggered(
                reason="Daily loss limit breached",
                metric_value=Decimal("-520"),
                limit_value=Decimal("-500")
            )

            mock_logger.critical.assert_called_once()
            context = mock_logger.critical.call_args[1]

            assert context["event"] == "kill_switch_triggered"
            assert context["reason"] == "Daily loss limit breached"
            assert context["metric_value"] == "-520"

    def test_pnl_update_logs_correctly(self):
        """Test pnl_update logs all PnL fields."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.pnl_update(
                symbol="BTC/USDT",
                realized_pnl=Decimal("90.00"),
                unrealized_pnl=Decimal("15.00"),
                total_pnl=Decimal("105.00")
            )

            mock_logger.info.assert_called_once()
            context = mock_logger.info.call_args[1]

            assert context["event"] == "pnl_update"
            assert context["realized_pnl"] == "90.00"
            assert context["unrealized_pnl"] == "15.00"
            assert context["total_pnl"] == "105.00"

    def test_custom_kwargs_are_included(self):
        """Test that custom kwargs are included in log context."""
        with patch('trade_engine.core.logging_config.logger') as mock_logger:
            trade_logger = TradingLogger()

            trade_logger.order_placed(
                symbol="BTC/USDT",
                side="BUY",
                size=Decimal("0.1"),
                custom_field="custom_value",
                latency_ms=15
            )

            context = mock_logger.info.call_args[1]
            assert context["custom_field"] == "custom_value"
            assert context["latency_ms"] == 15


class TestLogRotation:
    """Test log rotation and retention."""

    def test_log_files_created(self):
        """Test that log files are created with correct names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            configure_logging(
                level="INFO",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True
            )

            logger = get_logger(__name__)
            logger.info("test message")

            # Check files exist
            log_files = list(log_dir.glob("*.log"))
            assert len(log_files) > 0

            # Should have trade_engine, trades, and errors logs
            file_names = [f.stem.split('_')[0] for f in log_files]
            assert "trade" in ' '.join(file_names) or "trades" in ' '.join(file_names)


class TestJSONFormatting:
    """Test JSON log formatting."""

    def test_logs_are_valid_json(self):
        """Test that logs can be parsed as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            configure_logging(
                level="INFO",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True,
                serialize=True  # JSON format
            )

            logger = get_logger(__name__)
            logger.info("test_event", symbol="BTC/USDT", price=Decimal("45000.00"))

            # Read and parse log
            log_files = list(log_dir.glob("trade_engine_*.log"))
            assert len(log_files) > 0

            with open(log_files[0]) as f:
                for line in f:
                    if line.strip():
                        # Should not raise JSONDecodeError
                        data = json.loads(line)
                        assert "text" in data or "record" in data


class TestAuditTrail:
    """Test audit trail functionality."""

    def test_trading_logs_separated(self):
        """Test that trading logs are separated into trades_*.log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            configure_logging(
                level="INFO",
                log_dir=log_dir,
                enable_console=False,
                enable_file=True
            )

            trade_logger = TradingLogger()

            # Log trading event
            trade_logger.order_placed(
                symbol="BTC/USDT",
                side="BUY",
                size=Decimal("0.1")
            )

            # Should have trades log file
            trade_logs = list(log_dir.glob("trades_*.log"))
            assert len(trade_logs) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
