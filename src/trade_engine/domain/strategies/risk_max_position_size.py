"""
Maximum Position Size Risk Management Model.

Ensures no single position exceeds a maximum percentage of the portfolio.
"""

from typing import Dict
from loguru import logger

from trade_engine.domain.strategies.types import (
    RiskManagementModel,
    TargetPortfolio
)


class MaxPositionSizeRiskModel(RiskManagementModel):
    """
    Limit maximum size of any single position.

    If any position exceeds max_position_size, scale down all positions
    proportionally to bring the largest position to the limit.
    """

    def __init__(self, max_position_size: float = 0.25):
        """
        Initialize Max Position Size Risk Model.

        Args:
            max_position_size: Maximum weight for any single position (0.0 to 1.0)
                              Default: 0.25 (25% of portfolio)
        """
        if not 0.0 < max_position_size <= 1.0:
            raise ValueError(
                f"max_position_size must be between 0 and 1, got {max_position_size}"
            )

        self.max_position_size = max_position_size

    @property
    def name(self) -> str:
        return f"MaxPositionSize_{int(self.max_position_size * 100)}pct"

    def manage_risk(
        self,
        targets: TargetPortfolio,
        current_portfolio: Dict[str, float]
    ) -> TargetPortfolio:
        """
        Apply maximum position size constraint.

        Args:
            targets: Proposed target portfolio
            current_portfolio: Current holdings

        Returns:
            Risk-adjusted target portfolio
        """
        if not targets.targets:
            logger.debug(f"{self.name}: Empty portfolio, no risk adjustment needed")
            return targets

        # Find maximum position size (absolute value)
        max_weight = max(abs(w) for w in targets.targets.values())

        if max_weight <= self.max_position_size:
            logger.debug(
                f"{self.name}: Max position {max_weight:.4f} within limit "
                f"{self.max_position_size:.4f}, no adjustment needed"
            )
            return targets

        # Scale down all positions proportionally
        scale_factor = self.max_position_size / max_weight

        adjusted_targets = {
            symbol: weight * scale_factor
            for symbol, weight in targets.targets.items()
        }

        logger.warning(
            f"{self.name}: Max position {max_weight:.4f} exceeds limit "
            f"{self.max_position_size:.4f}. Scaling all positions by {scale_factor:.4f}"
        )

        return TargetPortfolio(
            targets=adjusted_targets,
            timestamp=targets.timestamp
        )
