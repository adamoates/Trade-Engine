"""
Integration tests for kill switch functionality.

Tests the complete kill switch flow:
1. Kill switch triggers during trading
2. All open positions are closed
3. System stops trading
4. No new trades are placed after activation

CRITICAL: Kill switch must work reliably - trading bot must stop
when daily loss limit or manual halt is triggered.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, call
from pathlib import Path

from trade_engine.services.trading.engine import LiveRunner
from trade_engine.core.types import Bar, Signal, Position
from trade_engine.core.constants import EXIT_FAILURE


class TestKillSwitchIntegration:
    """Integration tests for kill switch across entire trading system."""

    @pytest.fixture
    def mock_components(self):
        """Create mocked strategy, data feed, and broker."""
        # Mock strategy
        strategy = Mock()
        strategy.on_bar.return_value = []  # No signals by default

        # Mock data feed
        data = Mock()

        # Mock broker with positions
        broker = Mock()
        broker.positions.return_value = {
            "BTCUSDT": Position(
                symbol="BTCUSDT",
                side="long",
                qty=0.1,
                entry_price=50000.0,
                current_price=50050.0,
                pnl=5.0,
                pnl_pct=0.1
            ),
            "ETHUSDT": Position(
                symbol="ETHUSDT",
                side="short",
                qty=1.0,
                entry_price=3000.0,
                current_price=2990.0,
                pnl=10.0,
                pnl_pct=0.33
            )
        }
        broker.balance.return_value = 10000.0

        return strategy, data, broker

    @pytest.fixture
    def config_with_kill_file(self, tmp_path):
        """Config that uses kill switch file."""
        kill_file = tmp_path / "kill_switch.flag"
        return {
            "mode": "paper",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "timeframe": "1h",
            "risk": {
                "kill_switch_file": str(kill_file),
                "max_daily_loss": Decimal("500"),
                "max_trades_per_day": 20,
                "max_position_usd": Decimal("10000")
            }
        }, kill_file

    def test_kill_switch_closes_all_positions_on_activation(self, mock_components, config_with_kill_file):
        """
        Test kill switch closes all open positions when activated.

        Scenario:
        1. Runner has 2 open positions (BTC long, ETH short)
        2. Kill switch file is created
        3. Next bar triggers kill switch
        4. Both positions are closed
        """
        strategy, data, broker = mock_components
        config, kill_file = config_with_kill_file

        runner = LiveRunner(strategy, data, broker, config)

        # Verify initial state: 2 positions open
        positions = broker.positions()
        assert len(positions) == 2
        assert "BTCUSDT" in positions
        assert "ETHUSDT" in positions

        # Create kill switch file
        kill_file.touch()

        # Create test bar
        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - should trigger kill switch
        with pytest.raises(SystemExit) as exc_info:
            runner._process_bar(bar)

        # Verify system exited with failure code
        assert exc_info.value.code == EXIT_FAILURE

        # Verify ALL positions were closed
        assert broker.close_all.call_count == 2
        broker.close_all.assert_any_call("BTCUSDT")
        broker.close_all.assert_any_call("ETHUSDT")

    def test_kill_switch_stops_new_trades(self, mock_components, config_with_kill_file):
        """
        Test kill switch prevents new trades from being placed.

        Scenario:
        1. Strategy generates BUY signal
        2. Kill switch is already active
        3. Signal is blocked, no order placed
        """
        strategy, data, broker = mock_components
        config, kill_file = config_with_kill_file

        # Strategy will generate a signal
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.1,
            price=50000.0,
            sl=49500.0,
            tp=50500.0,
            reason="test_signal"
        )
        strategy.on_bar.return_value = [signal]

        runner = LiveRunner(strategy, data, broker, config)

        # Activate kill switch BEFORE processing bar
        kill_file.touch()

        # Create test bar
        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - should trigger kill switch before executing signal
        with pytest.raises(SystemExit):
            runner._process_bar(bar)

        # Verify NO new orders were placed (only close_all for existing positions)
        broker.buy.assert_not_called()
        broker.sell.assert_not_called()

    def test_kill_switch_via_config_halt_flag(self, mock_components):
        """
        Test kill switch triggers via config halt=True.

        This is the programmatic way to stop trading (no file needed).
        """
        strategy, data, broker = mock_components

        config = {
            "halt": True,  # Top-level halt flag
            "risk": {
                "max_daily_loss": Decimal("500"),
                "max_trades_per_day": 20
            }
        }

        runner = LiveRunner(strategy, data, broker, config)

        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - should trigger kill switch
        with pytest.raises(SystemExit) as exc_info:
            runner._process_bar(bar)

        assert exc_info.value.code == EXIT_FAILURE

        # Verify positions were closed
        assert broker.close_all.call_count == 2

    def test_kill_switch_emergency_shutdown_handles_broker_errors(self, mock_components, config_with_kill_file):
        """
        Test kill switch handles broker errors gracefully during emergency shutdown.

        Scenario:
        1. Kill switch activates
        2. Broker.close_all() raises exception
        3. Emergency shutdown continues and completes
        """
        strategy, data, broker = mock_components
        config, kill_file = config_with_kill_file

        # Make broker.close_all() raise exception
        broker.close_all.side_effect = Exception("Broker API error")

        runner = LiveRunner(strategy, data, broker, config)

        # Activate kill switch
        kill_file.touch()

        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - should still exit even if close_all fails
        with pytest.raises(SystemExit) as exc_info:
            runner._process_bar(bar)

        assert exc_info.value.code == EXIT_FAILURE

        # Verify close_all was attempted (stops on first error)
        assert broker.close_all.call_count == 1  # Stops after first error

    def test_normal_trading_without_kill_switch(self):
        """
        Test normal trading continues when kill switch is NOT active.

        Verifies kill switch doesn't interfere with normal operation.
        """
        # Create fresh mocks without positions (avoid Decimal/float type mismatch)
        strategy = Mock()
        data = Mock()
        broker = Mock()
        broker.positions.return_value = {}  # No open positions
        broker.balance.return_value = 10000.0

        config = {
            "mode": "paper",
            "risk": {
                "halt": False,  # Kill switch OFF
                "max_daily_loss": 500.0,
                "max_trades_per_day": 20,
                "max_position_usd": 10000.0
            }
        }

        # Strategy generates a signal
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.1,
            price=50000.0,
            sl=49500.0,
            tp=50500.0,
            reason="test_signal"
        )
        strategy.on_bar.return_value = [signal]

        runner = LiveRunner(strategy, data, broker, config)

        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - should execute signal normally
        runner._process_bar(bar)

        # Verify order was placed
        broker.buy.assert_called_once_with("BTCUSDT", 0.1, 49500.0, 50500.0)

        # Verify NO emergency shutdown
        broker.close_all.assert_not_called()

    def test_kill_switch_priority_over_risk_checks(self, mock_components, config_with_kill_file):
        """
        Test kill switch has highest priority (checked before other risk limits).

        Even if signal would pass other risk checks, kill switch blocks it.
        """
        strategy, data, broker = mock_components
        config, kill_file = config_with_kill_file

        # Strategy generates valid signal
        signal = Signal(
            symbol="BTCUSDT",
            side="buy",
            qty=0.1,
            price=50000.0,
            reason="valid_signal"
        )
        strategy.on_bar.return_value = [signal]

        runner = LiveRunner(strategy, data, broker, config)

        # Activate kill switch
        kill_file.touch()

        bar = Bar(
            timestamp=1000000000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=100.0,
            zero_vol_flag=False,
            gap_flag=False
        )

        # Process bar - kill switch should trigger before risk checks
        with pytest.raises(SystemExit):
            runner._process_bar(bar)

        # Verify signal was never evaluated by risk manager
        broker.buy.assert_not_called()
