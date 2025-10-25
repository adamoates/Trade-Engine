"""
Strategy framework types and interfaces.

LEAN-inspired modular architecture for building trading strategies.
Each component (Alpha, Portfolio Construction, Risk Management, Execution)
is decoupled and can be developed, tested, and swapped independently.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional
from enum import Enum

from app.data.types import OHLCV, Quote, DataSourceType, AssetType


class InsightDirection(Enum):
    """Direction of price prediction."""
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class InsightType(Enum):
    """Type of insight signal."""
    PRICE = "price"          # Directional price prediction
    VOLATILITY = "volatility"  # Volatility forecast
    CORRELATION = "correlation"  # Correlation change


@dataclass
class Insight:
    """
    A prediction about an asset's future behavior.

    Inspired by QuantConnect's Insight object. This is the core
    communication mechanism between the Alpha Model and downstream
    components (Portfolio Construction, Risk Management).
    """
    symbol: str
    direction: InsightDirection
    magnitude: Optional[float] = None  # Expected return (e.g., 0.02 for 2%)
    confidence: float = 1.0  # 0.0 to 1.0
    weight: Optional[float] = None  # Suggested portfolio weight
    period_seconds: Optional[int] = None  # How long this insight is valid
    insight_type: InsightType = InsightType.PRICE
    source: Optional[str] = None  # Alpha model that generated this
    generated_time: Optional[datetime] = None

    def __post_init__(self):
        if self.generated_time is None:
            self.generated_time = datetime.now(timezone.utc)

        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")

    @property
    def is_long(self) -> bool:
        """True if insight predicts upward movement."""
        return self.direction == InsightDirection.UP

    @property
    def is_short(self) -> bool:
        """True if insight predicts downward movement."""
        return self.direction == InsightDirection.DOWN

    @property
    def is_flat(self) -> bool:
        """True if insight predicts no significant movement."""
        return self.direction == InsightDirection.FLAT

    def __repr__(self):
        return (f"Insight({self.symbol}, {self.direction.value}, "
                f"confidence={self.confidence:.2f}, weight={self.weight})")


@dataclass
class TargetPortfolio:
    """
    Desired portfolio state from Portfolio Construction.

    Maps symbols to target weights (0.0 to 1.0).
    Weights should sum to <= 1.0 (cash is implicit).
    """
    targets: Dict[str, float]  # symbol -> weight
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

        # Validate weights
        for symbol, weight in self.targets.items():
            if not -1.0 <= weight <= 1.0:
                raise ValueError(
                    f"Weight for {symbol} must be between -1 and 1, got {weight}"
                )

    @property
    def total_weight(self) -> float:
        """Sum of all weights (should be <= 1.0)."""
        return sum(abs(w) for w in self.targets.values())

    @property
    def long_weight(self) -> float:
        """Sum of long positions."""
        return sum(w for w in self.targets.values() if w > 0)

    @property
    def short_weight(self) -> float:
        """Sum of short positions (absolute value)."""
        return abs(sum(w for w in self.targets.values() if w < 0))


class AlphaModel(ABC):
    """
    Abstract base class for Alpha Models.

    Alpha Models analyze market data and generate Insights
    (predictions about future price movements).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this alpha model."""
        pass

    @abstractmethod
    def generate_insights(
        self,
        data: Dict[str, List[OHLCV]],
        current_time: datetime
    ) -> List[Insight]:
        """
        Generate trading insights from market data.

        Args:
            data: Dictionary mapping symbol -> OHLCV candles
            current_time: Current simulation or real-world time

        Returns:
            List of Insights (predictions)
        """
        pass


class PortfolioConstructionModel(ABC):
    """
    Abstract base class for Portfolio Construction.

    Converts Insights into target portfolio weights.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this portfolio construction model."""
        pass

    @abstractmethod
    def create_targets(
        self,
        insights: List[Insight],
        current_portfolio: Dict[str, float]
    ) -> TargetPortfolio:
        """
        Convert insights into target portfolio weights.

        Args:
            insights: List of Insights from Alpha Model(s)
            current_portfolio: Current holdings (symbol -> weight)

        Returns:
            Target portfolio with desired weights
        """
        pass


class RiskManagementModel(ABC):
    """
    Abstract base class for Risk Management.

    Applies risk constraints to target portfolio.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this risk management model."""
        pass

    @abstractmethod
    def manage_risk(
        self,
        targets: TargetPortfolio,
        current_portfolio: Dict[str, float]
    ) -> TargetPortfolio:
        """
        Apply risk constraints to target portfolio.

        Args:
            targets: Proposed target portfolio
            current_portfolio: Current holdings

        Returns:
            Risk-adjusted target portfolio
        """
        pass
