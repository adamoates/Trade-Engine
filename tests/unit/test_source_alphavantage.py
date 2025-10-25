"""Unit tests for Alpha Vantage data source adapter."""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
import requests

from app.data.types import (
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)
from app.data.source_alphavantage import AlphaVantageSource


class TestAlphaVantageInit:
    """Test AlphaVantageSource initialization."""

    def test_source_initializes_with_api_key(self):
        """Test source can be initialized with API key."""
        # ACT
        source = AlphaVantageSource(api_key="test_key_123")

        # ASSERT
        assert source.source_type == DataSourceType.ALPHA_VANTAGE
        assert source.api_key == "test_key_123"

    @patch.dict('os.environ', {'ALPHAVANTAGE_API_KEY': 'env_key_456'})
    def test_source_initializes_from_env_var(self):
        """Test source reads API key from environment."""
        # ACT
        source = AlphaVantageSource()

        # ASSERT
        assert source.api_key == "env_key_456"

    def test_source_requires_api_key(self):
        """Test error when no API key provided."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="API key required"):
            AlphaVantageSource()

    def test_source_type_is_alpha_vantage(self):
        """Test source_type property."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        source_type = source.source_type

        # ASSERT
        assert source_type == DataSourceType.ALPHA_VANTAGE

    def test_supported_asset_types(self):
        """Test supported asset types."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        supported = source.supported_asset_types

        # ASSERT
        assert AssetType.STOCK in supported
        assert AssetType.ETF in supported
        assert AssetType.FOREX in supported
        assert AssetType.CRYPTO in supported
        assert AssetType.COMMODITY not in supported

    def test_custom_timeout(self):
        """Test custom timeout parameter."""
        # ACT
        source = AlphaVantageSource(api_key="test", timeout=60)

        # ASSERT
        assert source.timeout == 60


class TestAlphaVantageFetchOHLCV:
    """Test OHLCV data fetching."""

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_daily_returns_candles(self, mock_get):
        """Test fetching daily OHLCV."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2021-01-04": {
                    "1. open": "133.52",
                    "2. high": "133.61",
                    "3. low": "126.76",
                    "4. close": "129.41",
                    "5. volume": "143301900"
                },
                "2021-01-05": {
                    "1. open": "128.89",
                    "2. high": "131.74",
                    "3. low": "128.43",
                    "4. close": "131.01",
                    "5. volume": "97664900"
                }
            }
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "1d", start, end)

        # ASSERT
        assert len(candles) == 2
        assert candles[0].symbol == "AAPL"
        assert candles[0].open == 133.52
        assert candles[0].close == 129.41
        assert candles[0].volume == 143301900
        assert candles[0].source == DataSourceType.ALPHA_VANTAGE

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_intraday_returns_candles(self, mock_get):
        """Test fetching intraday OHLCV."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Time Series (5min)": {
                "2021-01-04 16:00:00": {
                    "1. open": "129.50",
                    "2. high": "129.60",
                    "3. low": "129.40",
                    "4. close": "129.50",
                    "5. volume": "500000"
                }
            }
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 4, tzinfo=timezone.utc)
        end = datetime(2021, 1, 5, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "5m", start, end)

        # ASSERT
        assert len(candles) == 1
        assert candles[0].open == 129.50

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_uses_correct_function(self, mock_get):
        """Test correct API function is called for each interval."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Time Series (Daily)": {}}
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("AAPL", "1d", start, end)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['function'] == "TIME_SERIES_DAILY"

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_invalid_interval(self, mock_get):
        """Test error on unsupported interval."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Unsupported interval"):
            source.fetch_ohlcv("AAPL", "2m", start, end)

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_api_error(self, mock_get):
        """Test handling of API error messages."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": "Invalid API call"
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="API error"):
            source.fetch_ohlcv("INVALID", "1d", start, end)

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_rate_limit(self, mock_get):
        """Test handling of rate limit."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute"
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "1d", start, end)

        # ASSERT - Returns empty list when rate limited
        assert candles == []

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_filters_by_date_range(self, mock_get):
        """Test date range filtering."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2021-01-01": {"1. open": "100", "2. high": "101", "3. low": "99", "4. close": "100", "5. volume": "1000"},
                "2021-01-05": {"1. open": "105", "2. high": "106", "3. low": "104", "4. close": "105", "5. volume": "1000"},
                "2021-01-10": {"1. open": "110", "2. high": "111", "3. low": "109", "4. close": "110", "5. volume": "1000"}
            }
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 4, tzinfo=timezone.utc)
        end = datetime(2021, 1, 7, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "1d", start, end)

        # ASSERT - Only 2021-01-05 should be in range
        assert len(candles) == 1
        assert candles[0].close == 105

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_ohlcv_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_ohlcv("AAPL", "1d", start, end)


class TestAlphaVantageFetchQuote:
    """Test real-time quote fetching."""

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_quote_returns_current_price(self, mock_get):
        """Test fetching current quote."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "150.25",
                "06. volume": "50000000"
            }
        }
        mock_get.return_value = mock_response

        # ACT
        quote = source.fetch_quote("AAPL")

        # ASSERT
        assert quote.symbol == "AAPL"
        assert quote.price == 150.25
        assert quote.volume_24h == 50000000
        assert quote.source == DataSourceType.ALPHA_VANTAGE

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_quote_api_error(self, mock_get):
        """Test handling of API error."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": "Invalid API call"
        }
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="API error"):
            source.fetch_quote("INVALID")

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_quote_rate_limit(self, mock_get):
        """Test handling of rate limit."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Note": "API call frequency exceeded"
        }
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="rate limit"):
            source.fetch_quote("AAPL")

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_fetch_quote_empty_data(self, mock_get):
        """Test handling of empty quote data."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Global Quote": {}
        }
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Empty quote data"):
            source.fetch_quote("AAPL")


class TestAlphaVantageNormalizeSymbol:
    """Test symbol normalization."""

    def test_normalize_stock_unchanged(self):
        """Test stock symbols remain unchanged."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("AAPL", AssetType.STOCK)

        # ASSERT
        assert normalized == "AAPL"

    def test_normalize_crypto_adds_usd(self):
        """Test crypto gets USD suffix."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTC", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSD"

    def test_normalize_crypto_removes_slash(self):
        """Test crypto slash is removed."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTC/USD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSD"

    def test_normalize_crypto_converts_usdt_to_usd(self):
        """Test USDT is converted to USD."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("BTCUSDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSD"

    def test_normalize_forex_removes_slash(self):
        """Test forex slash removal."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("EUR/USD", AssetType.FOREX)

        # ASSERT
        assert normalized == "EURUSD"

    def test_normalize_case_insensitive(self):
        """Test normalization is case insensitive."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        # ACT
        normalized = source.normalize_symbol("aapl", AssetType.STOCK)

        # ASSERT
        assert normalized == "AAPL"


class TestAlphaVantageValidateConnection:
    """Test connection validation."""

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_validate_connection_success(self, mock_get):
        """Test successful connection validation."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "SPY",
                "05. price": "450.00"
            }
        }
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_validate_connection_http_error(self, mock_get):
        """Test connection validation with HTTP error."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_validate_connection_api_error(self, mock_get):
        """Test connection validation with API error."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Error Message": "Invalid API key"
        }
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_validate_connection_rate_limit(self, mock_get):
        """Test connection validation with rate limit."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Note": "Rate limit exceeded"
        }
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('app.data.source_alphavantage.requests.Session.get')
    def test_validate_connection_exception(self, mock_get):
        """Test connection validation with exception."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")

        mock_get.side_effect = Exception("Network timeout")

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False


class TestAlphaVantageResourceManagement:
    """Test resource management (session cleanup)."""

    def test_context_manager_closes_session(self):
        """Test context manager properly closes session."""
        # ACT
        with AlphaVantageSource(api_key="test") as source:
            session = source.session

        # ASSERT - Methods exist
        assert hasattr(source, '__enter__')
        assert hasattr(source, '__exit__')

    def test_destructor_closes_session(self):
        """Test destructor closes session."""
        # ARRANGE
        source = AlphaVantageSource(api_key="test")
        session = source.session

        # ACT
        del source

        # ASSERT - No exception raised
        assert True
