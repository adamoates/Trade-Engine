"""
Equal Weight Portfolio Construction Model.

Allocates equal weight to all assets with active insights.
Simple but effective baseline strategy.
"""

from typing import List, Dict
from loguru import logger

from trade_engine.domain.strategies.types import (
    PortfolioConstructionModel,
    Insight,
    TargetPortfolio,
    InsightDirection
)


class EqualWeightPortfolioConstructionModel(PortfolioConstructionModel):
    """
    Allocate equal weight to all assets with insights.

    - Long signals get positive weight
    - Short signals get negative weight (if shorts_enabled)
    - Flat signals result in zero weight (exit position)
    """

    def __init__(self, shorts_enabled: bool = False):
        """
        Initialize Equal Weight Portfolio Construction.

        Args:
            shorts_enabled: Allow short positions (default: False)
        """
        self.shorts_enabled = shorts_enabled

    @property
    def name(self) -> str:
        shorts_suffix = "_with_shorts" if self.shorts_enabled else ""
        return f"EqualWeight{shorts_suffix}"

    def create_targets(
        self,
        insights: List[Insight],
        current_portfolio: Dict[str, float]
    ) -> TargetPortfolio:
        """
        Create equal-weighted target portfolio from insights.

        Args:
            insights: List of Insights from Alpha Model(s)
            current_portfolio: Current holdings (symbol -> weight)

        Returns:
            Target portfolio with equal weights
        """
        if not insights:
            logger.debug(f"{self.name}: No insights, returning empty portfolio")
            return TargetPortfolio(targets={})

        # Separate long and short signals
        long_symbols = [
            i.symbol for i in insights
            if i.direction == InsightDirection.UP
        ]

        short_symbols = [
            i.symbol for i in insights
            if i.direction == InsightDirection.DOWN and self.shorts_enabled
        ]

        flat_symbols = [
            i.symbol for i in insights
            if i.direction == InsightDirection.FLAT
        ]

        targets = {}

        # Equal weight for longs
        if long_symbols:
            long_weight = 1.0 / len(long_symbols)
            for symbol in long_symbols:
                targets[symbol] = long_weight
                logger.debug(f"{self.name}: Long {symbol} with weight {long_weight:.4f}")

        # Equal weight for shorts (negative)
        if short_symbols:
            short_weight = -1.0 / len(short_symbols)
            for symbol in short_symbols:
                targets[symbol] = short_weight
                logger.debug(f"{self.name}: Short {symbol} with weight {short_weight:.4f}")

        # Zero weight for flat signals (exit)
        for symbol in flat_symbols:
            targets[symbol] = 0.0
            logger.debug(f"{self.name}: Exit {symbol}")

        logger.info(
            f"{self.name}: Created portfolio with {len(long_symbols)} longs, "
            f"{len(short_symbols)} shorts, {len(flat_symbols)} exits"
        )

        return TargetPortfolio(targets=targets)
