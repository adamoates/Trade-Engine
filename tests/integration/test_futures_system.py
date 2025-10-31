"""
Integration Test: Perpetual Futures Trading System.

Tests complete workflow across all components:
- FundingRateService
- FuturesRiskManager
- PositionManager
- Database logging

Uses mocked broker and database to verify integration without external dependencies.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.services.trading.position_manager import PositionManager


@dataclass
class MockPosition:
    """Mock position object returned by broker.

    NOTE: Must match the real Position dataclass in src/trade_engine/core/types.py
    to ensure integration tests catch real-world bugs.
    """

    symbol: str
    side: str              # "long" | "short"
    qty: Decimal           # Position size (base currency)
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal           # Unrealized P&L (USD) - renamed from unrealized_pnl
    pnl_pct: Decimal       # Unrealized P&L (%)

    # Additional fields for futures testing (not in base Position)
    maintenance_margin: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")  # Deprecated, use pnl instead

    def __post_init__(self):
        """Sync unrealized_pnl with pnl for backward compatibility."""
        if self.unrealized_pnl == Decimal("0") and self.pnl != Decimal("0"):
            self.unrealized_pnl = self.pnl
        elif self.pnl == Decimal("0") and self.unrealized_pnl != Decimal("0"):
            self.pnl = self.unrealized_pnl


class TestFuturesSystemIntegration:
    """Integration tests for perpetual futures trading system."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker adapter."""
        broker = Mock()
        broker.balance.return_value = Decimal("10000")
        broker.get_ticker_price.return_value = Decimal("50000")
        broker.positions.return_value = {}
        broker.__class__.__name__ = "MockBroker"
        return broker

    @pytest.fixture
    def mock_database(self):
        """Create mock database adapter."""
        db = Mock()
        return db

    @pytest.fixture
    def mock_funding_service(self, mock_database):
        """Create funding service with mocked API calls."""
        with patch("trade_engine.services.data.funding_rate_service.requests") as mock_requests:
            # Mock funding rate API response
            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "fundingTime": 1640000000000,
                }
            ]
            mock_response.raise_for_status.return_value = None
            mock_requests.get.return_value = mock_response

            service = FundingRateService(database=mock_database, testnet=True)
            return service

    @pytest.fixture
    def risk_manager(self):
        """Create futures risk manager."""
        config = {
            "risk": {
                "max_daily_loss_usd": 500,
                "max_trades_per_day": 50,
                "max_position_usd": 10000,
            }
        }
        return FuturesRiskManager(
            config=config, max_leverage=5, liquidation_buffer=Decimal("0.15")
        )

    @pytest.fixture
    def position_manager(
        self, mock_broker, risk_manager, mock_funding_service, mock_database
    ):
        """Create position manager with all dependencies."""
        return PositionManager(
            broker=mock_broker,
            risk_manager=risk_manager,
            funding_service=mock_funding_service,
            database=mock_database,
        )

    def test_open_position_success(self, position_manager, mock_broker, mock_database):
        """Test successful position opening with all checks."""
        # Setup broker responses
        mock_broker.set_leverage = Mock()
        mock_broker.buy = Mock(return_value="order_12345")

        # Open position
        result = position_manager.open_position(
            symbol="BTCUSDT",
            side="long",
            size=Decimal("0.1"),
            leverage=3,
            strategy="test_strategy",
        )

        # Verify success
        assert result["success"] is True
        assert result["order_id"] == "order_12345"
        assert result["entry_price"] == Decimal("50000")
        assert "liquidation_price" in result
        assert "funding_rate" in result

        # Verify broker interactions
        mock_broker.set_leverage.assert_called_once_with("BTCUSDT", 3)
        mock_broker.buy.assert_called_once()

        # Verify database logging
        mock_database.open_position.assert_called_once()
        call_args = mock_database.open_position.call_args[1]
        assert call_args["symbol"] == "BTCUSDT"
        assert call_args["side"] == "long"
        assert call_args["qty"] == Decimal("0.1")
        assert call_args["strategy"] == "test_strategy"

    def test_open_position_risk_rejected(
        self, position_manager, mock_broker, risk_manager
    ):
        """Test position rejected by risk manager."""
        # Trigger kill switch to block trading
        risk_manager.trigger_kill_switch("Test block")

        # Attempt to open position
        result = position_manager.open_position(
            symbol="BTCUSDT", side="long", size=Decimal("0.1"), leverage=3
        )

        # Verify rejection
        assert result["success"] is False
        assert "Kill switch" in result["reason"]

        # Verify no broker calls
        mock_broker.set_leverage.assert_not_called()
        mock_broker.buy.assert_not_called()

    def test_open_position_excessive_size(self, position_manager, mock_broker):
        """Test position rejected due to excessive size."""
        # Try to open position exceeding max limit ($10K)
        result = position_manager.open_position(
            symbol="BTCUSDT",
            side="long",
            size=Decimal("1.0"),  # $50K notional
            leverage=1,
        )

        # Verify rejection
        assert result["success"] is False
        assert "hard limit" in result["reason"]
        mock_broker.buy.assert_not_called()

    def test_monitor_positions_healthy(
        self, position_manager, mock_broker, mock_database
    ):
        """Test position monitoring with healthy margin."""
        # Setup open position
        mock_broker.positions.return_value = {
            "BTCUSDT": MockPosition(
                symbol="BTCUSDT",
                side="long",
                qty=Decimal("0.1"),
                entry_price=Decimal("50000"),
                current_price=Decimal("50500"),
                pnl=Decimal("50"),
                pnl_pct=Decimal("0.01"),
                maintenance_margin=Decimal("500"),
            )
        }

        # Monitor positions
        position_manager.monitor_positions()

        # Verify PnL snapshot logged
        mock_database.log_pnl_snapshot.assert_called_once()
        call_args = mock_database.log_pnl_snapshot.call_args[1]
        assert call_args["balance"] == Decimal("10000")
        assert call_args["unrealized_pnl"] == Decimal("50")
        assert call_args["open_positions"] == 1

        # Verify no emergency actions
        mock_broker.close_all.assert_not_called()

    def test_monitor_positions_low_margin(
        self, position_manager, mock_broker, mock_database
    ):
        """Test position monitoring with low margin triggers reduction."""
        # Setup position with low margin ratio
        mock_broker.positions.return_value = {
            "BTCUSDT": MockPosition(
                symbol="BTCUSDT",
                side="long",
                qty=Decimal("0.2"),
                entry_price=Decimal("50000"),
                current_price=Decimal("48000"),
                pnl=Decimal("-400"),
                pnl_pct=Decimal("-0.04"),
                maintenance_margin=Decimal("8500"),  # High maintenance margin
            )
        }

        # Mock position reduction
        mock_broker.sell = Mock()

        # Monitor positions
        position_manager.monitor_positions()

        # Verify reduction triggered (sell half the position)
        mock_broker.sell.assert_called_once()

    def test_close_position_success(
        self, position_manager, mock_broker, mock_database
    ):
        """Test successful position closing with P&L tracking."""
        # Setup open position
        mock_broker.positions.return_value = {
            "BTCUSDT": MockPosition(
                symbol="BTCUSDT",
                side="long",
                qty=Decimal("0.1"),
                entry_price=Decimal("50000"),
                current_price=Decimal("51000"),
                pnl=Decimal("100"),
                pnl_pct=Decimal("0.02"),
                maintenance_margin=Decimal("500"),
            )
        }

        mock_broker.close_all = Mock()
        mock_broker.get_ticker_price.return_value = Decimal("51000")

        # Close position
        result = position_manager.close_position("BTCUSDT", reason="Test close")

        # Verify success
        assert result["success"] is True
        assert result["exit_price"] == Decimal("51000")
        assert result["realized_pnl"] == Decimal("100")

        # Verify P&L tracking updated
        pnl_stats = position_manager.get_realized_pnl()
        assert pnl_stats["session_pnl"] == Decimal("100")
        assert pnl_stats["daily_pnl"] == Decimal("100")

        # Verify broker call
        mock_broker.close_all.assert_called_once_with("BTCUSDT")

        # Verify database logging
        mock_database.close_position.assert_called_once()

    def test_close_position_not_open(self, position_manager, mock_broker):
        """Test closing non-existent position."""
        # No open positions
        mock_broker.positions.return_value = {}

        # Attempt to close
        result = position_manager.close_position("BTCUSDT")

        # Verify failure
        assert result["success"] is False
        assert "No open position" in result["reason"]
        mock_broker.close_all.assert_not_called()

    def test_multiple_positions_lifecycle(
        self, position_manager, mock_broker, mock_database
    ):
        """Test opening, monitoring, and closing multiple positions."""
        # Setup broker for multiple orders
        mock_broker.set_leverage = Mock()
        mock_broker.buy = Mock(side_effect=["order_1", "order_2"])
        mock_broker.sell = Mock(return_value="order_3")

        # Mock get_ticker_price to return appropriate prices for each symbol
        mock_broker.get_ticker_price = Mock(side_effect=[
            Decimal("50000"),  # BTC price for first position
            Decimal("3000"),   # ETH price for second position
            Decimal("50200"),  # BTC price when closing
        ])

        # Open two long positions with realistic sizes
        result1 = position_manager.open_position(
            symbol="BTCUSDT", side="long", size=Decimal("0.05"), leverage=3
        )
        result2 = position_manager.open_position(
            symbol="ETHUSDT", side="long", size=Decimal("0.5"), leverage=2
        )

        assert result1["success"] is True
        assert result2["success"] is True

        # Mock both positions open
        mock_broker.positions.return_value = {
            "BTCUSDT": MockPosition(
                symbol="BTCUSDT",
                side="long",
                qty=Decimal("0.05"),
                entry_price=Decimal("50000"),
                current_price=Decimal("50100"),
                pnl=Decimal("5"),
                pnl_pct=Decimal("0.001"),
                maintenance_margin=Decimal("250"),
            ),
            "ETHUSDT": MockPosition(
                symbol="ETHUSDT",
                side="long",
                qty=Decimal("0.5"),
                entry_price=Decimal("3000"),
                current_price=Decimal("3050"),
                pnl=Decimal("25"),
                pnl_pct=Decimal("0.0083"),
                maintenance_margin=Decimal("150"),
            ),
        }

        # Monitor positions
        position_manager.monitor_positions()

        # Verify monitoring logged both positions
        call_args = mock_database.log_pnl_snapshot.call_args[1]
        assert call_args["open_positions"] == 2
        assert call_args["unrealized_pnl"] == Decimal("30")  # 5 + 25

        # Close one position
        mock_broker.positions.return_value = {
            "BTCUSDT": MockPosition(
                symbol="BTCUSDT",
                side="long",
                qty=Decimal("0.05"),
                entry_price=Decimal("50000"),
                current_price=Decimal("50200"),
                pnl=Decimal("10"),
                pnl_pct=Decimal("0.002"),
                maintenance_margin=Decimal("250"),
            )
        }
        mock_broker.close_all = Mock()
        # Reset get_ticker_price to return value instead of side_effect
        mock_broker.get_ticker_price = Mock(return_value=Decimal("50200"))

        close_result = position_manager.close_position("BTCUSDT")
        assert close_result["success"] is True

        # Verify realized P&L updated
        pnl_stats = position_manager.get_realized_pnl()
        assert pnl_stats["session_pnl"] == Decimal("10")

    def test_liquidation_price_calculation(self, risk_manager):
        """Test liquidation price calculation with symbol-specific MMR."""
        # Test with BTC (0.4% MMR)
        btc_liq = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("50000"),
            leverage=5,
            side="long",
            symbol="BTCUSDT",
        )

        # Long liq = 50000 * (1 - 0.2 + 0.004) = 50000 * 0.804 = 40200
        assert btc_liq == Decimal("40200.00")

        # Test with ETH (0.5% MMR)
        eth_liq = risk_manager.calculate_liquidation_price(
            entry_price=Decimal("3000"),
            leverage=5,
            side="long",
            symbol="ETHUSDT",
        )

        # Long liq = 3000 * (1 - 0.2 + 0.005) = 3000 * 0.805 = 2415
        assert eth_liq == Decimal("2415.00")

    def test_funding_rate_integration(self, mock_funding_service):
        """Test funding rate service integration."""
        # Get current funding rate
        rate = mock_funding_service.get_current_funding_rate("BTCUSDT")
        assert rate == Decimal("0.0001")

        # Estimate daily funding
        daily_cost = mock_funding_service.estimate_daily_funding(
            "BTCUSDT", Decimal("0.1"), Decimal("50000")
        )

        # 0.1 BTC * 50000 * 0.0001 * 3 = $1.50 per day
        assert daily_cost == Decimal("1.50")

    def test_daily_pnl_reset(self, position_manager, mock_broker, mock_database):
        """Test daily P&L resets on new UTC day."""
        # Record some realized P&L
        position_manager.session_realized_pnl = Decimal("100")
        position_manager.daily_realized_pnl = Decimal("100")

        # Simulate UTC day change by manually calling reset check with mocked time
        with patch("trade_engine.services.trading.position_manager.datetime") as mock_dt:
            # Set current time to tomorrow
            tomorrow = datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = tomorrow

            # Trigger reset
            position_manager._check_daily_reset()

            # Verify daily P&L reset but session P&L persists
            assert position_manager.daily_realized_pnl == Decimal("0")
            assert position_manager.session_realized_pnl == Decimal("100")
