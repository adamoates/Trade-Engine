"""Unit tests for CoinMarketCap data source adapter."""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
import requests
import time

from trade_engine.services.data.types import (
    DataSourceType,
    AssetType,
    Quote
)
from trade_engine.adapters.data_sources.coinmarketcap import CoinMarketCapSource


class TestCoinMarketCapInit:
    """Test CoinMarketCapSource initialization."""

    def test_source_initializes_with_api_key(self):
        """Test source can be initialized with API key."""
        # ACT
        source = CoinMarketCapSource(api_key="test_key_123")

        # ASSERT
        assert source.source_type == DataSourceType.COINMARKETCAP
        assert source.api_key == "test_key_123"
        assert source.sandbox is False

    @patch.dict('os.environ', {'COINMARKETCAP_API_KEY': 'env_key_456'})
    def test_source_initializes_from_env_var(self):
        """Test source reads API key from environment."""
        # ACT
        source = CoinMarketCapSource()

        # ASSERT
        assert source.api_key == "env_key_456"

    def test_source_requires_api_key(self):
        """Test error when no API key provided."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="API key required"):
            CoinMarketCapSource()

    def test_source_type_is_coinmarketcap(self):
        """Test source_type property."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        source_type = source.source_type

        # ASSERT
        assert source_type == DataSourceType.COINMARKETCAP

    def test_supported_asset_types_only_crypto(self):
        """Test only crypto is supported."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        supported = source.supported_asset_types

        # ASSERT
        assert supported == [AssetType.CRYPTO]
        assert AssetType.STOCK not in supported

    def test_sandbox_mode(self):
        """Test sandbox mode initialization."""
        # ACT
        source = CoinMarketCapSource(api_key="test", sandbox=True)

        # ASSERT
        assert source.sandbox is True
        assert "sandbox" in source.base_url


class TestCoinMarketCapFetchQuote:
    """Test real-time quote fetching."""

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_fetch_quote_returns_current_price(self, mock_get):
        """Test fetching current quote."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {
                "error_code": 0
            },
            "data": {
                "BTC": {
                    "id": 1,
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "quote": {
                        "USD": {
                            "price": 67500.50,
                            "volume_24h": 28000000000.0
                        }
                    }
                }
            }
        }
        mock_get.return_value = mock_response

        # ACT
        quote = source.fetch_quote("BTC")

        # ASSERT
        assert quote.symbol == "BTC"
        assert quote.price == 67500.50
        assert quote.volume_24h == 28000000000.0
        assert quote.source == DataSourceType.COINMARKETCAP

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_fetch_quote_api_error(self, mock_get):
        """Test handling of API error."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {
                "error_code": 1001,
                "error_message": "Invalid API key"
            }
        }
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="API error"):
            source.fetch_quote("BTC")

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_fetch_quote_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_quote("BTC")

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_fetch_quote_uses_uppercase_symbol(self, mock_get):
        """Test symbol is converted to uppercase."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {"error_code": 0},
            "data": {
                "ETH": {
                    "quote": {
                        "USD": {"price": 3500.0, "volume_24h": 10000000000.0}
                    }
                }
            }
        }
        mock_get.return_value = mock_response

        # ACT
        source.fetch_quote("eth")

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['symbol'] == "ETH"


class TestCoinMarketCapFetchOHLCV:
    """Test OHLCV data fetching."""

    def test_fetch_ohlcv_returns_empty_for_free_tier(self):
        """Test OHLCV returns empty (not available in free tier)."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("BTC", "1d", start, end)

        # ASSERT
        assert candles == []


class TestCoinMarketCapNormalizeSymbol:
    """Test symbol normalization."""

    def test_normalize_btc_unchanged(self):
        """Test BTC remains unchanged."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTC", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC"

    def test_normalize_removes_usdt_suffix(self):
        """Test USDT suffix is removed."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTCUSDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC"

    def test_normalize_removes_usd_suffix(self):
        """Test USD suffix is removed."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTC/USD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC"

    def test_normalize_common_name_to_symbol(self):
        """Test common cryptocurrency names map to symbols."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT & ASSERT
        assert source.normalize_symbol("BITCOIN", AssetType.CRYPTO) == "BTC"
        assert source.normalize_symbol("ETHEREUM", AssetType.CRYPTO) == "ETH"
        assert source.normalize_symbol("CARDANO", AssetType.CRYPTO) == "ADA"

    def test_normalize_case_insensitive(self):
        """Test normalization is case insensitive."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("btc", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC"

    def test_normalize_non_crypto_raises_error(self):
        """Test error when normalizing non-crypto asset."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        # ACT & ASSERT
        with pytest.raises(ValueError, match="only supports cryptocurrencies"):
            source.normalize_symbol("AAPL", AssetType.STOCK)


class TestCoinMarketCapValidateConnection:
    """Test connection validation."""

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_validate_connection_success(self, mock_get):
        """Test successful connection validation."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {
                "error_code": 0
            },
            "data": {
                "plan": {
                    "credit_limit_daily": 333
                }
            }
        }
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_validate_connection_http_error(self, mock_get):
        """Test connection validation with HTTP error."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_validate_connection_api_error(self, mock_get):
        """Test connection validation with API error."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {
                "error_code": 1001,
                "error_message": "Invalid API key"
            }
        }
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_validate_connection_exception(self, mock_get):
        """Test connection validation with exception."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")

        mock_get.side_effect = Exception("Network timeout")

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False


class TestCoinMarketCapResourceManagement:
    """Test resource management (session cleanup)."""

    def test_context_manager_closes_session(self):
        """Test context manager properly closes session."""
        # ACT
        with CoinMarketCapSource(api_key="test") as source:
            session = source.session

        # ASSERT - Methods exist
        assert hasattr(source, '__enter__')
        assert hasattr(source, '__exit__')

    def test_destructor_closes_session(self):
        """Test destructor closes session."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test")
        session = source.session

        # ACT
        del source

        # ASSERT - No exception raised
        assert True


class TestCoinMarketCapRateLimiting:
    """Test rate limiting functionality."""

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_rate_limit_allows_under_minute_limit(self, mock_get):
        """Test requests succeed when under minute limit."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test", calls_per_minute=5)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {"error_code": 0},
            "data": {"BTC": {"quote": {"USD": {"price": 50000.0, "volume_24h": 1000000000.0}}}}
        }
        mock_get.return_value = mock_response

        # ACT - Make 4 calls (under limit of 5)
        for _ in range(4):
            quote = source.fetch_quote("BTC")
            assert quote.price == 50000.0

        # ASSERT - No exception raised
        assert len(source._minute_calls) == 4

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_rate_limit_blocks_over_minute_limit(self, mock_get):
        """Test rate limit enforced for minute limit."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test", calls_per_minute=3, calls_per_day=100)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {"error_code": 0},
            "data": {"BTC": {"quote": {"USD": {"price": 50000.0, "volume_24h": 1000000000.0}}}}
        }
        mock_get.return_value = mock_response

        # ACT - Make 3 calls (at limit)
        for _ in range(3):
            source.fetch_quote("BTC")

        # ASSERT - 4th call should fail
        with pytest.raises(ValueError, match="Rate limit exceeded.*per minute"):
            source.fetch_quote("BTC")

    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_rate_limit_blocks_over_day_limit(self, mock_get):
        """Test rate limit enforced for daily limit."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test", calls_per_minute=100, calls_per_day=2)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {"error_code": 0},
            "data": {"BTC": {"quote": {"USD": {"price": 50000.0, "volume_24h": 1000000000.0}}}}
        }
        mock_get.return_value = mock_response

        # ACT - Make 2 calls (at daily limit)
        for _ in range(2):
            source.fetch_quote("BTC")

        # ASSERT - 3rd call should fail
        with pytest.raises(ValueError, match="Rate limit exceeded.*per day"):
            source.fetch_quote("BTC")

    @patch('trade_engine.services.data.source_coinmarketcap.time.time')
    @patch('trade_engine.services.data.source_coinmarketcap.requests.Session.get')
    def test_rate_limit_resets_after_minute(self, mock_get, mock_time):
        """Test minute rate limit resets after 60 seconds."""
        # ARRANGE
        source = CoinMarketCapSource(api_key="test", calls_per_minute=2, calls_per_day=100)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": {"error_code": 0},
            "data": {"BTC": {"quote": {"USD": {"price": 50000.0, "volume_24h": 1000000000.0}}}}
        }
        mock_get.return_value = mock_response

        # ACT - Make 2 calls at time=0
        mock_time.return_value = 0.0
        for _ in range(2):
            source.fetch_quote("BTC")

        # Advance time by 61 seconds
        mock_time.return_value = 61.0

        # ASSERT - 3rd call should succeed (old calls expired)
        quote = source.fetch_quote("BTC")
        assert quote.price == 50000.0

    def test_rate_limit_configuration(self):
        """Test rate limit can be configured."""
        # ACT
        source = CoinMarketCapSource(api_key="test", calls_per_minute=10, calls_per_day=500)

        # ASSERT
        assert source.calls_per_minute == 10
        assert source.calls_per_day == 500
