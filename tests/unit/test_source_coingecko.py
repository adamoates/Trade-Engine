"""Unit tests for CoinGecko data source adapter."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests

from mft.services.data.types import (
    DataSourceType,
    AssetType,
    OHLCV,
    Quote
)
from mft.services.data.source_coingecko import CoinGeckoSource


class TestCoinGeckoInit:
    """Test CoinGeckoSource initialization."""

    def test_source_initializes_without_api_key(self):
        """Test source can be initialized without API key."""
        # ACT
        source = CoinGeckoSource()

        # ASSERT
        assert source.source_type == DataSourceType.COINGECKO
        assert source.api_key is None
        assert "User-Agent" in source.session.headers

    def test_source_initializes_with_api_key(self):
        """Test source initialization with API key."""
        # ACT
        source = CoinGeckoSource(api_key="test_key_123")

        # ASSERT
        assert source.api_key == "test_key_123"
        assert source.session.headers["x-cg-pro-api-key"] == "test_key_123"

    def test_source_type_is_coingecko(self):
        """Test source_type property."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        source_type = source.source_type

        # ASSERT
        assert source_type == DataSourceType.COINGECKO

    def test_supported_asset_types_only_crypto(self):
        """Test only crypto assets are supported."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        supported = source.supported_asset_types

        # ASSERT
        assert supported == [AssetType.CRYPTO]
        assert AssetType.STOCK not in supported


class TestCoinGeckoFetchOHLCV:
    """Test OHLCV data fetching."""

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_ohlcv_returns_candles(self, mock_get):
        """Test fetching OHLCV returns correct data structure."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "prices": [
                [1609459200000, 29000.0],
                [1609545600000, 29500.0]
            ],
            "total_volumes": [
                [1609459200000, 1000000000.0],
                [1609545600000, 1100000000.0]
            ]
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 3, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("bitcoin", "1d", start, end)

        # ASSERT
        assert len(candles) == 2
        assert candles[0].close == 29000.0
        assert candles[0].volume == 1000000000.0
        assert candles[0].source == DataSourceType.COINGECKO
        # CoinGecko synthetic OHLC: O=H=L=C
        assert candles[0].open == candles[0].close
        assert candles[0].high == candles[0].close
        assert candles[0].low == candles[0].close

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_ohlcv_with_limit(self, mock_get):
        """Test limit parameter restricts returned candles."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "prices": [[i * 1000, 100.0 + i] for i in range(100)],
            "total_volumes": [[i * 1000, 1000000.0] for i in range(100)]
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        candles = source.fetch_ohlcv("bitcoin", "1d", start, end, limit=5)

        # ASSERT
        assert len(candles) == 5

    def test_fetch_ohlcv_invalid_interval(self):
        """Test error handling for unsupported interval."""
        # ARRANGE
        source = CoinGeckoSource()
        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="CoinGecko only supports intervals"):
            source.fetch_ohlcv("bitcoin", "5m", start, end)

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_ohlcv_daily_interval(self, mock_get):
        """Test daily interval is correctly mapped."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "prices": [[1609459200000, 29000.0]],
            "total_volumes": [[1609459200000, 1000000000.0]]
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 10, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("bitcoin", "1d", start, end)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['interval'] == "daily"

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_ohlcv_hourly_interval(self, mock_get):
        """Test hourly interval is correctly mapped."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "prices": [[1609459200000, 29000.0]],
            "total_volumes": [[1609459200000, 1000000000.0]]
        }
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT
        source.fetch_ohlcv("bitcoin", "1h", start, end)

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['interval'] == "hourly"

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_ohlcv_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
        mock_get.return_value = mock_response

        start = datetime(2021, 1, 1, tzinfo=timezone.utc)
        end = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_ohlcv("bitcoin", "1d", start, end)


class TestCoinGeckoFetchQuote:
    """Test real-time quote fetching."""

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_quote_returns_current_price(self, mock_get):
        """Test fetching current quote."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bitcoin": {
                "usd": 66500.0,
                "usd_24h_vol": 25000000000.0,
                "last_updated_at": 1640000000
            }
        }
        mock_get.return_value = mock_response

        # ACT
        quote = source.fetch_quote("bitcoin")

        # ASSERT
        assert quote.symbol == "bitcoin"
        assert quote.price == 66500.0
        assert quote.volume_24h == 25000000000.0
        assert quote.timestamp == 1640000000 * 1000
        assert quote.source == DataSourceType.COINGECKO

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_quote_no_coin_data(self, mock_get):
        """Test error when coin not found."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Empty response
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(ValueError, match="No data for"):
            source.fetch_quote("invalid-coin")

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_quote_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        # ACT & ASSERT
        with pytest.raises(requests.HTTPError):
            source.fetch_quote("bitcoin")

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_fetch_quote_uses_correct_params(self, mock_get):
        """Test API call parameters."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bitcoin": {
                "usd": 66500.0
            }
        }
        mock_get.return_value = mock_response

        # ACT
        source.fetch_quote("bitcoin")

        # ASSERT
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['params']['ids'] == "bitcoin"
        assert call_kwargs['params']['vs_currencies'] == "usd"
        assert call_kwargs['params']['include_24hr_vol'] == "true"


class TestCoinGeckoNormalizeSymbol:
    """Test symbol normalization."""

    def test_normalize_btc_to_bitcoin(self):
        """Test BTC is normalized to bitcoin."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        normalized = source.normalize_symbol("BTC", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "bitcoin"

    def test_normalize_eth_to_ethereum(self):
        """Test ETH is normalized to ethereum."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        normalized = source.normalize_symbol("ETH", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "ethereum"

    def test_normalize_removes_usdt_suffix(self):
        """Test USDT suffix is removed."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        normalized = source.normalize_symbol("BTCUSDT", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "bitcoin"

    def test_normalize_removes_usd_suffix(self):
        """Test USD suffix is removed."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        normalized = source.normalize_symbol("BTC-USD", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "bitcoin"

    def test_normalize_common_symbols(self):
        """Test common symbol mappings."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT & ASSERT
        assert source.normalize_symbol("SOL", AssetType.CRYPTO) == "solana"
        assert source.normalize_symbol("ADA", AssetType.CRYPTO) == "cardano"
        assert source.normalize_symbol("DOT", AssetType.CRYPTO) == "polkadot"
        assert source.normalize_symbol("MATIC", AssetType.CRYPTO) == "matic-network"

    def test_normalize_unknown_symbol_uses_lowercase(self):
        """Test unknown symbols are lowercased."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        normalized = source.normalize_symbol("NEWCOIN", AssetType.CRYPTO)

        # ASSERT
        assert normalized == "newcoin"

    def test_normalize_non_crypto_raises_error(self):
        """Test error when normalizing non-crypto asset."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT & ASSERT
        with pytest.raises(ValueError, match="only supports cryptocurrencies"):
            source.normalize_symbol("AAPL", AssetType.STOCK)


class TestCoinGeckoValidateConnection:
    """Test connection validation."""

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_validate_connection_success(self, mock_get):
        """Test successful connection validation."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is True
        assert "/ping" in mock_get.call_args[0][0]

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_validate_connection_failure(self, mock_get):
        """Test connection validation failure."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False

    @patch('app.data.source_coingecko.requests.Session.get')
    def test_validate_connection_exception(self, mock_get):
        """Test connection validation with exception."""
        # ARRANGE
        source = CoinGeckoSource()

        mock_get.side_effect = Exception("Network timeout")

        # ACT
        result = source.validate_connection()

        # ASSERT
        assert result is False


class TestCoinGeckoSymbolToCoinId:
    """Test internal symbol to coin ID conversion."""

    def test_symbol_to_coin_id_removes_common_suffixes(self):
        """Test suffix removal."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT & ASSERT
        assert source._symbol_to_coin_id("BTC/USDT") == "bitcoin"
        assert source._symbol_to_coin_id("ETH-USD") == "ethereum"
        assert source._symbol_to_coin_id("BTC/USD") == "bitcoin"

    def test_symbol_to_coin_id_handles_uppercase(self):
        """Test case normalization."""
        # ARRANGE
        source = CoinGeckoSource()

        # ACT
        result = source._symbol_to_coin_id("btc")

        # ASSERT
        assert result == "bitcoin"
