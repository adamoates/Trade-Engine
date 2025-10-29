"""
Unit tests for PositionDatabase - Persistent entry price tracking.

Tests cover:
- Position opening with entry price tracking
- Position closing with P&L calculation
- Unrealized P&L calculation
- Daily P&L tracking
- Statistics aggregation
- Error handling
"""

import pytest
import tempfile
import os
from decimal import Decimal
from pathlib import Path

from trade_engine.core.position_database import PositionDatabase, PositionDatabaseError


class TestPositionDatabaseInit:
    """Test database initialization."""

    def test_init_creates_database(self):
        """Test that initialization creates database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            assert Path(db_path).exists()
            assert db.db_path == db_path

    def test_init_creates_schema(self):
        """Test that initialization creates all tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Verify tables exist by querying them
            assert db.get_open_positions() == {}
            assert db.get_daily_pnl() == Decimal("0")
            stats = db.get_statistics(days=30)
            assert stats["total_trades"] == 0


class TestOpenPosition:
    """Test opening positions."""

    def test_open_position_success(self):
        """Test successful position opening."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            position_id = db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            assert position_id > 0

            # Verify position was stored
            positions = db.get_open_positions()
            assert "BTCUSDT" in positions
            assert positions["BTCUSDT"]["entry_price"] == Decimal("50000.00")
            assert positions["BTCUSDT"]["qty"] == Decimal("0.1")
            assert positions["BTCUSDT"]["side"] == "long"

    def test_open_position_rejects_float(self):
        """Test that float values are rejected (must use Decimal)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # entry_price as float should fail
            with pytest.raises(PositionDatabaseError, match="entry_price must be Decimal"):
                db.open_position(
                    symbol="BTCUSDT",
                    side="long",
                    entry_price=50000.00,  # float (bad!)
                    qty=Decimal("0.1"),
                    broker="test_broker"
                )

            # qty as float should fail
            with pytest.raises(PositionDatabaseError, match="qty must be Decimal"):
                db.open_position(
                    symbol="BTCUSDT",
                    side="long",
                    entry_price=Decimal("50000.00"),
                    qty=0.1,  # float (bad!)
                    broker="test_broker"
                )

    def test_open_position_rejects_invalid_side(self):
        """Test that invalid sides are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            with pytest.raises(PositionDatabaseError, match="side must be 'long' or 'short'"):
                db.open_position(
                    symbol="BTCUSDT",
                    side="invalid",
                    entry_price=Decimal("50000.00"),
                    qty=Decimal("0.1"),
                    broker="test_broker"
                )

    def test_open_position_prevents_duplicates(self):
        """Test that duplicate positions are prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # First position should succeed
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            # Duplicate should fail
            with pytest.raises(PositionDatabaseError, match="Position already open"):
                db.open_position(
                    symbol="BTCUSDT",
                    side="long",
                    entry_price=Decimal("51000.00"),
                    qty=Decimal("0.2"),
                    broker="test_broker"
                )


class TestClosePosition:
    """Test closing positions and P&L calculation."""

    def test_close_position_long_profit(self):
        """Test closing long position with profit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Open position
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            # Close position with profit
            trade = db.close_position(
                symbol="BTCUSDT",
                exit_price=Decimal("51000.00"),
                exit_reason="take_profit",
                broker="test_broker"
            )

            # Verify P&L calculation
            expected_pnl = (Decimal("51000.00") - Decimal("50000.00")) * Decimal("0.1")
            assert trade["pnl"] == expected_pnl  # $100
            assert trade["pnl_pct"] == Decimal("2.0")  # 2%
            assert trade["exit_reason"] == "take_profit"

            # Verify position was removed
            positions = db.get_open_positions()
            assert "BTCUSDT" not in positions

    def test_close_position_long_loss(self):
        """Test closing long position with loss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Open position
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            # Close position with loss
            trade = db.close_position(
                symbol="BTCUSDT",
                exit_price=Decimal("49000.00"),
                exit_reason="stop_loss",
                broker="test_broker"
            )

            # Verify P&L calculation
            expected_pnl = (Decimal("49000.00") - Decimal("50000.00")) * Decimal("0.1")
            assert trade["pnl"] == expected_pnl  # -$100
            assert trade["pnl_pct"] == Decimal("-2.0")  # -2%

    def test_close_position_short_profit(self):
        """Test closing short position with profit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Open short position
            db.open_position(
                symbol="BTCUSDT",
                side="short",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            # Close position with profit (price went down)
            trade = db.close_position(
                symbol="BTCUSDT",
                exit_price=Decimal("49000.00"),
                exit_reason="take_profit",
                broker="test_broker"
            )

            # Verify P&L calculation (profit on short = entry - exit)
            expected_pnl = (Decimal("50000.00") - Decimal("49000.00")) * Decimal("0.1")
            assert trade["pnl"] == expected_pnl  # $100
            assert trade["pnl_pct"] == Decimal("2.0")  # 2%

    def test_close_position_not_found(self):
        """Test closing non-existent position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            with pytest.raises(PositionDatabaseError, match="No open position found"):
                db.close_position(
                    symbol="BTCUSDT",
                    exit_price=Decimal("50000.00"),
                    exit_reason="manual",
                    broker="test_broker"
                )


class TestGetPosition:
    """Test retrieving specific position."""

    def test_get_position_exists(self):
        """Test retrieving existing position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            position = db.get_position("BTCUSDT", broker="test_broker")

            assert position is not None
            assert position["side"] == "long"
            assert position["entry_price"] == Decimal("50000.00")
            assert position["qty"] == Decimal("0.1")
            assert "duration_seconds" in position

    def test_get_position_not_found(self):
        """Test retrieving non-existent position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            position = db.get_position("BTCUSDT", broker="test_broker")
            assert position is None


class TestUnrealizedPnL:
    """Test unrealized P&L calculation."""

    def test_calculate_unrealized_pnl_long_profit(self):
        """Test unrealized P&L for long position in profit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            pnl, pnl_pct = db.calculate_unrealized_pnl(
                symbol="BTCUSDT",
                current_price=Decimal("51000.00"),
                broker="test_broker"
            )

            assert pnl == Decimal("100.0")  # $100 profit
            assert pnl_pct == Decimal("2.0")  # 2% gain

    def test_calculate_unrealized_pnl_short_loss(self):
        """Test unrealized P&L for short position in loss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            db.open_position(
                symbol="BTCUSDT",
                side="short",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )

            pnl, pnl_pct = db.calculate_unrealized_pnl(
                symbol="BTCUSDT",
                current_price=Decimal("51000.00"),  # Price went up (bad for short)
                broker="test_broker"
            )

            assert pnl == Decimal("-100.0")  # $100 loss
            assert pnl_pct == Decimal("-2.0")  # -2% loss

    def test_calculate_unrealized_pnl_no_position(self):
        """Test unrealized P&L when position doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            with pytest.raises(PositionDatabaseError, match="No open position"):
                db.calculate_unrealized_pnl(
                    symbol="BTCUSDT",
                    current_price=Decimal("50000.00"),
                    broker="test_broker"
                )


class TestDailyPnL:
    """Test daily P&L tracking."""

    def test_get_daily_pnl_no_trades(self):
        """Test daily P&L when no trades today."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            daily_pnl = db.get_daily_pnl()
            assert daily_pnl == Decimal("0")

    def test_get_daily_pnl_with_trades(self):
        """Test daily P&L calculation with multiple trades."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Trade 1: +$100
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )
            db.close_position(
                symbol="BTCUSDT",
                exit_price=Decimal("51000.00"),
                exit_reason="take_profit",
                broker="test_broker"
            )

            # Trade 2: -$50
            db.open_position(
                symbol="ETHUSDT",
                side="long",
                entry_price=Decimal("3000.00"),
                qty=Decimal("1.0"),
                broker="test_broker"
            )
            db.close_position(
                symbol="ETHUSDT",
                exit_price=Decimal("2950.00"),
                exit_reason="stop_loss",
                broker="test_broker"
            )

            daily_pnl = db.get_daily_pnl()
            assert daily_pnl == Decimal("50.0")  # $100 - $50


class TestStatistics:
    """Test statistics calculation."""

    def test_get_statistics_no_trades(self):
        """Test statistics when no trades."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            stats = db.get_statistics(days=30)

            assert stats["total_trades"] == 0
            assert stats["winning_trades"] == 0
            assert stats["losing_trades"] == 0
            assert stats["win_rate"] == 0.0
            assert stats["total_pnl"] == Decimal("0")
            assert stats["profit_factor"] == 0.0

    def test_get_statistics_with_trades(self):
        """Test statistics calculation with trades."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Trade 1: Win (+$100)
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )
            db.close_position(
                symbol="BTCUSDT",
                exit_price=Decimal("51000.00"),
                exit_reason="take_profit",
                broker="test_broker"
            )

            # Trade 2: Loss (-$50)
            db.open_position(
                symbol="ETHUSDT",
                side="long",
                entry_price=Decimal("3000.00"),
                qty=Decimal("1.0"),
                broker="test_broker"
            )
            db.close_position(
                symbol="ETHUSDT",
                exit_price=Decimal("2950.00"),
                exit_reason="stop_loss",
                broker="test_broker"
            )

            # Trade 3: Win (+$200)
            db.open_position(
                symbol="SOLUSDT",
                side="long",
                entry_price=Decimal("100.00"),
                qty=Decimal("10.0"),
                broker="test_broker"
            )
            db.close_position(
                symbol="SOLUSDT",
                exit_price=Decimal("120.00"),
                exit_reason="take_profit",
                broker="test_broker"
            )

            stats = db.get_statistics(days=30)

            assert stats["total_trades"] == 3
            assert stats["winning_trades"] == 2
            assert stats["losing_trades"] == 1
            assert stats["win_rate"] == 66.67  # 2/3 * 100
            assert stats["total_pnl"] == Decimal("250.0")  # $100 - $50 + $200
            assert stats["avg_pnl"] == Decimal("83.33333333333333333333333333")  # $250 / 3
            assert stats["profit_factor"] == 6.0  # $300 wins / $50 losses


class TestClearAllPositions:
    """Test clearing all positions."""

    def test_clear_all_positions(self):
        """Test clearing all positions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Open multiple positions
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="test_broker"
            )
            db.open_position(
                symbol="ETHUSDT",
                side="long",
                entry_price=Decimal("3000.00"),
                qty=Decimal("1.0"),
                broker="test_broker"
            )

            # Verify positions exist
            positions = db.get_open_positions()
            assert len(positions) == 2

            # Clear all
            db.clear_all_positions()

            # Verify all cleared
            positions = db.get_open_positions()
            assert len(positions) == 0


class TestMultiBrokerSupport:
    """Test multi-broker position tracking."""

    def test_different_brokers_same_symbol(self):
        """Test tracking same symbol on different brokers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_positions.db")
            db = PositionDatabase(db_path=db_path)

            # Open position on broker 1
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50000.00"),
                qty=Decimal("0.1"),
                broker="binance_us"
            )

            # Open same symbol on broker 2
            db.open_position(
                symbol="BTCUSDT",
                side="long",
                entry_price=Decimal("50100.00"),
                qty=Decimal("0.2"),
                broker="kraken"
            )

            # Verify both positions exist
            all_positions = db.get_open_positions()
            assert len(all_positions) == 2

            # Filter by broker
            binance_positions = db.get_open_positions(broker="binance_us")
            assert len(binance_positions) == 1
            assert binance_positions["BTCUSDT"]["entry_price"] == Decimal("50000.00")

            kraken_positions = db.get_open_positions(broker="kraken")
            assert len(kraken_positions) == 1
            assert kraken_positions["BTCUSDT"]["entry_price"] == Decimal("50100.00")
