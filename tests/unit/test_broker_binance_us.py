"""
Unit tests for Binance.us Spot broker adapter.

Tests use mocked API responses to validate broker functionality
without requiring real API credentials or making actual trades.

IMPORTANT: Binance.us spot trading is LONG-ONLY (no shorting).
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from app.adapters.broker_binance_us import BinanceUSSpotBroker, BinanceUSError
from app.engine.types import Position


class TestBinanceUSBrokerInit:
    """Test broker initialization."""

    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_init_with_credentials(self):
        """Test initialization with valid credentials."""
        broker = BinanceUSSpotBroker()

        assert broker.api_key == "test_key"
        assert broker.api_secret == "test_secret"
        assert broker.recv_window == 5000

    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_init_with_custom_recv_window(self):
        """Test initialization with custom recv_window."""
        broker = BinanceUSSpotBroker(recv_window=10000)

        assert broker.recv_window == 10000

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(BinanceUSError, match="Missing API credentials"):
            BinanceUSSpotBroker()

    @patch.dict("os.environ", {"BINANCE_US_API_KEY": "test_key"}, clear=True)
    def test_init_without_api_secret(self):
        """Test initialization fails without API secret."""
        with pytest.raises(BinanceUSError, match="Missing API credentials"):
            BinanceUSSpotBroker()


class TestSignature:
    """Test HMAC-SHA256 signature generation."""

    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_sign(self):
        """Test signature generation."""
        broker = BinanceUSSpotBroker()

        params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET"
        }

        signature = broker._sign(params)

        # Should return a hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in signature)

    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_sign_deterministic(self):
        """Test signature is deterministic (same input = same output)."""
        broker = BinanceUSSpotBroker()

        params = {"symbol": "BTCUSDT", "side": "BUY"}

        sig1 = broker._sign(params)
        sig2 = broker._sign(params)

        assert sig1 == sig2


class TestBuyOrder:
    """Test BUY order placement (open long position)."""

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_buy_success(self, mock_post):
        """Test successful BUY order."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "orderId": 12345678,
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "executedQty": "0.001"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()
        order_id = broker.buy(
            symbol="BTCUSDT",
            qty=Decimal("0.001")
        )

        assert order_id == "12345678"
        mock_post.assert_called_once()

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_buy_with_decimal_qty(self, mock_post):
        """Test BUY order with Decimal quantity (NOT float)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orderId": 12345678}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()
        order_id = broker.buy(
            symbol="BTCUSDT",
            qty=Decimal("0.00123456")  # Precise Decimal
        )

        # Verify qty was converted to string (not float)
        call_args = mock_post.call_args
        params = call_args[1]["params"]
        assert params["quantity"] == "0.00123456"
        assert isinstance(params["quantity"], str)

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_buy_api_error(self, mock_post):
        """Test BUY order with API error."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"code":-1111,"msg":"Insufficient balance"}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()

        with pytest.raises(BinanceUSError, match="HTTP 400"):
            broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_buy_no_order_id(self, mock_post):
        """Test BUY order fails if no orderId returned."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No orderId
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()

        with pytest.raises(BinanceUSError, match="no orderId returned"):
            broker.buy(symbol="BTCUSDT", qty=Decimal("0.001"))


class TestSellOrder:
    """Test SELL order placement (close long position, NOT short)."""

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_sell_success(self, mock_post):
        """Test successful SELL order (closes long position)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "orderId": 87654321,
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "executedQty": "0.001"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()
        order_id = broker.sell(
            symbol="BTCUSDT",
            qty=Decimal("0.001")
        )

        assert order_id == "87654321"
        mock_post.assert_called_once()

        # Verify it's a SELL order
        call_args = mock_post.call_args
        params = call_args[1]["params"]
        assert params["side"] == "SELL"

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_sell_with_decimal_qty(self, mock_post):
        """Test SELL order with Decimal quantity (NOT float)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"orderId": 87654321}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        broker = BinanceUSSpotBroker()
        order_id = broker.sell(
            symbol="BTCUSDT",
            qty=Decimal("0.00234567")
        )

        # Verify qty was converted to string (not float)
        call_args = mock_post.call_args
        params = call_args[1]["params"]
        assert params["quantity"] == "0.00234567"
        assert isinstance(params["quantity"], str)


class TestCloseAll:
    """Test close_all() - sell all holdings for a symbol."""

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_close_all_with_position(self, mock_get, mock_post):
        """Test close_all sells existing holdings."""
        # Mock positions() to return holdings
        mock_response_account = MagicMock()
        mock_response_account.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"}
            ]
        }
        mock_response_account.raise_for_status = Mock()

        # Mock ticker price
        mock_response_ticker = MagicMock()
        mock_response_ticker.json.return_value = {"price": "50000.0"}
        mock_response_ticker.raise_for_status = Mock()

        # Mock sell order
        mock_response_sell = MagicMock()
        mock_response_sell.json.return_value = {"orderId": 99999}
        mock_response_sell.raise_for_status = Mock()

        mock_get.side_effect = [mock_response_account, mock_response_ticker]
        mock_post.return_value = mock_response_sell

        broker = BinanceUSSpotBroker()
        broker.close_all("BTCUSDT")

        # Should have called sell with the BTC balance
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        params = call_args[1]["params"]
        assert params["side"] == "SELL"
        assert params["quantity"] == "0.5"  # Total BTC holdings

    @patch("app.adapters.broker_binance_us.requests.post")
    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_close_all_no_position(self, mock_get, mock_post):
        """Test close_all does nothing if no holdings."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.0", "locked": "0.0"},  # No BTC
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()
        broker.close_all("BTCUSDT")

        # Should NOT call sell
        mock_post.assert_not_called()


class TestPositions:
    """Test position tracking (holdings in spot trading)."""

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_positions_with_holdings(self, mock_get):
        """Test positions() returns holdings."""
        # Mock account balances
        mock_response_account = MagicMock()
        mock_response_account.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.1"},
                {"asset": "ETH", "free": "5.0", "locked": "0.0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"}
            ]
        }
        mock_response_account.raise_for_status = Mock()

        # Mock ticker prices
        mock_response_btc = MagicMock()
        mock_response_btc.json.return_value = {"price": "50000.0"}
        mock_response_btc.raise_for_status = Mock()

        mock_response_eth = MagicMock()
        mock_response_eth.json.return_value = {"price": "3000.0"}
        mock_response_eth.raise_for_status = Mock()

        mock_get.side_effect = [
            mock_response_account,
            mock_response_btc,
            mock_response_eth
        ]

        broker = BinanceUSSpotBroker()
        positions = broker.positions()

        # Should return 2 positions (BTC and ETH)
        assert len(positions) == 2
        assert "BTCUSDT" in positions
        assert "ETHUSDT" in positions

        # Check BTC position
        btc_pos = positions["BTCUSDT"]
        assert isinstance(btc_pos, Position)
        assert btc_pos.symbol == "BTCUSDT"
        assert btc_pos.side == "long"  # Spot is always long
        assert btc_pos.qty == Decimal("0.6")  # free + locked
        assert btc_pos.current_price == Decimal("50000.0")

        # Check ETH position
        eth_pos = positions["ETHUSDT"]
        assert eth_pos.symbol == "ETHUSDT"
        assert eth_pos.qty == Decimal("5.0")

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_positions_empty(self, mock_get):
        """Test positions() with no holdings."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.0", "locked": "0.0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()
        positions = broker.positions()

        # Should return empty dict (USDT is quote currency, skipped)
        assert len(positions) == 0

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_positions_skips_quote_currency(self, mock_get):
        """Test positions() skips USDT/USD (quote currencies)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "balances": [
                {"asset": "USDT", "free": "5000.0", "locked": "0.0"},
                {"asset": "USD", "free": "1000.0", "locked": "0.0"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()
        positions = broker.positions()

        # Should NOT include USDT or USD positions
        assert len(positions) == 0


class TestBalance:
    """Test account balance queries."""

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_balance_success(self, mock_get):
        """Test successful balance query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "USDT", "free": "12345.67", "locked": "100.0"},
                {"asset": "ETH", "free": "2.0", "locked": "0.0"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()
        balance = broker.balance()

        # Should return free USDT balance
        assert isinstance(balance, Decimal)
        assert balance == Decimal("12345.67")

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_balance_no_usdt(self, mock_get):
        """Test balance query with no USDT."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "ETH", "free": "2.0", "locked": "0.0"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()
        balance = broker.balance()

        # Should return 0
        assert balance == Decimal("0")

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_balance_api_error(self, mock_get):
        """Test balance query with API error."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"code":-2015,"msg":"Invalid API-key"}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        broker = BinanceUSSpotBroker()

        with pytest.raises(BinanceUSError, match="HTTP 401"):
            broker.balance()


class TestRequestMethod:
    """Test internal _request method."""

    @patch("app.adapters.broker_binance_us.requests.get")
    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_request_timeout(self, mock_get):
        """Test request with timeout."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        broker = BinanceUSSpotBroker()

        with pytest.raises(BinanceUSError, match="Request failed"):
            broker._request("GET", "/api/v3/account", signed=True)

    @patch.dict("os.environ", {
        "BINANCE_US_API_KEY": "test_key",
        "BINANCE_US_API_SECRET": "test_secret"
    })
    def test_request_unsupported_method(self):
        """Test request with unsupported HTTP method."""
        broker = BinanceUSSpotBroker()

        with pytest.raises(BinanceUSError, match="Unsupported HTTP method"):
            broker._request("PATCH", "/api/v3/order")
