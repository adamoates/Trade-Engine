"""Tests for funding rate service."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from trade_engine.services.data.funding_rate_service import FundingRateService


class TestFundingRateService:
    """Test funding rate service functionality."""

    def test_calculate_funding_cost(self):
        """Test funding cost calculation."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("0.5"),
            entry_price=Decimal("50000"),
            funding_rate=Decimal("0.0001"),
            periods=1,
        )

        assert cost == Decimal("2.50")  # 0.5 * 50000 * 0.0001 = 2.50

    def test_calculate_funding_cost_negative_rate(self):
        """Test funding income with negative rate."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("1.0"),
            entry_price=Decimal("30000"),
            funding_rate=Decimal("-0.0001"),
            periods=1,
        )

        assert cost == Decimal("-3.00")  # Negative = income

    def test_calculate_funding_cost_multiple_periods(self):
        """Test 24-hour funding cost (3 periods)."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("0.1"),
            entry_price=Decimal("60000"),
            funding_rate=Decimal("0.0001"),
            periods=3,  # 24 hours
        )

        assert cost == Decimal("1.80")  # 0.1 * 60000 * 0.0001 * 3 = 1.80

    def test_calculate_funding_cost_zero_rate(self):
        """Test funding cost with zero rate."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("1.0"),
            entry_price=Decimal("50000"),
            funding_rate=Decimal("0"),
            periods=1,
        )

        assert cost == Decimal("0.00")

    def test_calculate_funding_cost_large_position(self):
        """Test funding cost with larger position."""
        service = FundingRateService()

        cost = service.calculate_funding_cost(
            position_size=Decimal("10.0"),
            entry_price=Decimal("45000"),
            funding_rate=Decimal("0.0002"),
            periods=1,
        )

        # 10 * 45000 * 0.0002 = 90
        assert cost == Decimal("90.00")

    @patch("requests.get")
    def test_get_current_funding_rate(self, mock_get):
        """Test fetching current funding rate."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1635724800000,
            }
        ]
        mock_get.return_value = mock_response

        service = FundingRateService()
        rate = service.get_current_funding_rate("BTCUSDT")

        assert rate == Decimal("0.0001")

    @patch("requests.get")
    def test_get_current_funding_rate_no_data(self, mock_get):
        """Test fetching funding rate when no data available."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        service = FundingRateService()
        rate = service.get_current_funding_rate("BTCUSDT")

        assert rate == Decimal("0")

    @patch("requests.get")
    def test_get_current_funding_rate_api_error(self, mock_get):
        """Test handling of API errors."""
        mock_get.side_effect = Exception("API Error")

        service = FundingRateService()

        with pytest.raises(Exception):
            service.get_current_funding_rate("BTCUSDT")

    def test_estimate_daily_funding(self):
        """Test daily funding estimation."""
        service = FundingRateService()

        # Mock the API call
        service.get_current_funding_rate = Mock(return_value=Decimal("0.0001"))

        daily_cost = service.estimate_daily_funding(
            symbol="BTCUSDT",
            position_size=Decimal("1.0"),
            entry_price=Decimal("50000"),
        )

        # 1 BTC * 50k * 0.0001 * 3 periods = 15 USDT
        assert daily_cost == Decimal("15.00")

    def test_estimate_daily_funding_high_rate(self):
        """Test daily funding with high rate."""
        service = FundingRateService()

        # Mock high funding rate
        service.get_current_funding_rate = Mock(return_value=Decimal("0.0005"))

        daily_cost = service.estimate_daily_funding(
            symbol="BTCUSDT",
            position_size=Decimal("0.5"),
            entry_price=Decimal("60000"),
        )

        # 0.5 * 60000 * 0.0005 * 3 = 45 USDT
        assert daily_cost == Decimal("45.00")

    @patch("requests.get")
    def test_get_historical_funding(self, mock_get):
        """Test fetching historical funding rates."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1635724800000,
            },
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00015000",
                "fundingTime": 1635753600000,
            },
        ]
        mock_get.return_value = mock_response

        service = FundingRateService()
        history = service.get_historical_funding("BTCUSDT", limit=2)

        assert len(history) == 2
        assert history[0]["fundingRate"] == "0.00010000"
        assert history[1]["fundingRate"] == "0.00015000"

    def test_funding_cost_precision(self):
        """Test that funding costs are properly quantized."""
        service = FundingRateService()

        # Test with value that would have many decimal places
        cost = service.calculate_funding_cost(
            position_size=Decimal("0.123"),
            entry_price=Decimal("45678.90"),
            funding_rate=Decimal("0.000123"),
            periods=1,
        )

        # Result should be quantized to 2 decimal places
        assert str(cost).count(".") == 1
        assert len(str(cost).split(".")[1]) == 2
