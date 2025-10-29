"""Unit tests for BinanceFuturesBroker."""
import os
import hmac
import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock
from trade_engine.adapters.brokers.binance import BinanceFuturesBroker, BinanceError


class TestBrokerSignature:
    """Test HMAC SHA256 signature generation."""

    def test_sign_generates_correct_hmac_sha256(self):
        """Test that _sign() generates correct HMAC SHA256 signature."""
        # ARRANGE: Set up test credentials and parameters
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "a" * 64,
            "BINANCE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Test parameters
            params = {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.001",
                "timestamp": "1609459200000",
                "recvWindow": "5000"
            }

            # Expected signature (pre-calculated)
            # Query string: symbol=BTCUSDT&side=BUY&type=MARKET&quantity=0.001&timestamp=1609459200000&recvWindow=5000
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            expected_signature = hmac.new(
                b"b" * 64,
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()

            # ACT: Generate signature
            actual_signature = broker._sign(params)

            # ASSERT: Signature matches expected HMAC SHA256
            assert actual_signature == expected_signature
            assert isinstance(actual_signature, str)
            assert len(actual_signature) == 64  # SHA256 hex digest is 64 chars

    def test_sign_different_params_generates_different_signature(self):
        """Test that different parameters generate different signatures."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "a" * 64,
            "BINANCE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            params1 = {"symbol": "BTCUSDT", "quantity": "0.001"}
            params2 = {"symbol": "ETHUSDT", "quantity": "0.001"}

            # ACT
            sig1 = broker._sign(params1)
            sig2 = broker._sign(params2)

            # ASSERT
            assert sig1 != sig2

    def test_sign_empty_params(self):
        """Test signature generation with empty parameters."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "a" * 64,
            "BINANCE_TESTNET_API_SECRET": "b" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # ACT
            signature = broker._sign({})

            # ASSERT: Should still generate valid signature (empty query string)
            expected = hmac.new(
                b"b" * 64,
                b"",
                hashlib.sha256
            ).hexdigest()
            assert signature == expected


class TestBrokerInitialization:
    """Test broker initialization and configuration."""

    def test_testnet_initialization_success(self):
        """Test successful testnet broker initialization."""
        # ARRANGE & ACT
        test_key = "a" * 64  # Valid 64-character key
        test_secret = "b" * 64  # Valid 64-character secret
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": test_key,
            "BINANCE_TESTNET_API_SECRET": test_secret
        }):
            broker = BinanceFuturesBroker(testnet=True)

        # ASSERT
        assert broker.testnet is True
        assert broker.base_url == BinanceFuturesBroker.TESTNET_BASE
        assert broker.api_key == test_key
        assert broker.api_secret == test_secret
        assert broker.recv_window == 5000

    def test_live_initialization_success(self):
        """Test successful live broker initialization."""
        # ARRANGE & ACT
        live_key = "c" * 64
        live_secret = "d" * 64
        with patch.dict(os.environ, {
            "BINANCE_API_KEY": live_key,
            "BINANCE_API_SECRET": live_secret
        }):
            broker = BinanceFuturesBroker(testnet=False)

        # ASSERT
        assert broker.testnet is False
        assert broker.base_url == BinanceFuturesBroker.LIVE_BASE
        assert broker.api_key == live_key
        assert broker.api_secret == live_secret

    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises BinanceError."""
        # ARRANGE: Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            # ACT & ASSERT
            with pytest.raises(BinanceError, match="Missing API credentials"):
                BinanceFuturesBroker(testnet=True)

    def test_missing_api_secret_raises_error(self):
        """Test that missing API secret raises BinanceError."""
        # ARRANGE: Only API key set
        with patch.dict(os.environ, {"BINANCE_TESTNET_API_KEY": "c" * 64}, clear=True):
            # ACT & ASSERT
            with pytest.raises(BinanceError, match="Missing API credentials"):
                BinanceFuturesBroker(testnet=True)

    def test_custom_recv_window(self):
        """Test custom recvWindow configuration."""
        # ARRANGE & ACT
        test_key = "e" * 64
        test_secret = "f" * 64
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": test_key,
            "BINANCE_TESTNET_API_SECRET": test_secret
        }):
            broker = BinanceFuturesBroker(testnet=True, recv_window=10000)

        # ASSERT
        assert broker.recv_window == 10000


class TestBrokerOrderOperations:
    """Test broker order operations (buy, sell, close)."""

    def test_buy_success(self):
        """Test successful buy order placement."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Mock the _request method to return a successful response
            broker._request = Mock(return_value={"orderId": 123456789})

            # ACT
            order_id = broker.buy(symbol="BTCUSDT", qty=0.001)

            # ASSERT
            assert order_id == "123456789"
            broker._request.assert_called_once()

            # Verify the request parameters
            call_args = broker._request.call_args
            assert call_args[0][0] == "POST"  # method
            assert call_args[0][1] == "/fapi/v1/order"  # endpoint
            assert call_args[1]["signed"] is True
            assert call_args[1]["symbol"] == "BTCUSDT"
            assert call_args[1]["side"] == "BUY"
            assert call_args[1]["type"] == "MARKET"
            assert call_args[1]["quantity"] == 0.001

    def test_sell_success(self):
        """Test successful sell order placement."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)
            broker._request = Mock(return_value={"orderId": 987654321})

            # ACT
            order_id = broker.sell(symbol="ETHUSDT", qty=0.01)

            # ASSERT
            assert order_id == "987654321"
            broker._request.assert_called_once()

            call_args = broker._request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[1]["symbol"] == "ETHUSDT"
            assert call_args[1]["side"] == "SELL"
            assert call_args[1]["quantity"] == 0.01

    def test_positions_with_open_long(self):
        """Test positions() returns long position correctly."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Mock API response for a long position
            broker._request = Mock(return_value=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.001",  # Positive = long
                    "entryPrice": "50000.0",
                    "markPrice": "51000.0",
                    "unRealizedProfit": "1.0"
                }
            ])

            # ACT
            positions = broker.positions()

            # ASSERT
            assert "BTCUSDT" in positions
            pos = positions["BTCUSDT"]
            assert pos.symbol == "BTCUSDT"
            assert pos.side == "long"
            assert pos.qty == 0.001
            assert pos.entry_price == 50000.0
            assert pos.current_price == 51000.0
            assert pos.pnl == 1.0
            assert pos.pnl_pct > 0  # Profit

    def test_positions_with_open_short(self):
        """Test positions() returns short position correctly."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Mock API response for a short position
            broker._request = Mock(return_value=[
                {
                    "symbol": "ETHUSDT",
                    "positionAmt": "-0.01",  # Negative = short
                    "entryPrice": "3000.0",
                    "markPrice": "2950.0",
                    "unRealizedProfit": "0.5"
                }
            ])

            # ACT
            positions = broker.positions()

            # ASSERT
            assert "ETHUSDT" in positions
            pos = positions["ETHUSDT"]
            assert pos.side == "short"
            assert pos.qty == 0.01  # Absolute value

    def test_positions_empty_when_no_positions(self):
        """Test positions() returns empty dict when no positions."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Mock API response with zero position
            broker._request = Mock(return_value=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.0",  # No position
                    "entryPrice": "0.0",
                    "markPrice": "50000.0",
                    "unRealizedProfit": "0.0"
                }
            ])

            # ACT
            positions = broker.positions()

            # ASSERT
            assert positions == {}  # Empty dict

    def test_close_all_long_position(self):
        """Test close_all() closes long position with sell order."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            # Mock positions to return a long position
            from trade_engine.core.types import Position
            mock_position = Position(
                symbol="BTCUSDT",
                side="long",
                qty=0.001,
                entry_price=50000.0,
                current_price=51000.0,
                pnl=1.0,
                pnl_pct=2.0
            )
            broker.positions = Mock(return_value={"BTCUSDT": mock_position})
            broker.sell = Mock(return_value="close_order_123")

            # ACT
            broker.close_all("BTCUSDT")

            # ASSERT
            broker.sell.assert_called_once_with("BTCUSDT", 0.001)

    def test_close_all_short_position(self):
        """Test close_all() closes short position with buy order."""
        # ARRANGE
        with patch.dict(os.environ, {
            "BINANCE_TESTNET_API_KEY": "c" * 64,
            "BINANCE_TESTNET_API_SECRET": "d" * 64
        }):
            broker = BinanceFuturesBroker(testnet=True)

            from trade_engine.core.types import Position
            mock_position = Position(
                symbol="ETHUSDT",
                side="short",
                qty=0.01,
                entry_price=3000.0,
                current_price=2950.0,
                pnl=0.5,
                pnl_pct=1.67
            )
            broker.positions = Mock(return_value={"ETHUSDT": mock_position})
            broker.buy = Mock(return_value="close_order_456")

            # ACT
            broker.close_all("ETHUSDT")

            # ASSERT
            broker.buy.assert_called_once_with("ETHUSDT", 0.01)
