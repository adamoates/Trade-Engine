"""
Tests for Web3 data source signals.

Tests use real API calls (free tier) to validate integration.
Can be run with --slow flag or mocked for fast unit tests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from app.data.web3_signals import (
    Web3DataSource,
    GasData,
    LiquidityData,
    FundingRateData,
    Web3Signal,
    get_web3_signal
)


class TestWeb3DataSourceInit:
    """Test Web3DataSource initialization."""

    def test_init_with_defaults(self):
        """Test default initialization."""
        source = Web3DataSource()

        assert source.timeout == 5
        assert source.retry_attempts == 2
        assert source.session is not None

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        source = Web3DataSource(timeout=10, retry_attempts=3)

        assert source.timeout == 10
        assert source.retry_attempts == 3


class TestGasPrices:
    """Test gas price fetching from Etherscan."""

    @patch('app.data.web3_signals.requests.Session')
    def test_get_gas_prices_success(self, mock_session_class):
        """Test successful gas price fetch."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": {
                "SafeGasPrice": "25",
                "ProposeGasPrice": "30",
                "FastGasPrice": "35"
            }
        }
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        gas = source.get_gas_prices()

        assert gas is not None
        assert isinstance(gas, GasData)
        assert gas.safe_gas_price == 25.0
        assert gas.propose_gas_price == 30.0
        assert gas.fast_gas_price == 35.0
        assert isinstance(gas.timestamp, datetime)

    @patch('app.data.web3_signals.requests.Session')
    def test_get_gas_prices_api_failure(self, mock_session_class):
        """Test gas price fetch with API failure."""
        mock_session = MagicMock()
        mock_session.get.return_value.json.return_value = {
            "status": "0",
            "message": "NOTOK"
        }
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        gas = source.get_gas_prices()

        assert gas is None

    @patch('app.data.web3_signals.requests.Session')
    def test_get_gas_prices_timeout(self, mock_session_class):
        """Test gas price fetch with timeout."""
        import requests

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.Timeout()
        mock_session_class.return_value = mock_session

        source = Web3DataSource(retry_attempts=1)
        gas = source.get_gas_prices()

        assert gas is None


class TestDEXLiquidity:
    """Test DEX liquidity fetching from The Graph."""

    @patch('app.data.web3_signals.requests.Session')
    def test_get_dex_liquidity_success(self, mock_session_class):
        """Test successful liquidity fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "pool": {
                    "token0": {"symbol": "WBTC"},
                    "token1": {"symbol": "USDC"},
                    "liquidity": "123456789",
                    "volumeUSD": "5000000.50",
                    "feeTier": "3000"
                }
            }
        }
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        liquidity = source.get_dex_liquidity("WBTC/USDC")

        assert liquidity is not None
        assert isinstance(liquidity, LiquidityData)
        assert liquidity.token0 == "WBTC"
        assert liquidity.token1 == "USDC"
        assert liquidity.liquidity == 123456789.0
        assert liquidity.volume_24h_usd == 5000000.50
        assert isinstance(liquidity.timestamp, datetime)

    def test_get_dex_liquidity_unknown_pool(self):
        """Test liquidity fetch with unknown pool."""
        source = Web3DataSource()
        liquidity = source.get_dex_liquidity("INVALID/POOL")

        assert liquidity is None

    @patch('app.data.web3_signals.requests.Session')
    def test_get_dex_liquidity_graphql_error(self, mock_session_class):
        """Test liquidity fetch with GraphQL error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errors": [{"message": "Query failed"}]
        }
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        liquidity = source.get_dex_liquidity("WBTC/USDC")

        assert liquidity is None


class TestFundingRates:
    """Test funding rate fetching from dYdX."""

    @patch('app.data.web3_signals.requests.Session')
    def test_get_funding_rate_success(self, mock_session_class):
        """Test successful funding rate fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "market": {
                "nextFundingRate": "0.00125",
                "nextFundingAt": "2025-10-24T08:00:00.000Z"
            }
        }
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        funding = source.get_funding_rate("BTC-USD")

        assert funding is not None
        assert isinstance(funding, FundingRateData)
        assert funding.symbol == "BTC-USD"
        assert funding.funding_rate == 0.00125
        assert isinstance(funding.next_funding_time, datetime)
        assert isinstance(funding.timestamp, datetime)

    @patch('app.data.web3_signals.requests.Session')
    def test_get_funding_rate_negative(self, mock_session_class):
        """Test funding rate fetch with negative rate (bullish)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "market": {
                "nextFundingRate": "-0.00250",
                "nextFundingAt": "2025-10-24T08:00:00.000Z"
            }
        }
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        funding = source.get_funding_rate("BTC-USD")

        assert funding.funding_rate == -0.00250  # Negative = bullish

    @patch('app.data.web3_signals.requests.Session')
    def test_get_funding_rate_api_failure(self, mock_session_class):
        """Test funding rate fetch with API failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        source = Web3DataSource()
        funding = source.get_funding_rate("BTC-USD")

        assert funding is None


class TestCombinedSignal:
    """Test combined signal generation."""

    def test_combined_signal_all_bullish(self):
        """Test combined signal with all bullish indicators."""
        source = Web3DataSource()

        # Mock all methods to return bullish data
        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=20.0,
            propose_gas_price=25.0,
            fast_gas_price=30.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_dex_liquidity = Mock(return_value=LiquidityData(
            pool_address="0x...",
            token0="WBTC",
            token1="USDC",
            liquidity=1000000.0,
            volume_24h_usd=5000000.0,  # High volume
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=-0.015,  # Negative = bullish
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        signal = source.get_combined_signal()

        assert signal.signal == "BUY"
        assert signal.score > 0
        assert signal.confidence == 1.0  # All 3 signals available

    def test_combined_signal_all_bearish(self):
        """Test combined signal with all bearish indicators."""
        source = Web3DataSource()

        # Mock all methods to return bearish data
        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=100.0,
            propose_gas_price=120.0,  # High gas = bearish
            fast_gas_price=150.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_dex_liquidity = Mock(return_value=LiquidityData(
            pool_address="0x...",
            token0="WBTC",
            token1="USDC",
            liquidity=1000000.0,
            volume_24h_usd=500000.0,  # Low volume = bearish
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=0.020,  # Positive = bearish
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        signal = source.get_combined_signal()

        assert signal.signal == "SELL"
        assert signal.score < 0
        assert signal.confidence == 1.0

    def test_combined_signal_neutral(self):
        """Test combined signal with neutral/conflicting indicators."""
        source = Web3DataSource()

        # Mock neutral data
        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=20.0,
            propose_gas_price=25.0,  # Normal gas
            fast_gas_price=30.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_dex_liquidity = Mock(return_value=LiquidityData(
            pool_address="0x...",
            token0="WBTC",
            token1="USDC",
            liquidity=1000000.0,
            volume_24h_usd=2000000.0,  # Adequate volume
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=0.005,  # Near zero = neutral
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        signal = source.get_combined_signal()

        assert signal.signal == "NEUTRAL"
        assert signal.score == 0

    def test_combined_signal_partial_data(self):
        """Test combined signal with some data sources failing."""
        source = Web3DataSource()

        # Some methods succeed, some fail
        source.get_gas_prices = Mock(return_value=None)  # Failed
        source.get_dex_liquidity = Mock(return_value=None)  # Failed

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=-0.015,  # Only this works
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        signal = source.get_combined_signal()

        # Should still work with partial data
        assert signal.confidence < 1.0  # Confidence reduced
        assert signal.confidence == 1.0 / 3.0  # Only 1 of 3 signals


class TestVolatilityDetection:
    """Test high volatility detection."""

    def test_high_volatility_from_gas(self):
        """Test volatility detection from high gas prices."""
        source = Web3DataSource()

        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=100.0,
            propose_gas_price=150.0,  # Very high
            fast_gas_price=200.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=0.005,
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        assert source.is_high_volatility() is True

    def test_high_volatility_from_funding(self):
        """Test volatility detection from extreme funding rate."""
        source = Web3DataSource()

        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=20.0,
            propose_gas_price=25.0,
            fast_gas_price=30.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=0.025,  # 2.5% = extreme
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        assert source.is_high_volatility() is True

    def test_normal_volatility(self):
        """Test normal volatility conditions."""
        source = Web3DataSource()

        source.get_gas_prices = Mock(return_value=GasData(
            safe_gas_price=20.0,
            propose_gas_price=25.0,
            fast_gas_price=30.0,
            timestamp=datetime.now(timezone.utc)
        ))

        source.get_funding_rate = Mock(return_value=FundingRateData(
            symbol="BTC-USD",
            funding_rate=0.005,
            next_funding_time=datetime.now(timezone.utc),
            timestamp=datetime.now(timezone.utc)
        ))

        assert source.is_high_volatility() is False


class TestConvenienceFunction:
    """Test convenience helper function."""

    @patch('app.data.web3_signals.Web3DataSource')
    def test_get_web3_signal(self, mock_source_class):
        """Test get_web3_signal convenience function."""
        mock_source = MagicMock()
        mock_signal = Web3Signal(
            score=1,
            gas_data=None,
            liquidity_data=None,
            funding_data=None,
            signal="BUY",
            confidence=1.0,
            timestamp=datetime.now(timezone.utc)
        )
        mock_source.get_combined_signal.return_value = mock_signal
        mock_source_class.return_value = mock_source

        signal = get_web3_signal()

        assert signal.signal == "BUY"
        assert signal.score == 1


# Integration tests (run with --slow flag or skip in CI)
@pytest.mark.slow
class TestRealAPIIntegration:
    """
    Integration tests with real APIs.

    Run with: pytest tests/unit/test_web3_signals.py -v -m slow
    """

    def test_real_gas_prices(self):
        """Test real gas price fetch from Etherscan."""
        source = Web3DataSource(timeout=10)
        gas = source.get_gas_prices()

        # Should succeed with real API
        if gas:  # May fail if rate limited
            assert gas.safe_gas_price > 0
            assert gas.propose_gas_price >= gas.safe_gas_price
            assert gas.fast_gas_price >= gas.propose_gas_price

    def test_real_dex_liquidity(self):
        """Test real liquidity fetch from The Graph."""
        source = Web3DataSource(timeout=10)
        liquidity = source.get_dex_liquidity("WBTC/USDC")

        if liquidity:  # May fail if rate limited
            assert liquidity.liquidity > 0
            assert liquidity.volume_24h_usd >= 0

    def test_real_funding_rate(self):
        """Test real funding rate fetch from dYdX."""
        source = Web3DataSource(timeout=10)
        funding = source.get_funding_rate("BTC-USD")

        if funding:  # May fail if market closed or API down
            assert -1.0 < funding.funding_rate < 1.0  # Realistic range

    def test_real_combined_signal(self):
        """Test real combined signal generation."""
        source = Web3DataSource(timeout=10)
        signal = source.get_combined_signal()

        # Should always return a signal (even if some sources fail)
        assert signal is not None
        assert signal.signal in ["BUY", "SELL", "NEUTRAL"]
        assert 0.0 <= signal.confidence <= 1.0
