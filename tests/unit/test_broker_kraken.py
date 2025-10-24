"""Unit tests for KrakenFuturesBroker."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from app.adapters.broker_kraken import (
    KrakenFuturesBroker,
    KrakenError
)
from app.engine.types import Position


class TestKrakenFuturesBroker:
    """Test KrakenFuturesBroker class."""

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_api_key_123",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXRfMTIz"  # base64: "test_secret_123"
    })
    def test_init_demo(self):
        """Test broker initialization with demo environment."""
        broker = KrakenFuturesBroker(demo=True)

        assert broker.demo is True
        assert broker.base_url == KrakenFuturesBroker.DEMO_BASE
        assert broker.api_key == "test_api_key_123"
        assert broker.api_secret == "dGVzdF9zZWNyZXRfMTIz"

    @patch.dict("os.environ", {
        "KRAKEN_API_KEY": "live_key",
        "KRAKEN_API_SECRET": "bGl2ZV9zZWNyZXQ="
    })
    def test_init_live(self):
        """Test broker initialization with live environment."""
        broker = KrakenFuturesBroker(demo=False)

        assert broker.demo is False
        assert broker.base_url == KrakenFuturesBroker.LIVE_BASE
        assert broker.api_key == "live_key"

    @patch.dict("os.environ", {}, clear=True)
    def test_init_missing_credentials(self):
        """Test initialization fails without credentials."""
        with pytest.raises(KrakenError) as exc_info:
            KrakenFuturesBroker(demo=True)

        assert "Missing API credentials" in str(exc_info.value)

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    def test_get_nonce(self):
        """Test nonce generation."""
        broker = KrakenFuturesBroker(demo=True)

        nonce1 = broker._get_nonce()
        nonce2 = broker._get_nonce()

        # Nonces should be unique and increasing
        assert int(nonce2) > int(nonce1)

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    def test_sign(self):
        """Test signature generation."""
        broker = KrakenFuturesBroker(demo=True)

        signature = broker._sign(
            endpoint_path="/sendorder",
            post_data="symbol=PF_XBTUSD&side=buy",
            nonce="1234567890"
        )

        # Signature should be base64-encoded
        assert isinstance(signature, str)
        assert len(signature) > 0

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.post")
    def test_buy_success(self, mock_post):
        """Test successful BUY order."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "sendStatus": {
                "order_id": "test_order_123",
                "status": "placed"
            }
        }
        mock_post.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        order_id = broker.buy(
            symbol="PF_XBTUSD",
            qty=Decimal("0.001")
        )

        assert order_id == "test_order_123"

        # Verify request was made correctly
        assert mock_post.called
        call_args = mock_post.call_args
        assert "/sendorder" in call_args[0][0]

        # Check POST data
        post_data = call_args[1]["data"]
        assert post_data["symbol"] == "PF_XBTUSD"
        assert post_data["side"] == "buy"
        assert post_data["size"] == "0.001"
        assert post_data["orderType"] == "mkt"

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.post")
    def test_sell_success(self, mock_post):
        """Test successful SELL order."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "sendStatus": {
                "order_id": "test_order_456",
                "status": "placed"
            }
        }
        mock_post.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        order_id = broker.sell(
            symbol="PF_XBTUSD",
            qty=Decimal("0.002")
        )

        assert order_id == "test_order_456"

        # Verify SELL side
        post_data = mock_post.call_args[1]["data"]
        assert post_data["side"] == "sell"

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.get")
    def test_positions_with_open_long(self, mock_get):
        """Test querying positions with open long."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "openPositions": [
                {
                    "symbol": "PF_XBTUSD",
                    "side": "long",
                    "size": 0.001,
                    "price": 50000.0
                }
            ]
        }
        mock_get.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        positions = broker.positions()

        assert "PF_XBTUSD" in positions
        pos = positions["PF_XBTUSD"]

        assert pos.symbol == "PF_XBTUSD"
        assert pos.side == "long"
        assert pos.qty == Decimal("0.001")
        assert pos.entry_price == Decimal("50000.0")

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.get")
    def test_positions_with_open_short(self, mock_get):
        """Test querying positions with open short."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "openPositions": [
                {
                    "symbol": "PF_ETHUSD",
                    "side": "short",
                    "size": 0.1,
                    "price": 3000.0
                }
            ]
        }
        mock_get.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        positions = broker.positions()

        assert "PF_ETHUSD" in positions
        pos = positions["PF_ETHUSD"]

        assert pos.side == "short"
        assert pos.qty == Decimal("0.1")

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.get")
    def test_positions_empty(self, mock_get):
        """Test querying positions when none open."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "openPositions": []
        }
        mock_get.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        positions = broker.positions()

        assert len(positions) == 0

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.get")
    def test_balance(self, mock_get):
        """Test querying account balance."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "accounts": {
                "flex": {
                    "balanceValue": 10000.50
                }
            }
        }
        mock_get.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)
        balance = broker.balance()

        assert balance == Decimal("10000.50")

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.post")
    def test_order_api_error(self, mock_post):
        """Test order fails with API error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "error",
            "error": "Insufficient margin"
        }
        mock_post.return_value = mock_response

        broker = KrakenFuturesBroker(demo=True)

        with pytest.raises(KrakenError) as exc_info:
            broker.buy(symbol="PF_XBTUSD", qty=Decimal("1.0"))

        assert "Insufficient margin" in str(exc_info.value)

    @patch.dict("os.environ", {
        "KRAKEN_DEMO_API_KEY": "test_key",
        "KRAKEN_DEMO_API_SECRET": "dGVzdF9zZWNyZXQ="
    })
    @patch("requests.get")
    @patch("requests.post")
    def test_close_all_long_position(self, mock_post, mock_get):
        """Test closing a long position."""
        # Mock positions() to return open long
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "result": "success",
            "openPositions": [
                {
                    "symbol": "PF_XBTUSD",
                    "side": "long",
                    "size": 0.001,
                    "price": 50000.0
                }
            ]
        }
        mock_get.return_value = mock_get_response

        # Mock sell() order
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "result": "success",
            "sendStatus": {"order_id": "close_order_123"}
        }
        mock_post.return_value = mock_post_response

        broker = KrakenFuturesBroker(demo=True)
        broker.close_all(symbol="PF_XBTUSD")

        # Should have called sell()
        assert mock_post.called
        post_data = mock_post.call_args[1]["data"]
        assert post_data["side"] == "sell"
        assert post_data["size"] == "0.001"
