"""Shared pytest fixtures and configuration."""
import os
import pytest
from datetime import datetime
from unittest.mock import Mock


@pytest.fixture
def mock_binance_api():
    """Mock Binance API responses."""
    mock = Mock()

    # Mock successful order response
    mock.post_order.return_value = {
        "orderId": "12345",
        "symbol": "BTCUSDT",
        "status": "FILLED",
        "executedQty": "0.001",
        "cumQuote": "50.0"
    }

    # Mock position response
    mock.get_positions.return_value = [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "0.001",
            "entryPrice": "50000.0",
            "unRealizedProfit": "5.0"
        }
    ]

    return mock


@pytest.fixture
def sample_bar():
    """Sample OHLCV bar for testing."""
    from trade_engine.core.engine.types import Bar

    return Bar(
        timestamp=int(datetime(2025, 1, 1, 12, 0).timestamp() * 1000),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=100.5,
        gap_flag=False,
        zero_vol_flag=False
    )


@pytest.fixture
def sample_signal():
    """Sample trading signal for testing."""
    from trade_engine.core.engine.types import Signal

    return Signal(
        symbol="BTCUSDT",
        side="buy",
        qty=0.001,
        price=50000.0,
        sl=49500.0,
        tp=50500.0,
        reason="Test signal"
    )


@pytest.fixture
def testnet_config():
    """Test configuration (testnet mode)."""
    return {
        "mode": "paper",
        "binance": {
            "testnet": True,
            "api_key": os.getenv("BINANCE_TESTNET_API_KEY", "test_key"),
            "api_secret": os.getenv("BINANCE_TESTNET_API_SECRET", "test_secret")
        },
        "symbols": ["BTCUSDT"],
        "timeframe": "5m",
        "risk": {
            "max_position_usd": 100,
            "max_total_exposure_usd": 200,
            "max_daily_loss_usd": 20,
            "max_trades_per_day": 10
        }
    }


@pytest.fixture
def temp_csv_file(tmp_path):
    """Temporary CSV file for testing."""
    csv_path = tmp_path / "test_data.csv"
    return str(csv_path)
