"""
Signal Confirmation Filter using Market Microstructure Data.

This module implements a confirmation layer that cross-references technical
alpha signals with options market data and Level 2 order book data to filter
out false signals and increase conviction in validated signals.

Based on institutional trading practices:
- Options data provides forward-looking sentiment and volatility expectations
- Level 2 data reveals real-time order flow and liquidity dynamics
- Cross-referencing these with technical signals reduces false positives

Key Concepts:
1. Put-Call Ratio (PCR) for sentiment confirmation
2. Open Interest (OI) for trend strength validation
3. Order Book Imbalance for immediate pressure assessment
4. Liquidity Score for execution feasibility
"""

from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from trade_engine.services.data.types_microstructure import MarketMicrostructure, OptionsSnapshot, Level2Snapshot
from trade_engine.services.strategies.types import Insight, InsightDirection


class SignalConfirmationFilter:
    """
    Filter and weight alpha insights using market microstructure data.

    This filter acts as a quality gate between alpha signal generation and
    portfolio construction, ensuring only high-conviction signals proceed.
    """

    def __init__(
        self,
        require_options_confirmation: bool = False,
        require_l2_confirmation: bool = True,
        min_liquidity_score: float = 50.0,
        pcr_bullish_threshold: float = 0.7,
        pcr_bearish_threshold: float = 1.2,
        ob_imbalance_threshold: float = 0.2,
        confidence_boost_factor: float = 1.2,
        confidence_penalty_factor: float = 0.7
    ):
        """
        Initialize Signal Confirmation Filter.

        Args:
            require_options_confirmation: If True, reject signals without options confirmation
            require_l2_confirmation: If True, reject signals without L2 confirmation
            min_liquidity_score: Minimum liquidity score to pass (0-100)
            pcr_bullish_threshold: PCR below this = bullish sentiment
            pcr_bearish_threshold: PCR above this = bearish sentiment
            ob_imbalance_threshold: Order book imbalance threshold for confirmation
            confidence_boost_factor: Multiply confidence when confirmed (default: 1.2x)
            confidence_penalty_factor: Multiply confidence when conflicting (default: 0.7x)
        """
        self.require_options_confirmation = require_options_confirmation
        self.require_l2_confirmation = require_l2_confirmation
        self.min_liquidity_score = min_liquidity_score
        self.pcr_bullish_threshold = pcr_bullish_threshold
        self.pcr_bearish_threshold = pcr_bearish_threshold
        self.ob_imbalance_threshold = ob_imbalance_threshold
        self.confidence_boost_factor = confidence_boost_factor
        self.confidence_penalty_factor = confidence_penalty_factor

    def _check_options_confirmation(
        self,
        insight: Insight,
        options_data: OptionsSnapshot
    ) -> Optional[str]:
        """
        Check if options data confirms the insight direction.

        Args:
            insight: Technical signal to validate
            options_data: Options market snapshot

        Returns:
            "CONFIRM", "CONFLICT", or "NEUTRAL"
        """
        # Check PCR-based sentiment
        pcr = options_data.put_call_ratio

        if insight.direction == InsightDirection.UP:
            # Bullish signal - confirm if PCR is bullish
            if pcr < self.pcr_bullish_threshold:
                return "CONFIRM"
            elif pcr > self.pcr_bearish_threshold:
                return "CONFLICT"
            else:
                return "NEUTRAL"

        elif insight.direction == InsightDirection.DOWN:
            # Bearish signal - confirm if PCR is bearish
            if pcr > self.pcr_bearish_threshold:
                return "CONFIRM"
            elif pcr < self.pcr_bullish_threshold:
                return "CONFLICT"
            else:
                return "NEUTRAL"

        return "NEUTRAL"

    def _check_l2_confirmation(
        self,
        insight: Insight,
        l2_data: Level2Snapshot
    ) -> Optional[str]:
        """
        Check if Level 2 order book confirms the insight direction.

        Args:
            insight: Technical signal to validate
            l2_data: Level 2 order book snapshot

        Returns:
            "CONFIRM", "CONFLICT", or "NEUTRAL"
        """
        imbalance = l2_data.get_order_book_imbalance()

        if insight.direction == InsightDirection.UP:
            # Bullish signal - confirm if buying pressure dominant
            if imbalance > self.ob_imbalance_threshold:
                return "CONFIRM"
            elif imbalance < -self.ob_imbalance_threshold:
                return "CONFLICT"
            else:
                return "NEUTRAL"

        elif insight.direction == InsightDirection.DOWN:
            # Bearish signal - confirm if selling pressure dominant
            if imbalance < -self.ob_imbalance_threshold:
                return "CONFIRM"
            elif imbalance > self.ob_imbalance_threshold:
                return "CONFLICT"
            else:
                return "NEUTRAL"

        return "NEUTRAL"

    def _check_liquidity_adequate(self, l2_data: Level2Snapshot) -> bool:
        """
        Check if liquidity is adequate for trading.

        Args:
            l2_data: Level 2 order book snapshot

        Returns:
            True if liquidity meets minimum threshold
        """
        liquidity_score = l2_data.get_liquidity_score()
        return liquidity_score >= self.min_liquidity_score

    def _detect_wall_interference(
        self,
        insight: Insight,
        l2_data: Level2Snapshot
    ) -> bool:
        """
        Detect if order book walls might interfere with the trade.

        Args:
            insight: Technical signal
            l2_data: Level 2 order book snapshot

        Returns:
            True if walls detected that conflict with signal direction
        """
        walls = l2_data.detect_walls()

        if insight.direction == InsightDirection.UP:
            # Bullish signal - large sell walls are concerning
            return len(walls["sell_walls"]) > 2

        elif insight.direction == InsightDirection.DOWN:
            # Bearish signal - large buy walls are concerning
            return len(walls["buy_walls"]) > 2

        return False

    def filter_insights(
        self,
        insights: List[Insight],
        microstructure_data: Dict[str, MarketMicrostructure]
    ) -> List[Insight]:
        """
        Filter and adjust insights based on microstructure confirmation.

        Args:
            insights: List of insights from alpha models
            microstructure_data: Dict mapping symbol -> MarketMicrostructure

        Returns:
            Filtered list of insights with adjusted confidence
        """
        filtered_insights = []

        for insight in insights:
            # Get microstructure data for this symbol
            micro_data = microstructure_data.get(insight.symbol)

            if micro_data is None:
                # No microstructure data available
                if self.require_options_confirmation or self.require_l2_confirmation:
                    logger.debug(
                        f"Rejecting {insight.symbol} {insight.direction.value} signal: "
                        f"no microstructure data available"
                    )
                    continue
                else:
                    # Pass through without confirmation
                    filtered_insights.append(insight)
                    continue

            # Initialize confirmation tracking
            confirmations = []
            conflicts = []
            adjusted_confidence = insight.confidence

            # Check options confirmation
            if micro_data.options_data:
                options_result = self._check_options_confirmation(
                    insight,
                    micro_data.options_data
                )

                if options_result == "CONFIRM":
                    confirmations.append("OPTIONS")
                    logger.info(
                        f"Options data confirms {insight.symbol} {insight.direction.value}: "
                        f"PCR={micro_data.options_data.put_call_ratio:.2f}"
                    )
                elif options_result == "CONFLICT":
                    conflicts.append("OPTIONS")
                    logger.warning(
                        f"Options data conflicts with {insight.symbol} {insight.direction.value}: "
                        f"PCR={micro_data.options_data.put_call_ratio:.2f}"
                    )

                    if self.require_options_confirmation:
                        logger.debug(f"Rejecting {insight.symbol}: options conflict")
                        continue

            # Check L2 confirmation
            if micro_data.l2_data:
                # First check liquidity
                if not self._check_liquidity_adequate(micro_data.l2_data):
                    logger.warning(
                        f"Rejecting {insight.symbol} {insight.direction.value}: "
                        f"insufficient liquidity "
                        f"(score={micro_data.l2_data.get_liquidity_score():.1f})"
                    )
                    continue

                # Check order book confirmation
                l2_result = self._check_l2_confirmation(insight, micro_data.l2_data)

                if l2_result == "CONFIRM":
                    confirmations.append("L2")
                    logger.info(
                        f"L2 data confirms {insight.symbol} {insight.direction.value}: "
                        f"imbalance={micro_data.l2_data.get_order_book_imbalance():+.2f}"
                    )
                elif l2_result == "CONFLICT":
                    conflicts.append("L2")
                    logger.warning(
                        f"L2 data conflicts with {insight.symbol} {insight.direction.value}: "
                        f"imbalance={micro_data.l2_data.get_order_book_imbalance():+.2f}"
                    )

                    if self.require_l2_confirmation:
                        logger.debug(f"Rejecting {insight.symbol}: L2 conflict")
                        continue

                # Check for wall interference
                if self._detect_wall_interference(insight, micro_data.l2_data):
                    logger.warning(
                        f"Large order book walls detected for {insight.symbol}, "
                        f"reducing confidence"
                    )
                    adjusted_confidence *= 0.9

            # Adjust confidence based on confirmations/conflicts
            if confirmations:
                # Boost confidence for each confirmation
                boost = self.confidence_boost_factor ** len(confirmations)
                adjusted_confidence = min(1.0, insight.confidence * boost)

                logger.info(
                    f"Boosted {insight.symbol} confidence: "
                    f"{insight.confidence:.2f} -> {adjusted_confidence:.2f} "
                    f"(confirmations: {', '.join(confirmations)})"
                )

            if conflicts:
                # Penalize confidence for each conflict
                penalty = self.confidence_penalty_factor ** len(conflicts)
                adjusted_confidence = insight.confidence * penalty

                logger.info(
                    f"Reduced {insight.symbol} confidence: "
                    f"{insight.confidence:.2f} -> {adjusted_confidence:.2f} "
                    f"(conflicts: {', '.join(conflicts)})"
                )

            # Create adjusted insight
            adjusted_insight = Insight(
                symbol=insight.symbol,
                direction=insight.direction,
                magnitude=insight.magnitude,
                confidence=adjusted_confidence,
                period_seconds=insight.period_seconds,
                insight_type=insight.insight_type,
                source=f"{insight.source}+CONFIRMED",
                generated_time=insight.generated_time
            )

            filtered_insights.append(adjusted_insight)

        logger.info(
            f"Signal confirmation: {len(insights)} input -> "
            f"{len(filtered_insights)} filtered ({len(filtered_insights)/len(insights)*100:.0f}% pass rate)"
        )

        return filtered_insights
