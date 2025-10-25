"""Unit tests for strategy framework types."""
import pytest
from datetime import datetime, timezone

from trade_engine.services.strategies.types import (
    Insight,
    InsightDirection,
    InsightType,
    TargetPortfolio
)


class TestInsight:
    """Test Insight data class."""

    def test_insight_creates_with_required_fields(self):
        """Test creating insight with minimal fields."""
        # ACT
        insight = Insight(
            symbol="BTC",
            direction=InsightDirection.UP
        )

        # ASSERT
        assert insight.symbol == "BTC"
        assert insight.direction == InsightDirection.UP
        assert insight.confidence == 1.0
        assert insight.is_long is True
        assert insight.is_short is False
        assert insight.is_flat is False

    def test_insight_creates_with_all_fields(self):
        """Test creating insight with all fields."""
        # ARRANGE
        now = datetime.now(timezone.utc)

        # ACT
        insight = Insight(
            symbol="ETH",
            direction=InsightDirection.DOWN,
            magnitude=0.05,
            confidence=0.8,
            weight=0.25,
            period_seconds=3600,
            insight_type=InsightType.VOLATILITY,
            source="TestAlpha",
            generated_time=now
        )

        # ASSERT
        assert insight.symbol == "ETH"
        assert insight.direction == InsightDirection.DOWN
        assert insight.magnitude == 0.05
        assert insight.confidence == 0.8
        assert insight.weight == 0.25
        assert insight.period_seconds == 3600
        assert insight.insight_type == InsightType.VOLATILITY
        assert insight.source == "TestAlpha"
        assert insight.generated_time == now
        assert insight.is_short is True

    def test_insight_auto_generates_timestamp(self):
        """Test insight auto-generates timestamp if not provided."""
        # ACT
        insight = Insight(symbol="BTC", direction=InsightDirection.UP)

        # ASSERT
        assert insight.generated_time is not None
        assert isinstance(insight.generated_time, datetime)

    def test_insight_validates_confidence_range(self):
        """Test confidence must be between 0 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            Insight(symbol="BTC", direction=InsightDirection.UP, confidence=1.5)

        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            Insight(symbol="BTC", direction=InsightDirection.UP, confidence=-0.1)

    def test_insight_direction_properties(self):
        """Test direction convenience properties."""
        # ARRANGE
        long_insight = Insight(symbol="BTC", direction=InsightDirection.UP)
        short_insight = Insight(symbol="ETH", direction=InsightDirection.DOWN)
        flat_insight = Insight(symbol="ADA", direction=InsightDirection.FLAT)

        # ASSERT
        assert long_insight.is_long and not long_insight.is_short and not long_insight.is_flat
        assert short_insight.is_short and not short_insight.is_long and not short_insight.is_flat
        assert flat_insight.is_flat and not flat_insight.is_long and not flat_insight.is_short

    def test_insight_repr(self):
        """Test insight string representation."""
        # ARRANGE
        insight = Insight(
            symbol="BTC",
            direction=InsightDirection.UP,
            confidence=0.75,
            weight=0.5
        )

        # ACT
        repr_str = repr(insight)

        # ASSERT
        assert "BTC" in repr_str
        assert "up" in repr_str
        assert "0.75" in repr_str


class TestTargetPortfolio:
    """Test TargetPortfolio data class."""

    def test_target_portfolio_creates_with_targets(self):
        """Test creating target portfolio."""
        # ACT
        portfolio = TargetPortfolio(
            targets={"BTC": 0.5, "ETH": 0.3}
        )

        # ASSERT
        assert portfolio.targets == {"BTC": 0.5, "ETH": 0.3}
        assert portfolio.timestamp is not None

    def test_target_portfolio_auto_generates_timestamp(self):
        """Test portfolio auto-generates timestamp."""
        # ACT
        portfolio = TargetPortfolio(targets={"BTC": 1.0})

        # ASSERT
        assert portfolio.timestamp is not None
        assert isinstance(portfolio.timestamp, datetime)

    def test_target_portfolio_validates_weight_range(self):
        """Test weights must be between -1 and 1."""
        # ACT & ASSERT
        with pytest.raises(ValueError, match="Weight.*must be between -1 and 1"):
            TargetPortfolio(targets={"BTC": 1.5})

        with pytest.raises(ValueError, match="Weight.*must be between -1 and 1"):
            TargetPortfolio(targets={"ETH": -1.5})

    def test_target_portfolio_calculates_total_weight(self):
        """Test total weight calculation (absolute values)."""
        # ARRANGE
        portfolio = TargetPortfolio(
            targets={"BTC": 0.5, "ETH": -0.3, "ADA": 0.2}
        )

        # ACT
        total = portfolio.total_weight

        # ASSERT
        assert total == 1.0  # |0.5| + |-0.3| + |0.2|

    def test_target_portfolio_calculates_long_weight(self):
        """Test long weight calculation."""
        # ARRANGE
        portfolio = TargetPortfolio(
            targets={"BTC": 0.5, "ETH": -0.3, "ADA": 0.2}
        )

        # ACT
        long_weight = portfolio.long_weight

        # ASSERT
        assert long_weight == 0.7  # 0.5 + 0.2

    def test_target_portfolio_calculates_short_weight(self):
        """Test short weight calculation (absolute value)."""
        # ARRANGE
        portfolio = TargetPortfolio(
            targets={"BTC": 0.5, "ETH": -0.3, "ADA": -0.1}
        )

        # ACT
        short_weight = portfolio.short_weight

        # ASSERT
        assert short_weight == 0.4  # |-0.3| + |-0.1|

    def test_target_portfolio_empty_targets(self):
        """Test empty portfolio."""
        # ARRANGE
        portfolio = TargetPortfolio(targets={})

        # ASSERT
        assert portfolio.total_weight == 0.0
        assert portfolio.long_weight == 0.0
        assert portfolio.short_weight == 0.0
