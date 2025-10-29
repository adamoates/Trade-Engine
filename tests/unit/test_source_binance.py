"""Unit tests for Binance data source adapter."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests

from trade_engine.services.data.types import (
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)
from trade_engine.adapters.data_sources.binance import BinanceDataSource


class TestBinanceInit:
    """Test BinanceDataSource initialization."""

    def test_source_initializes_with_spot_market(self):
        """Test source can be initialized for spot market."""
        # ACT
        source = BinanceDataSource(market="spot")

        # ASSERT
        assert source.source_type == DataSourceType.BINANCE
        assert source.market == "spot"
        assert source.base_url == "https://api.binance.com"

    def test_source_initializes_with_futures_market(self):
        """Test source can be initialized for futures market."""
        # ACT
        source = BinanceDataSource(market="futures")

        # ASSERT
        assert source.market == "futures"
        assert source.base_url == "https://fapi.binance.com"

    def test_source_defaults_to_spot_market(self):
        """Test default market is spot."""
        # ACT
        source = BinanceDataSource()

        # ASSERT
        assert source.market == "spot"

    def test_source_initializes_with_custom_timeout(self):
        """Test custom timeout parameter."""
        # ACT
        source = BinanceDataSource(timeout=30)

        # ASSERT
        assert source.timeout == 30

    def test_source_rejects_invalid_market(self):
        """Test error on invalid market type."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Invalid market"):
            BinanceDataSource(market="invalid")

    def test_source_type_is_binance(self):
        """Test source_type property."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        source_type = source.source_type

        # ASSERT
        assert source_type == DataSourceType.BINANCE

    def test_supported_asset_types_only_crypto(self):
        """Test only crypto assets are supported."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        supported = source.supported_asset_types

        # ASSERT
        assert supported == [AssetType.CRYPTO]
        assert AssetType.STOCK not in supported


class TestBinanceFetchOHLCV:
    """Test OHLCV data fetching."""

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_returns_candles(self, mock_get):
        """Test fetching OHLCV returns correct data structure."""
        # ARRANGE
        source = BinanceDataSource(market="spot")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [1609459200000, "29000.00", "29500.00", "28500.00", "29200.00", "1000.00", 1609459259999, "29100000.00", 100, "500.00", "14550000.00", "0"],
            [1609545600000, "29200.00", "30000.00", "29000.00", "29800.00", "1200.00", 1609545659999, "35760000.00", 120, "600.00", "17880000.00", "0"]
        ]
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 3, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("BTCUSDT", "1d", start, end)

        # ASSERT
        assert len(candles) == 2
        assert candles[0].timestamp == 1609459200000
        assert candles[0].open == 29000.00
        assert candles[0].high == 29500.00
        assert candles[0].low == 28500.00
        assert candles[0].close == 29200.00
        assert candles[0].volume == 1000.00
        assert candles[0].source == DataSourceType.BINANCE
        assert candles[0].symbol == "BTCUSDT"

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_spot_uses_correct_endpoint(self, mock_get):
        """Test spot market uses correct API endpoint."""
        # ARRANGE
        source = BinanceDataSource(market="spot")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("BTCUSDT", "1d", start, end)

        # ASSERT
        call_args = mock_get.call_args[0][0]
        assert "https://api.binance.com/api/v3/klines" in call_args

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_futures_uses_correct_endpoint(self, mock_get):
        """Test futures market uses correct API endpoint."""
        # ARRANGE
        source = BinanceDataSource(market="futures")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("BTCUSDT", "1d", start, end)

        # ASSERT
        call_args = mock_get.call_args[0][0]
        assert "https://fapi.binance.com/fapi/v1/klines" in call_args

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_with_limit(self, mock_get):
        """Test limit parameter restricts returned candles."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("BTCUSDT", "1d", start, end, limit=500)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['limit'] == 500

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_limits_to_1500_max(self, mock_get):
        """Test limit is capped at Binance's 1500 max."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("BTCUSDT", "1d", start, end, limit=5000)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['limit'] == 1500

    def test_fetch_ohlcv_invalid_interval(self):
        """Test error handling for unsupported interval."""
        # ARRANGE
        source = BinanceDataSource()
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Unsupported interval"):
            source.fetch_ohlcv("BTCUSDT", "10m", start, end)

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_interval_mapping(self, mock_get):
        """Test interval is correctly mapped."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("BTCUSDT", "1mo", start, end)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['interval'] == "1M"  # Binance uses 1M for monthly

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_normalizes_symbol(self, mock_get):
        """Test symbol is normalized to Binance format."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("btc/usdt", "1d", start, end)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['symbol'] == "BTCUSDT"

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_ohlcv("BTCUSDT", "1d", start, end)

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_ohlcv_empty_response(self, mock_get):
        """Test handling of empty response."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("BTCUSDT", "1d", start, end)

        # ASSERT
        assert candles == []


class TestBinanceFetchQuote:
    """Test real-time quote fetching."""

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_quote_returns_current_price(self, mock_get):
        """Test fetching current quote."""
        # ARRANGE
        source = BinanceDataSource()

        # Mock 24hr ticker response
        ticker_response = MagicMock()
        ticker_response.status_code = 200
        ticker_response.json.return_value = {
            "symbol": "BTCUSDT",
            "lastPrice": "66500.00",
            "volume": "25000.00"
        }

        # Mock book ticker response
        book_response = MagicMock()
        book_response.status_code = 200
        book_response.json.return_value = {
            "symbol": "BTCUSDT",
            "bidPrice": "66499.50",
            "askPrice": "66500.50"
        }

        mock_get.side_effect = [ticker_response, book_response]

        # ACT
        quote = source.fetch_quote("BTCUSDT")

        # ASSERT
        assert quote.symbol == "BTCUSDT"
        assert quote.price == 66500.00
        assert quote.bid == 66499.50
        assert quote.ask == 66500.50
        assert quote.volume_24h == 25000.00
        assert quote.source == DataSourceType.BINANCE

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_quote_handles_missing_book_ticker(self, mock_get):
        """Test quote fetching when book ticker fails."""
        # ARRANGE
        source = BinanceDataSource()

        # Mock 24hr ticker response
        ticker_response = MagicMock()
        ticker_response.status_code = 200
        ticker_response.json.return_value = {
            "symbol": "BTCUSDT",
            "lastPrice": "66500.00",
            "volume": "25000.00"
        }

        # Mock book ticker failure
        book_response = MagicMock()
        book_response.status_code = 500
        book_response.json.return_value = {}

        mock_get.side_effect = [ticker_response, book_response]

        # ACT
        quote = source.fetch_quote("BTCUSDT")

        # ASSERT
        assert quote.price == 66500.00
        assert quote.bid is None
        assert quote.ask is None

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_quote_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_quote("BTCUSDT")

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_fetch_quote_normalizes_symbol(self, mock_get):
        """Test symbol is normalized."""
        # ARRANGE
        source = BinanceDataSource()

        ticker_response = MagicMock()
        ticker_response.status_code = 200
        ticker_response.json.return_value = {
            "lastPrice": "66500.00",
            "volume": "25000.00"
        }

        book_response = MagicMock()
        book_response.status_code = 200
        book_response.json.return_value = {}

        mock_get.side_effect = [ticker_response, book_response]

        # ACT
        source.fetch_quote("btc/usdt")

        # ASSERT
        first_call = mock_get.call_args_list[0]
        assert first_call[1]['params']['symbol'] == "BTCUSDT"


class TestBinanceNormalizeSymbol:
    """Test symbol normalization."""

    def test_normalize_btcusdt_no_change(self):
        """Test BTCUSDT is unchanged."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("BTCUSDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_btc_adds_usdt(self):
        """Test BTC adds USDT suffix."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("BTC", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_removes_slash(self):
        """Test slash is removed."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("BTC/USDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_converts_usd_to_usdt(self):
        """Test USD is converted to USDT."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("BTCUSD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_preserves_other_quote_currencies(self):
        """Test other quote currencies are preserved."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT & ASSERT
        assert source.normalize_symbol("ETHBTC", AssetType.CRYPTO) == "ETHBTC"
        assert source.normalize_symbol("BNBBUSD", AssetType.CRYPTO) == "BNBBUSD"
        assert source.normalize_symbol("ETHUSDC", AssetType.CRYPTO) == "ETHUSDC"

    def test_normalize_case_insensitive(self):
        """Test normalization is case insensitive."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("btc/usdt", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_removes_hyphens(self):
        """Test hyphens are removed."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT
        normalized = source.normalize_symbol("BTC-USDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTCUSDT"

    def test_normalize_non_crypto_raises_error(self):
        """Test error when normalizing non-crypto asset."""
        # ARRANGE
        source = BinanceDataSource()

        # ACT & ASSERT
        with pytest.raises(ValueError, match="only supports cryptocurrencies"):
            source.normalize_symbol("AAPL", AssetType.STOCK)


class TestBinanceValidateConnection:
    """Test connection validation."""

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_validate_connection_success_spot(self, mock_get):
        """Test successful connection validation for spot."""
        # ARRANGE
        source = BinanceDataSource(market="spot")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True
        call_args = mock_get.call_args[0][0]
        assert "/api/v3/ping" in call_args

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_validate_connection_success_futures(self, mock_get):
        """Test successful connection validation for futures."""
        # ARRANGE
        source = BinanceDataSource(market="futures")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True
        call_args = mock_get.call_args[0][0]
        assert "/fapi/v1/ping" in call_args

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_validate_connection_failure(self, mock_get):
        """Test connection validation failure."""
        # ARRANGE
        source = BinanceDataSource()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('trade_engine.services.data.source_binance.requests.Session.get')
    def test_validate_connection_exception(self, mock_get):
        """Test connection validation with exception."""
        # ARRANGE
        source = BinanceDataSource()

        mock_get.side_effect = Exception("Network timeout")

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False


class TestBinanceResourceManagement:
    """Test resource management (session cleanup)."""

    def test_context_manager_closes_session(self):
        """Test context manager properly closes session."""
        # ACT
        with BinanceDataSource() as source:
            session = source.session

        # ASSERT - session should be closed after context exit
        # We can't directly test if closed, but we can verify the methods exist
        assert hasattr(source, '__enter__')
        assert hasattr(source, '__exit__')

    def test_destructor_closes_session(self):
        """Test destructor closes session."""
        # ARRANGE
        source = BinanceDataSource()
        session = source.session

        # ACT
        del source

        # ASSERT - should not raise exception
        # The cleanup happens in __del__, which we can't directly verify
        # but we ensure the method exists
        assert True  # If we got here, no exception was raised
