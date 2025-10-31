"""
Comprehensive test suite for log import script.

Tests all critical functionality:
- Audit log parsing
- Trade log parsing
- Decimal conversion safety
- Error handling and recovery
- Database interactions
"""

import json
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from import_logs_to_db import LogImporter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_database():
    """Mock PostgresDatabase for testing without real DB."""
    with patch("import_logs_to_db.PostgresDatabase") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        yield mock_db


@pytest.fixture
def importer(mock_database):
    """Create LogImporter with mocked database."""
    return LogImporter(database_url="postgresql://test:test@localhost/test")


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# TEST DECIMAL CONVERSION (_safe_decimal)
# ============================================================================


class TestSafeDecimal:
    """Test _safe_decimal() method for financial precision."""

    def test_safe_decimal_with_none(self, importer):
        """Test that None converts to Decimal('0')."""
        result = importer._safe_decimal(None)
        assert result == Decimal("0")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_string(self, importer):
        """Test string conversion."""
        result = importer._safe_decimal("123.45")
        assert result == Decimal("123.45")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_integer(self, importer):
        """Test integer conversion."""
        result = importer._safe_decimal(100)
        assert result == Decimal("100")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_float(self, importer):
        """Test float conversion (via string to avoid precision loss)."""
        result = importer._safe_decimal(123.45)
        # Should convert via string, not direct float
        assert result == Decimal("123.45")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_decimal(self, importer):
        """Test Decimal passthrough."""
        decimal_value = Decimal("456.789")
        result = importer._safe_decimal(decimal_value)
        assert result == decimal_value
        assert result is decimal_value  # Should be same object

    def test_safe_decimal_with_negative(self, importer):
        """Test negative value conversion."""
        result = importer._safe_decimal("-99.99")
        assert result == Decimal("-99.99")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_zero(self, importer):
        """Test zero conversion."""
        result = importer._safe_decimal("0")
        assert result == Decimal("0")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_large_precision(self, importer):
        """Test high-precision value (8 decimal places for crypto)."""
        result = importer._safe_decimal("0.12345678")
        assert result == Decimal("0.12345678")
        assert isinstance(result, Decimal)

    def test_safe_decimal_with_scientific_notation(self, importer):
        """Test scientific notation conversion."""
        result = importer._safe_decimal("1.5e-5")
        assert result == Decimal("0.000015")
        assert isinstance(result, Decimal)

    def test_safe_decimal_invalid_string(self, importer):
        """Test that invalid string raises ValueError."""
        with pytest.raises((ValueError, Exception)):
            importer._safe_decimal("not_a_number")


# ============================================================================
# TEST TIMESTAMP PARSING
# ============================================================================


class TestTimestampParsing:
    """Test _parse_timestamp() method."""

    def test_parse_iso_timestamp_with_z(self, importer):
        """Test ISO timestamp with Z suffix."""
        ts_str = "2025-10-29T07:14:47.130863Z"
        result = importer._parse_timestamp(ts_str)

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 29
        assert result.hour == 7
        assert result.minute == 14
        assert result.second == 47

    def test_parse_iso_timestamp_with_timezone(self, importer):
        """Test ISO timestamp with explicit timezone."""
        ts_str = "2025-10-29T07:14:47+00:00"
        result = importer._parse_timestamp(ts_str)

        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_parse_empty_timestamp(self, importer):
        """Test empty timestamp returns current time."""
        result = importer._parse_timestamp("")

        assert isinstance(result, datetime)
        # Should be close to now
        assert (datetime.now(timezone.utc) - result).total_seconds() < 2

    def test_parse_none_timestamp(self, importer):
        """Test None timestamp returns current time."""
        result = importer._parse_timestamp(None)

        assert isinstance(result, datetime)
        assert (datetime.now(timezone.utc) - result).total_seconds() < 2

    def test_parse_invalid_timestamp(self, importer):
        """Test invalid timestamp falls back to current time."""
        result = importer._parse_timestamp("not-a-timestamp")

        assert isinstance(result, datetime)
        assert (datetime.now(timezone.utc) - result).total_seconds() < 2


# ============================================================================
# TEST AUDIT LOG IMPORT
# ============================================================================


class TestAuditLogImport:
    """Test import_audit_log() method."""

    def test_import_audit_log_signal_generated(self, importer, temp_log_dir, mock_database):
        """Test importing signal_generated event."""
        # Create test audit log
        log_file = temp_log_dir / "audit_test.jsonl"
        event = {
            "ts": "2025-10-29T07:14:47.130863Z",
            "event": "signal_generated",
            "signal": {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry_price": "50000.00",
                "confidence": "0.85"
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        # Import log
        count = importer.import_audit_log(log_file)

        assert count == 1
        assert importer.stats["audit_events"] == 1

    def test_import_audit_log_risk_block(self, importer, temp_log_dir, mock_database):
        """Test importing risk_block event."""
        log_file = temp_log_dir / "audit_test.jsonl"
        event = {
            "ts": "2025-10-29T07:14:47.130863Z",
            "event": "risk_block",
            "reason": "Daily loss limit exceeded",
            "signal": {"symbol": "BTCUSDT"}
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        count = importer.import_audit_log(log_file)

        assert count == 1
        assert importer.stats["risk_events"] == 1

        # Verify risk event was logged
        mock_database.log_risk_event.assert_called_once()
        call_args = mock_database.log_risk_event.call_args[1]
        # Risk blocks are mapped to 'position_limit' event type
        assert call_args["event_type"] == "position_limit"
        assert call_args["reason"] == "Daily loss limit exceeded"

    def test_import_audit_log_multiple_events(self, importer, temp_log_dir, mock_database):
        """Test importing multiple events from one file."""
        log_file = temp_log_dir / "audit_test.jsonl"

        events = [
            {"ts": "2025-10-29T07:14:47Z", "event": "signal_generated", "signal": {"symbol": "BTC"}},
            {"ts": "2025-10-29T07:15:47Z", "event": "risk_block", "reason": "Test", "signal": {"symbol": "ETH"}},
            {"ts": "2025-10-29T07:16:47Z", "event": "bar_received", "bar": {"symbol": "BTC"}},
        ]

        with open(log_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        count = importer.import_audit_log(log_file)

        assert count == 3
        # signal_generated + bar_received = 2 audit events
        # risk_block = 1 risk event (not counted in audit_events)
        assert importer.stats["audit_events"] == 2
        assert importer.stats["risk_events"] == 1

    def test_import_audit_log_malformed_line(self, importer, temp_log_dir, mock_database):
        """Test error handling for malformed JSON."""
        log_file = temp_log_dir / "audit_test.jsonl"

        with open(log_file, "w") as f:
            f.write('{"valid": "json"}\n')
            f.write('invalid json line\n')  # Malformed
            f.write('{"another": "valid"}\n')

        count = importer.import_audit_log(log_file)

        # Should import 2 valid lines, error on 1
        assert count == 2
        assert importer.stats["errors"] == 1

    def test_import_audit_log_empty_file(self, importer, temp_log_dir):
        """Test importing empty log file."""
        log_file = temp_log_dir / "audit_empty.jsonl"
        log_file.touch()

        count = importer.import_audit_log(log_file)

        assert count == 0


# ============================================================================
# TEST TRADE LOG IMPORT
# ============================================================================


class TestTradeLogImport:
    """Test import_trades_log() method."""

    def test_import_trade_log_order_filled(self, importer, temp_log_dir, mock_database):
        """Test importing order_filled event."""
        log_file = temp_log_dir / "trades_test.log"

        event = {
            "record": {
                "extra": {
                    "event": "order_filled",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "size": "0.01",
                    "fill_price": "50000.00",
                    "order_id": "12345",
                    "trade_id": "67890",
                    "commission": "5.00"
                },
                "time": {"repr": "2025-10-29 07:14:47.130863"}
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        count = importer.import_trades_log(log_file)

        assert count == 1
        assert importer.stats["trade_events"] == 1

        # Verify trade was logged with Decimal values
        mock_database.log_trade.assert_called_once()
        call_args = mock_database.log_trade.call_args[1]
        assert isinstance(call_args["price"], Decimal)
        assert isinstance(call_args["qty"], Decimal)
        assert call_args["symbol"] == "BTCUSDT"

    def test_import_trade_log_position_opened(self, importer, temp_log_dir, mock_database):
        """Test importing position_opened event."""
        log_file = temp_log_dir / "trades_test.log"

        event = {
            "record": {
                "extra": {
                    "event": "position_opened",
                    "symbol": "BTCUSDT",
                    "side": "LONG",
                    "size": "0.01",
                    "entry_price": "50000.00",
                    "broker": "binance"
                },
                "time": {"repr": "2025-10-29 07:14:47.130863"}
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        count = importer.import_trades_log(log_file)

        assert count == 1
        assert importer.stats["position_events"] == 1

        # Verify position was opened
        mock_database.open_position.assert_called_once()

    def test_import_trade_log_position_closed(self, importer, temp_log_dir, mock_database):
        """Test importing position_closed event."""
        log_file = temp_log_dir / "trades_test.log"

        event = {
            "record": {
                "extra": {
                    "event": "position_closed",
                    "symbol": "BTCUSDT",
                    "exit_price": "51000.00",
                    "exit_reason": "take_profit",
                    "broker": "binance"
                },
                "time": {"repr": "2025-10-29 07:14:47.130863"}
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        count = importer.import_trades_log(log_file)

        assert count == 1
        assert importer.stats["position_events"] == 1

        # Verify position was closed
        mock_database.close_position.assert_called_once()

    def test_import_trade_log_position_not_found(self, importer, temp_log_dir, mock_database):
        """Test graceful handling when position doesn't exist."""
        # Mock close_position to raise "not found" error
        mock_database.close_position.side_effect = Exception("No open position found")

        log_file = temp_log_dir / "trades_test.log"
        event = {
            "record": {
                "extra": {
                    "event": "position_closed",
                    "symbol": "BTCUSDT",
                    "exit_price": "51000.00"
                },
                "time": {"repr": "2025-10-29 07:14:47"}
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        # Should not raise, should handle gracefully
        count = importer.import_trades_log(log_file)

        assert count == 1
        # Should not increment error count for "not found" (expected condition)
        assert importer.stats["errors"] == 0

    def test_import_trade_log_duplicate_trade_id(self, importer, temp_log_dir, mock_database):
        """Test handling of duplicate trade_id (database constraint)."""
        # Mock log_trade to raise duplicate error
        mock_database.log_trade.side_effect = Exception("duplicate key value violates unique constraint")

        log_file = temp_log_dir / "trades_test.log"
        event = {
            "record": {
                "extra": {
                    "event": "order_filled",
                    "symbol": "BTCUSDT",
                    "trade_id": "12345"
                },
                "time": {"repr": "2025-10-29 07:14:47"}
            }
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        count = importer.import_trades_log(log_file)

        # Should process the line but log_trade will fail
        assert count == 1
        # Exception in _log_trade_from_event increments error count
        assert importer.stats["errors"] == 1


# ============================================================================
# TEST DIRECTORY IMPORT
# ============================================================================


class TestDirectoryImport:
    """Test import_directory() method."""

    def test_import_directory_mixed_logs(self, importer, temp_log_dir, mock_database):
        """Test importing all log types from directory."""
        # Create multiple log files
        (temp_log_dir / "audit_2025-10-29.jsonl").write_text(
            '{"ts": "2025-10-29T07:14:47Z", "event": "signal_generated"}\n'
        )
        (temp_log_dir / "trades_2025-10-29.log").write_text(
            '{"record": {"extra": {"event": "order_filled"}, "time": {"repr": "2025-10-29 07:14:47"}}}\n'
        )
        (temp_log_dir / "trade_engine_2025-10-29.log").write_text(
            '{"record": {"extra": {"event": "position_opened"}, "time": {"repr": "2025-10-29 07:14:47"}}}\n'
        )

        importer.import_directory(temp_log_dir)

        # Should have imported from all files
        assert importer.stats["audit_events"] > 0
        assert importer.stats["trade_events"] > 0

    def test_import_directory_no_logs(self, importer, temp_log_dir):
        """Test importing from empty directory."""
        # Should not raise error
        importer.import_directory(temp_log_dir)

        assert importer.stats["audit_events"] == 0
        assert importer.stats["trade_events"] == 0

    def test_import_directory_error_recovery(self, importer, temp_log_dir, mock_database):
        """Test that errors in one file don't stop processing others."""
        # Create valid audit log
        (temp_log_dir / "audit_good.jsonl").write_text(
            '{"ts": "2025-10-29T07:14:47Z", "event": "signal_generated"}\n'
        )

        # Create corrupted trade log
        (temp_log_dir / "trades_bad.log").write_text("not valid json at all")

        # Should process good file, error on bad file
        importer.import_directory(temp_log_dir)

        # Good file should be imported
        assert importer.stats["audit_events"] == 1
        # Bad file should log error
        assert importer.stats["errors"] == 1


# ============================================================================
# TEST STATISTICS
# ============================================================================


class TestStatistics:
    """Test statistics tracking."""

    def test_stats_initialization(self, importer):
        """Test that stats are initialized correctly."""
        assert importer.stats["audit_events"] == 0
        assert importer.stats["trade_events"] == 0
        assert importer.stats["position_events"] == 0
        assert importer.stats["risk_events"] == 0
        assert importer.stats["errors"] == 0

    def test_stats_increment_on_events(self, importer, temp_log_dir, mock_database):
        """Test that stats increment correctly."""
        # Import audit event
        audit_log = temp_log_dir / "audit.jsonl"
        audit_log.write_text('{"ts": "2025-10-29T07:14:47Z", "event": "signal_generated"}\n')
        importer.import_audit_log(audit_log)

        assert importer.stats["audit_events"] == 1

        # Import trade event
        trade_log = temp_log_dir / "trades.log"
        trade_log.write_text(
            '{"record": {"extra": {"event": "order_filled"}, "time": {"repr": "2025-10-29 07:14:47"}}}\n'
        )
        importer.import_trades_log(trade_log)

        assert importer.stats["trade_events"] == 1

    def test_print_stats(self, importer, capsys):
        """Test print_stats() outputs correctly."""
        importer.stats["audit_events"] = 10
        importer.stats["trade_events"] = 5
        importer.stats["errors"] = 2

        importer.print_stats()

        # Loguru outputs to stderr, so we can't easily capture it
        # This test mainly ensures print_stats doesn't crash
        assert True  # If we got here, print_stats didn't raise


# ============================================================================
# TEST INTEGRATION (END-TO-END)
# ============================================================================


class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_import_workflow(self, importer, temp_log_dir, mock_database):
        """Test complete import workflow with mixed events."""
        # Create realistic audit log
        audit_log = temp_log_dir / "audit_2025-10-29.jsonl"
        with open(audit_log, "w") as f:
            # Signal generation
            f.write(json.dumps({
                "ts": "2025-10-29T07:14:47Z",
                "event": "signal_generated",
                "signal": {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "entry_price": "50000.00",
                    "confidence": "0.85"
                }
            }) + "\n")

            # Risk block
            f.write(json.dumps({
                "ts": "2025-10-29T07:15:47Z",
                "event": "risk_block",
                "reason": "Position size exceeded",
                "signal": {"symbol": "ETHUSDT"}
            }) + "\n")

        # Create realistic trade log
        trade_log = temp_log_dir / "trades_2025-10-29.log"
        with open(trade_log, "w") as f:
            # Order filled
            f.write(json.dumps({
                "record": {
                    "extra": {
                        "event": "order_filled",
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "size": "0.01",
                        "fill_price": "50000.00",
                        "trade_id": "12345"
                    },
                    "time": {"repr": "2025-10-29 07:16:00"}
                }
            }) + "\n")

            # Position opened
            f.write(json.dumps({
                "record": {
                    "extra": {
                        "event": "position_opened",
                        "symbol": "BTCUSDT",
                        "size": "0.01",
                        "entry_price": "50000.00"
                    },
                    "time": {"repr": "2025-10-29 07:16:01"}
                }
            }) + "\n")

            # Position closed
            f.write(json.dumps({
                "record": {
                    "extra": {
                        "event": "position_closed",
                        "symbol": "BTCUSDT",
                        "exit_price": "51000.00",
                        "exit_reason": "take_profit"
                    },
                    "time": {"repr": "2025-10-29 07:17:00"}
                }
            }) + "\n")

        # Import directory
        importer.import_directory(temp_log_dir)

        # Verify statistics
        # signal_generated = 1 audit event (risk_block is separate)
        assert importer.stats["audit_events"] == 1
        assert importer.stats["trade_events"] == 1
        assert importer.stats["position_events"] == 2
        assert importer.stats["risk_events"] == 1
        assert importer.stats["errors"] == 0

        # Verify database calls
        assert mock_database.log_trade.call_count == 1
        assert mock_database.open_position.call_count == 1
        assert mock_database.close_position.call_count == 1
        assert mock_database.log_risk_event.call_count == 1

    def test_decimal_precision_preserved(self, importer, temp_log_dir, mock_database):
        """Test that Decimal precision is maintained through import."""
        trade_log = temp_log_dir / "trades.log"
        trade_log.write_text(json.dumps({
            "record": {
                "extra": {
                    "event": "order_filled",
                    "symbol": "BTCUSDT",
                    "size": "0.12345678",  # 8 decimal places
                    "fill_price": "50123.45",
                    "commission": "6.26"
                },
                "time": {"repr": "2025-10-29 07:14:47"}
            }
        }) + "\n")

        importer.import_trades_log(trade_log)

        # Verify Decimal was used
        call_args = mock_database.log_trade.call_args[1]
        assert isinstance(call_args["qty"], Decimal)
        assert isinstance(call_args["price"], Decimal)
        assert call_args["qty"] == Decimal("0.12345678")
        assert call_args["price"] == Decimal("50123.45")
