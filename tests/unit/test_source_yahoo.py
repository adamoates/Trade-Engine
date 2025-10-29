"""Unit tests for Yahoo Finance data source adapter."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from trade_engine.services.data.types import (
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)
from trade_engine.adapters.data_sources.yahoo import YahooFinanceSource


class TestYahooFinanceInit:
    """Test YahooFinanceSource initialization."""

    def test_source_initializes_successfully(self):
        """Test source can be initialized."""
        # ACT
        source = YahooFinanceSource()

        # ASSERT
        assert source.source_type == DataSourceType.YAHOO_FINANCE
        assert AssetType.STOCK in source.supported_asset_types
        assert AssetType.CRYPTO in source.supported_asset_types

    def test_source_type_is_yahoo_finance(self):
        """Test source_type property."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        source_type = source.source_type

        # ASSERT
        assert source_type == DataSourceType.YAHOO_FINANCE

    def test_supported_asset_types_includes_all(self):
        """Test all expected asset types are supported."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        supported = source.supported_asset_types

        # ASSERT
        assert AssetType.STOCK in supported
        assert AssetType.ETF in supported
        assert AssetType.INDEX in supported
        assert AssetType.CRYPTO in supported
        assert AssetType.FOREX in supported


class TestYahooFetchOHLCV:
    """Test OHLCV data fetching."""

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_ohlcv_returns_candles(self, mock_ticker):
        """Test fetching OHLCV returns correct data structure."""
        # ARRANGE
        source = YahooFinanceSource()

        # Mock DataFrame with timezone-aware index
        mock_df = pd.DataFrame({
            'Open': [100.0, 102.0],
            'High': [105.0, 107.0],
            'Low': [99.0, 101.0],
            'Close': [102.0, 105.0],
            'Volume': [1000.0, 1100.0]
        })
        # Create timezone-aware timestamps
        tz_utc = timezone.utc
        mock_df.index = pd.DatetimeIndex([
            datetime(2025, 1, 1, 0, 0, 0, tzinfo=tz_utc),
            datetime(2025, 1, 1, 0, 1, 0, tzinfo=tz_utc)
        ])

        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        start = datetime(2025, 1, 1, tzinfo=tz_utc)
        end = datetime(2025, 1, 2, tzinfo=tz_utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "1m", start, end)

        # ASSERT
        assert len(candles) == 2
        assert candles[0].open == 100.0
        assert candles[0].close == 102.0
        assert candles[0].volume == 1000.0
        assert candles[0].source == DataSourceType.YAHOO_FINANCE
        assert candles[0].symbol == "AAPL"

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_ohlcv_empty_response(self, mock_ticker):
        """Test handling of empty data response."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()  # Empty DataFrame
        mock_ticker.return_value = mock_instance

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("INVALID", "1m", start, end)

        # ASSERT
        assert candles == []

    def test_fetch_ohlcv_invalid_interval(self):
        """Test error handling for unsupported interval."""
        # ARRANGE
        source = YahooFinanceSource()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Unsupported interval"):
            source.fetch_ohlcv("AAPL", "3m", start, end)

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_ohlcv_uses_correct_interval(self, mock_ticker):
        """Test interval mapping to yfinance format."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("AAPL", "1h", start, end)

        # ASSERT
        mock_instance.history.assert_called_once()
        call_kwargs = mock_instance.history.call_args[1]
        assert call_kwargs['interval'] == "1h"

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_ohlcv_converts_timestamps_correctly(self, mock_ticker):
        """Test timestamp conversion to milliseconds."""
        # ARRANGE
        source = YahooFinanceSource()

        # Mock DataFrame
        mock_df = pd.DataFrame({
            'Open': [100.0],
            'High': [105.0],
            'Low': [99.0],
            'Close': [102.0],
            'Volume': [1000.0]
        })
        # Specific timestamp to test
        expected_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_df.index = pd.DatetimeIndex([expected_ts])

        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 2, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("AAPL", "1d", start, end)

        # ASSERT
        expected_ts_ms = int(expected_ts.timestamp() * 1000)
        assert candles[0].timestamp == expected_ts_ms


class TestYahooFetchQuote:
    """Test real-time quote fetching."""

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_quote_returns_current_price(self, mock_ticker):
        """Test fetching current quote."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {
            'currentPrice': 150.25,
            'bid': 150.20,
            'ask': 150.30,
            'volume': 1000000
        }
        mock_ticker.return_value = mock_instance

        # ACT
        quote = source.fetch_quote("AAPL")

        # ASSERT
        assert quote.symbol == "AAPL"
        assert quote.price == 150.25
        assert quote.bid == 150.20
        assert quote.ask == 150.30
        assert quote.volume_24h == 1000000
        assert quote.source == DataSourceType.YAHOO_FINANCE

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_quote_fallback_to_regular_market_price(self, mock_ticker):
        """Test price fallback when currentPrice not available."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {
            'regularMarketPrice': 150.25
        }
        mock_ticker.return_value = mock_instance

        # ACT
        quote = source.fetch_quote("AAPL")

        # ASSERT
        assert quote.price == 150.25

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_quote_fallback_to_previous_close(self, mock_ticker):
        """Test price fallback to previousClose."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {
            'previousClose': 150.25
        }
        mock_ticker.return_value = mock_instance

        # ACT
        quote = source.fetch_quote("AAPL")

        # ASSERT
        assert quote.price == 150.25

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_fetch_quote_no_price_raises_error(self, mock_ticker):
        """Test error when no price data available."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {}  # No price data
        mock_ticker.return_value = mock_instance

        # ACT & ASSERT
        with pytest.raises(ValueError, match="No price data available"):
            source.fetch_quote("INVALID")


class TestYahooNormalizeSymbol:
    """Test symbol normalization."""

    def test_normalize_crypto_adds_usd_suffix(self):
        """Test crypto normalization adds -USD suffix."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("BTC", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC-USD"

    def test_normalize_crypto_replaces_usdt_with_usd(self):
        """Test USDT is replaced with USD."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("BTCUSDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC-USD"

    def test_normalize_crypto_already_has_usd_suffix(self):
        """Test already normalized crypto symbol."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("BTC-USD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC-USD"

    def test_normalize_stock_no_change(self):
        """Test stock symbols are uppercased."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("aapl", AssetType.STOCK)

        # ASSERT
        assert normalized == "AAPL"

    def test_normalize_index_adds_caret_prefix(self):
        """Test index normalization adds ^ prefix."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("SPX", AssetType.INDEX)

        # ASSERT
        assert normalized == "^GSPC"

    def test_normalize_index_common_mappings(self):
        """Test common index symbol mappings."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT & ASSERT
        assert source.normalize_symbol("SP500", AssetType.INDEX) == "^GSPC"
        assert source.normalize_symbol("DOW", AssetType.INDEX) == "^DJI"
        assert source.normalize_symbol("NASDAQ", AssetType.INDEX) == "^IXIC"

    def test_normalize_removes_slashes(self):
        """Test slash removal in symbols."""
        # ARRANGE
        source = YahooFinanceSource()

        # ACT
        normalized = source.normalize_symbol("BTC/USD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "BTC-USD"


class TestYahooValidateConnection:
    """Test connection validation."""

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_validate_connection_success(self, mock_ticker):
        """Test successful connection validation."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {'currentPrice': 450.0}
        mock_ticker.return_value = mock_instance

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_validate_connection_with_regular_market_price(self, mock_ticker):
        """Test connection validation with regularMarketPrice."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {'regularMarketPrice': 450.0}
        mock_ticker.return_value = mock_instance

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_validate_connection_failure(self, mock_ticker):
        """Test connection validation failure."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_instance = MagicMock()
        mock_instance.info = {}  # No price data
        mock_ticker.return_value = mock_instance

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('trade_engine.services.data.source_yahoo.yf.Ticker')
    def test_validate_connection_exception(self, mock_ticker):
        """Test connection validation with exception."""
        # ARRANGE
        source = YahooFinanceSource()

        mock_ticker.side_effect = Exception("Network error")

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False
