"""
Breakout Setup Detection Strategy

Multi-factor breakout detection combining:
- Price breakout above resistance with volume confirmation
- Momentum indicators (RSI, MACD)
- Volatility squeeze (Bollinger Bands)
- Derivatives signals (Open Interest, Funding Rate, Put/Call Ratio)
- Risk filters (overextension, trap detection)

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

from decimal import Decimal
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque
import time
from loguru import logger

from trade_engine.core.types import Strategy, Bar, Signal


@dataclass
class BreakoutConfig:
    """Configuration for breakout detection strategy."""

    # Breakout Detection
    volume_spike_threshold: Decimal = Decimal("2.0")  # 2x average volume required
    resistance_confirmation_pct: Decimal = Decimal("0.5")  # 0.5% above resistance

    # Momentum Indicators
    rsi_period: int = 14
    rsi_bullish_threshold: Decimal = Decimal("55")
    rsi_overbought_threshold: Decimal = Decimal("75")

    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    macd_lookback_bars: int = 5  # Check MACD cross in last N bars

    # Volatility
    bb_period: int = 20
    bb_std_dev: Decimal = Decimal("2.0")
    bb_squeeze_threshold: Decimal = Decimal("0.02")  # 2% bandwidth = tight
    bb_expansion_multiplier: Decimal = Decimal("1.5")  # 1.5x squeeze bandwidth = expansion

    # Volume
    volume_ma_period: int = 20
    min_volume_threshold: Decimal = Decimal("0.001")  # Minimum volume for ratio calculation

    # Derivatives (Optional - may not be available)
    oi_increase_threshold: Decimal = Decimal("0.10")  # 10% increase in 24h
    put_call_bullish_threshold: Decimal = Decimal("1.0")  # < 1.0 = bullish
    funding_rate_positive_min: Decimal = Decimal("0.0001")  # 0.01% per 8h
    funding_rate_extreme_max: Decimal = Decimal("0.0005")  # 0.05% per 8h (avoid)

    # Support/Resistance Detection
    sr_lookback_bars: int = 50  # Look back 50 bars for S/R levels
    sr_tolerance_pct: Decimal = Decimal("0.5")  # 0.5% tolerance for level matching
    sr_detection_window: int = 2  # Bars on each side for swing high/low detection

    # Risk Filters
    trap_detection_price_move_pct: Decimal = Decimal("1.0")  # <1% price move = flat (trap risk)
    stop_loss_pct_below_resistance: Decimal = Decimal("0.98")  # Stop loss 2% below resistance
    stop_loss_pct_fallback: Decimal = Decimal("0.97")  # Stop loss 3% below entry if no resistance
    take_profit_risk_reward_ratio: Decimal = Decimal("2.0")  # 2:1 R:R ratio for TP

    # Position Sizing
    position_size_usd: Decimal = Decimal("1000")

    # Signal Confidence Weights
    weight_breakout: Decimal = Decimal("0.30")
    weight_momentum: Decimal = Decimal("0.25")
    weight_volatility: Decimal = Decimal("0.15")
    weight_derivatives: Decimal = Decimal("0.20")
    weight_risk_filter: Decimal = Decimal("0.10")

    # Signal Generation Thresholds
    confidence_threshold_bullish_breakout: Decimal = Decimal("0.70")  # 70% confidence for signal
    confidence_threshold_watchlist: Decimal = Decimal("0.50")  # 50% confidence for watchlist


@dataclass
class SetupSignal:
    """Detailed breakout setup signal with all conditions."""

    symbol: str
    setup: str  # "Bullish Breakout", "Watchlist", "No Trade"
    confidence: Decimal
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    action: str = "No action"

    # Detailed metrics
    current_price: Decimal = Decimal("0")
    resistance_level: Optional[Decimal] = None
    support_level: Optional[Decimal] = None
    volume_ratio: Decimal = Decimal("0")
    rsi: Decimal = Decimal("0")
    macd_histogram: Decimal = Decimal("0")
    bb_bandwidth_pct: Decimal = Decimal("0")
    oi_change_pct: Optional[Decimal] = None
    funding_rate: Optional[Decimal] = None
    put_call_ratio: Optional[Decimal] = None

    # Confidence breakdown
    raw_confidence: Decimal = Decimal("0")  # Confidence before risk filter
    risk_blocked: bool = False  # True if risk filter failed

    timestamp: int = 0


class BreakoutSetupDetector(Strategy):
    """
    Breakout Setup Detection Strategy.

    Detects bullish breakout setups using multi-factor confirmation:
    1. Price breakout above resistance with volume
    2. Momentum confirmation (RSI, MACD)
    3. Volatility squeeze (Bollinger Bands)
    4. Derivatives signals (OI, funding, put/call)
    5. Risk filters (overextension, trap detection)

    Returns detailed SetupSignal with all conditions and confidence score.
    """

    def __init__(
        self,
        symbol: str,
        config: Optional[BreakoutConfig] = None
    ):
        """
        Initialize breakout detector.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            config: Strategy configuration (uses defaults if None)
        """
        self.symbol = symbol
        self.config = config or BreakoutConfig()

        # Validate configuration
        # S/R detection requires minimum 5 bars: 2 on each side + 1 center
        # (due to sr_detection_window=2 in loop range(2, len-2))
        min_sr_bars = self.config.sr_detection_window * 2 + 1
        if self.config.sr_lookback_bars < min_sr_bars:
            logger.warning(
                "sr_lookback_bars_too_small",
                symbol=self.symbol,
                configured_value=self.config.sr_lookback_bars,
                minimum_required=min_sr_bars,
                detection_window=self.config.sr_detection_window,
                reason="S/R detection requires window bars on each side plus center"
            )
            self.config.sr_lookback_bars = min_sr_bars

        # Validate and auto-normalize confidence weights to sum to 1.0
        weight_sum = (
            self.config.weight_breakout +
            self.config.weight_momentum +
            self.config.weight_volatility +
            self.config.weight_derivatives +
            self.config.weight_risk_filter
        )
        if weight_sum != Decimal("1.0"):
            logger.warning(
                "confidence_weights_misconfigured",
                symbol=self.symbol,
                weight_sum=float(weight_sum),
                expected=1.0,
                breakout=float(self.config.weight_breakout),
                momentum=float(self.config.weight_momentum),
                volatility=float(self.config.weight_volatility),
                derivatives=float(self.config.weight_derivatives),
                risk_filter=float(self.config.weight_risk_filter),
                action="auto_normalizing"
            )

            # Auto-normalize weights to sum to 1.0
            self.config.weight_breakout /= weight_sum
            self.config.weight_momentum /= weight_sum
            self.config.weight_volatility /= weight_sum
            self.config.weight_derivatives /= weight_sum
            self.config.weight_risk_filter /= weight_sum

            logger.info(
                "confidence_weights_normalized",
                symbol=self.symbol,
                breakout=float(self.config.weight_breakout),
                momentum=float(self.config.weight_momentum),
                volatility=float(self.config.weight_volatility),
                derivatives=float(self.config.weight_derivatives),
                risk_filter=float(self.config.weight_risk_filter),
                new_sum=1.0
            )

        # Price history for indicators
        self.closes: deque = deque(maxlen=max(
            self.config.bb_period,
            self.config.volume_ma_period,
            self.config.sr_lookback_bars
        ))
        self.highs: deque = deque(maxlen=self.config.sr_lookback_bars)
        self.lows: deque = deque(maxlen=self.config.sr_lookback_bars)
        self.volumes: deque = deque(maxlen=self.config.volume_ma_period)

        # Indicator state
        self.rsi_values: deque = deque(maxlen=self.config.rsi_period + 10)
        self.macd_values: deque = deque(maxlen=self.config.macd_lookback_bars + 10)
        self.macd_signal_values: deque = deque(maxlen=self.config.macd_lookback_bars + 10)
        self.macd_histogram_values: deque = deque(maxlen=self.config.macd_lookback_bars)

        # RSI Wilder's smoothing state
        self._prev_avg_gain: Optional[Decimal] = None
        self._prev_avg_loss: Optional[Decimal] = None

        # Support/Resistance levels
        self.resistance_levels: List[Decimal] = []
        self.support_levels: List[Decimal] = []

        # Derivatives data (optional, updated externally)
        self.open_interest_history: deque = deque(maxlen=24)  # 24 hours of data
        self.current_funding_rate: Optional[Decimal] = None
        self.current_put_call_ratio: Optional[Decimal] = None

        # Derivatives data staleness tracking
        self.oi_last_update: Optional[int] = None
        self.funding_last_update: Optional[int] = None
        self.put_call_last_update: Optional[int] = None
        self.derivatives_staleness_threshold: int = 3600  # 1 hour in seconds

        # State tracking
        self.last_signal_time: int = 0
        self.signal_count: int = 0

        logger.info(
            f"BreakoutSetupDetector initialized | "
            f"Symbol: {self.symbol} | "
            f"RSI: {self.config.rsi_period} | "
            f"MACD: {self.config.macd_fast}/{self.config.macd_slow}/{self.config.macd_signal} | "
            f"BB: {self.config.bb_period} | "
            f"Volume Threshold: {self.config.volume_spike_threshold}x"
        )

    def on_bar(self, bar: Bar) -> list[Signal]:
        """
        Process new bar and detect breakout setups.

        Args:
            bar: Current completed bar

        Returns:
            List of signals (standard Signal format for compatibility)
        """
        # Update price history
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.volumes.append(bar.volume)

        # Need minimum bars for indicators
        if len(self.closes) < self.config.bb_period:
            logger.debug(
                "strategy_warmup",
                symbol=self.symbol,
                current_bars=len(self.closes),
                required_bars=self.config.bb_period,
                status="warming_up"
            )
            return []

        # Update indicators
        self._update_indicators()

        # Detect support/resistance levels
        self._update_support_resistance()

        # Analyze breakout setup
        setup = self._analyze_breakout_setup(bar)

        # Log detailed setup info with structured logging
        logger.info(
            "breakout_analysis",
            symbol=self.symbol,
            setup=setup.setup,
            confidence=float(setup.confidence),
            raw_confidence=float(setup.raw_confidence),
            risk_blocked=setup.risk_blocked,
            conditions_met=len(setup.conditions_met),
            conditions_failed=len(setup.conditions_failed),
            current_price=str(setup.current_price),
            resistance_level=str(setup.resistance_level) if setup.resistance_level else None,
            volume_ratio=float(setup.volume_ratio),
            rsi=float(setup.rsi),
            macd_histogram=float(setup.macd_histogram),
            bb_bandwidth_pct=float(setup.bb_bandwidth_pct),
            oi_change_pct=float(setup.oi_change_pct) if setup.oi_change_pct else None,
            funding_rate=float(setup.funding_rate) if setup.funding_rate else None
        )

        # Convert to standard Signal if bullish breakout detected
        if setup.setup == "Bullish Breakout" and setup.confidence >= self.config.confidence_threshold_bullish_breakout:
            signal = self._create_signal_from_setup(setup, bar)
            self.signal_count += 1
            self.last_signal_time = int(time.time())
            return [signal]

        return []

    def _update_indicators(self) -> None:
        """Calculate and update all technical indicators."""
        # RSI
        rsi = self._calculate_rsi()
        if rsi is not None:
            self.rsi_values.append(rsi)

        # MACD
        macd_line, signal_line, histogram = self._calculate_macd()
        if macd_line is not None:
            self.macd_values.append(macd_line)
            self.macd_signal_values.append(signal_line)
            self.macd_histogram_values.append(histogram)

    def _calculate_rsi(self) -> Optional[Decimal]:
        """
        Calculate RSI using Wilder's smoothing method.

        Formula:
        - First RS = average gain / average loss over period
        - Subsequent RS = (previous average gain * (period-1) + current gain) / period
                        / (previous average loss * (period-1) + current loss) / period

        This matches TradingView, MT4, and industry-standard RSI implementations.
        """
        if len(self.closes) < self.config.rsi_period + 1:
            return None

        # First calculation: use simple moving average
        if self._prev_avg_gain is None or self._prev_avg_loss is None:
            gains = Decimal("0")
            losses = Decimal("0")

            for i in range(1, self.config.rsi_period + 1):
                change = self.closes[-i] - self.closes[-i - 1]
                if change > 0:
                    gains += change
                else:
                    losses += abs(change)

            self._prev_avg_gain = gains / Decimal(str(self.config.rsi_period))
            self._prev_avg_loss = losses / Decimal(str(self.config.rsi_period))
        else:
            # Wilder's smoothing: exponential averaging
            change = self.closes[-1] - self.closes[-2]
            current_gain = change if change > 0 else Decimal("0")
            current_loss = abs(change) if change < 0 else Decimal("0")

            period_dec = Decimal(str(self.config.rsi_period))
            self._prev_avg_gain = (self._prev_avg_gain * (period_dec - 1) + current_gain) / period_dec
            self._prev_avg_loss = (self._prev_avg_loss * (period_dec - 1) + current_loss) / period_dec

        # Calculate RSI
        if self._prev_avg_loss == 0:
            return Decimal("100")

        rs = self._prev_avg_gain / self._prev_avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

        return rsi

    def _calculate_macd(self) -> tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """Calculate MACD (12, 26, 9 default)."""
        if len(self.closes) < self.config.macd_slow:
            return None, None, None

        # Fast EMA
        fast_ema = self._calculate_ema(list(self.closes), self.config.macd_fast)

        # Slow EMA
        slow_ema = self._calculate_ema(list(self.closes), self.config.macd_slow)

        # MACD Line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema

        # Signal Line = 9-period EMA of MACD Line
        if len(self.macd_values) < self.config.macd_signal:
            signal_line = macd_line  # Not enough data for signal yet
        else:
            signal_line = self._calculate_ema(list(self.macd_values), self.config.macd_signal)

        # Histogram = MACD Line - Signal Line
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _calculate_ema(self, data: List[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            # Fall back to SMA if not enough data
            return sum(data[-period:]) / Decimal(str(period))

        multiplier = Decimal("2") / (Decimal(str(period)) + Decimal("1"))
        ema = sum(data[:period]) / Decimal(str(period))  # Start with SMA

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_bollinger_bands(self) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate Bollinger Bands (upper, middle, lower)."""
        period = self.config.bb_period
        std_dev = self.config.bb_std_dev

        # Convert deque to list for slicing
        closes_list = list(self.closes)

        # Middle Band (SMA)
        middle = sum(closes_list[-period:]) / Decimal(str(period))

        # Standard Deviation
        variance = sum((x - middle) ** 2 for x in closes_list[-period:]) / Decimal(str(period))
        std = variance.sqrt()

        # Upper and Lower Bands
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return upper, middle, lower

    def _update_support_resistance(self) -> None:
        """
        Detect support and resistance levels from recent price action.

        Uses >= comparisons to handle double tops/bottoms and tolerance-based
        merging to consolidate nearby levels.
        """
        if len(self.highs) < self.config.sr_lookback_bars:
            return

        # Simple S/R detection: recent swing highs/lows
        recent_highs = list(self.highs)[-self.config.sr_lookback_bars:]
        recent_lows = list(self.lows)[-self.config.sr_lookback_bars:]

        # Resistance: Recent swing highs (local maxima)
        # Using >= to handle double tops
        raw_resistance = []
        window = self.config.sr_detection_window
        for i in range(window, len(recent_highs) - window):
            if (recent_highs[i] >= recent_highs[i-1] and
                recent_highs[i] >= recent_highs[i-2] and
                recent_highs[i] >= recent_highs[i+1] and
                recent_highs[i] >= recent_highs[i+2]):
                raw_resistance.append(recent_highs[i])

        # Support: Recent swing lows (local minima)
        # Using <= to handle double bottoms
        raw_support = []
        for i in range(window, len(recent_lows) - window):
            if (recent_lows[i] <= recent_lows[i-1] and
                recent_lows[i] <= recent_lows[i-2] and
                recent_lows[i] <= recent_lows[i+1] and
                recent_lows[i] <= recent_lows[i+2]):
                raw_support.append(recent_lows[i])

        # Merge nearby levels using tolerance
        self.resistance_levels = self._merge_nearby_levels(raw_resistance)[:5]
        self.support_levels = self._merge_nearby_levels(raw_support)[:5]

    def _merge_nearby_levels(self, levels: List[Decimal]) -> List[Decimal]:
        """
        Merge nearby S/R levels within tolerance percentage.

        Args:
            levels: List of price levels to merge

        Returns:
            Merged list of unique levels
        """
        if not levels:
            return []

        # Sort levels
        sorted_levels = sorted(set(levels), reverse=True)
        merged: List[Decimal] = []

        for level in sorted_levels:
            # Check if this level is close to any existing merged level
            is_unique = True
            for existing_level in merged:
                pct_diff = abs(level - existing_level) / existing_level * Decimal("100")
                if pct_diff < self.config.sr_tolerance_pct:
                    is_unique = False
                    break

            if is_unique:
                merged.append(level)

        return merged

    def _analyze_breakout_setup(self, bar: Bar) -> SetupSignal:
        """
        Analyze current bar for breakout setup.

        Returns SetupSignal with detailed analysis.
        """
        setup = SetupSignal(
            symbol=self.symbol,
            setup="No Trade",
            confidence=Decimal("0"),
            current_price=bar.close,
            timestamp=bar.timestamp
        )

        conditions_met = []
        conditions_failed = []
        confidence_scores = []

        # 1. BREAKOUT CHECK
        breakout_score, breakout_msg = self._check_breakout(bar)
        if breakout_score > 0:
            conditions_met.append(breakout_msg)
            setup.resistance_level = self._get_nearest_resistance(bar.close)
        else:
            conditions_failed.append(breakout_msg)
        confidence_scores.append(breakout_score * self.config.weight_breakout)

        # 2. MOMENTUM CONFIRMATION
        momentum_score, momentum_msg = self._check_momentum()
        if momentum_score > 0:
            conditions_met.append(momentum_msg)
        else:
            conditions_failed.append(momentum_msg)
        confidence_scores.append(momentum_score * self.config.weight_momentum)

        # Fill in metrics
        if len(self.rsi_values) > 0:
            setup.rsi = self.rsi_values[-1]
        if len(self.macd_histogram_values) > 0:
            setup.macd_histogram = self.macd_histogram_values[-1]

        # 3. VOLATILITY SQUEEZE CHECK
        volatility_score, volatility_msg = self._check_volatility_squeeze()
        if volatility_score > 0:
            conditions_met.append(volatility_msg)
        else:
            conditions_failed.append(volatility_msg)
        confidence_scores.append(volatility_score * self.config.weight_volatility)

        upper, middle, lower = self._calculate_bollinger_bands()
        setup.bb_bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # 4. DERIVATIVES SIGNALS (Optional)
        derivatives_score, derivatives_msg = self._check_derivatives()
        if derivatives_score > 0:
            conditions_met.append(derivatives_msg)
        elif derivatives_score < 0:
            conditions_failed.append(derivatives_msg)
        confidence_scores.append(max(Decimal("0"), derivatives_score) * self.config.weight_derivatives)

        setup.oi_change_pct = self._get_oi_change_pct()
        setup.funding_rate = self.current_funding_rate
        setup.put_call_ratio = self.current_put_call_ratio

        # Calculate volume ratio with robust zero check
        if len(self.volumes) >= self.config.volume_ma_period:
            avg_volume = sum(list(self.volumes)[:-1]) / Decimal(str(self.config.volume_ma_period - 1))
            # Use robust threshold to avoid division by near-zero values
            if avg_volume > self.config.min_volume_threshold:
                setup.volume_ratio = bar.volume / avg_volume
            else:
                setup.volume_ratio = Decimal("0")
                logger.warning(
                    "volume_ratio_skipped",
                    symbol=self.symbol,
                    avg_volume=str(avg_volume),
                    threshold=str(self.config.min_volume_threshold),
                    reason="Average volume below minimum threshold"
                )

        # Calculate RAW confidence from POSITIVE factors only (before risk filter)
        setup.raw_confidence = max(Decimal("0"), min(Decimal("1"), sum(confidence_scores)))

        # 5. RISK FILTER - Applied as BOOLEAN gate, not as confidence penalty
        risk_passed, risk_msg = self._check_risk_filters()
        if risk_passed:
            # Risk filter passed - use raw confidence
            setup.confidence = setup.raw_confidence
            setup.risk_blocked = False
            conditions_met.append(risk_msg)
        else:
            # Risk filter failed - hard block (set confidence to 0)
            setup.confidence = Decimal("0")
            setup.risk_blocked = True
            conditions_failed.append(risk_msg)

        setup.conditions_met = conditions_met
        setup.conditions_failed = conditions_failed

        # Determine setup type based on confidence thresholds
        if setup.confidence >= self.config.confidence_threshold_bullish_breakout:
            setup.setup = "Bullish Breakout"
            setup.action = "Enter long via call options or perp with stop below resistance"
        elif setup.confidence >= self.config.confidence_threshold_watchlist:
            setup.setup = "Watchlist"
            setup.action = "Setup forming but not confirmed. Monitor for entry."
        else:
            setup.setup = "No Trade"
            setup.action = "Stay flat. Conditions not satisfied."

        return setup

    def _check_breakout(self, bar: Bar) -> tuple[Decimal, str]:
        """Check if price is breaking above resistance with volume."""
        if not self.resistance_levels:
            return Decimal("0"), "No resistance level identified"

        nearest_resistance = self._get_nearest_resistance(bar.close)
        if nearest_resistance is None:
            return Decimal("0"), "No resistance level identified"

        # Check if closing above resistance
        breakout_threshold = nearest_resistance * (Decimal("1") + self.config.resistance_confirmation_pct / Decimal("100"))
        if bar.close <= breakout_threshold:
            return Decimal("0"), f"Price {bar.close} not above resistance {nearest_resistance}"

        # Check volume spike
        if len(self.volumes) < self.config.volume_ma_period:
            return Decimal("0.5"), f"Breakout above {nearest_resistance} but volume data insufficient"

        avg_volume = sum(list(self.volumes)[:-1]) / Decimal(str(self.config.volume_ma_period - 1))

        # Robust check: ensure avg_volume is above minimum threshold to avoid division issues
        if avg_volume <= self.config.min_volume_threshold:
            logger.warning(
                "breakout_volume_insufficient",
                symbol=self.symbol,
                avg_volume=str(avg_volume),
                threshold=str(self.config.min_volume_threshold),
                nearest_resistance=str(nearest_resistance)
            )
            return Decimal("0.3"), f"Breakout above {nearest_resistance} but volume too low to confirm"

        volume_ratio = bar.volume / avg_volume

        if volume_ratio >= self.config.volume_spike_threshold:
            return Decimal("1.0"), f"Breakout above resistance {nearest_resistance} with volume {volume_ratio:.1f}x avg"
        else:
            return Decimal("0.5"), f"Breakout above {nearest_resistance} but volume only {volume_ratio:.1f}x avg"

    def _check_momentum(self) -> tuple[Decimal, str]:
        """Check RSI and MACD for bullish momentum."""
        score = Decimal("0")
        messages = []

        # RSI Check
        if len(self.rsi_values) == 0:
            return Decimal("0"), "RSI data insufficient"

        current_rsi = self.rsi_values[-1]
        if current_rsi >= self.config.rsi_bullish_threshold:
            score += Decimal("0.5")
            messages.append(f"RSI {current_rsi:.0f} bullish")
        else:
            messages.append(f"RSI {current_rsi:.0f} below threshold")

        # MACD Check
        if len(self.macd_values) < self.config.macd_lookback_bars:
            messages.append("MACD data insufficient")
        else:
            # Check if MACD crossed above zero in last N bars
            macd_crossed_up = False
            for i in range(1, min(self.config.macd_lookback_bars + 1, len(self.macd_values))):
                # Safety check: ensure we don't access out of bounds
                if i + 1 <= len(self.macd_values):
                    if self.macd_values[-i] > 0 and self.macd_values[-i-1] <= 0:
                        macd_crossed_up = True
                        break

            if macd_crossed_up or self.macd_values[-1] > 0:
                score += Decimal("0.5")
                messages.append(f"MACD bullish (hist: {self.macd_histogram_values[-1]:+.4f})")
            else:
                messages.append(f"MACD not bullish (hist: {self.macd_histogram_values[-1]:+.4f})")

        return score, ", ".join(messages)

    def _check_volatility_squeeze(self) -> tuple[Decimal, str]:
        """Check for Bollinger Band squeeze (precedes breakouts)."""
        if len(self.closes) < self.config.bb_period:
            return Decimal("0"), "BB data insufficient"

        upper, middle, lower = self._calculate_bollinger_bands()
        bandwidth_pct = ((upper - lower) / middle) * Decimal("100")

        # Check historical bandwidth to see if it was recently tight
        # For now, simple check: is current bandwidth expanding from tight?
        squeeze_threshold_pct = self.config.bb_squeeze_threshold * Decimal("100")
        expansion_threshold_pct = squeeze_threshold_pct * self.config.bb_expansion_multiplier

        if bandwidth_pct <= squeeze_threshold_pct:
            return Decimal("0.5"), f"BB squeeze active ({bandwidth_pct:.2f}% bandwidth)"
        elif bandwidth_pct > expansion_threshold_pct:
            return Decimal("1.0"), f"BB expanding from squeeze ({bandwidth_pct:.2f}% bandwidth)"
        else:
            return Decimal("0"), f"BB bandwidth normal ({bandwidth_pct:.2f}%)"

    def _check_derivatives(self) -> tuple[Decimal, str]:
        """Check Open Interest, Funding Rate, Put/Call Ratio."""
        score = Decimal("0")
        messages = []
        current_time = int(time.time())

        # Check for stale derivatives data
        if self.oi_last_update and (current_time - self.oi_last_update) > self.derivatives_staleness_threshold:
            return Decimal("0"), "Derivatives data stale (OI >1h old)"

        # Open Interest Check
        oi_change = self._get_oi_change_pct()
        if oi_change is not None:
            if oi_change >= self.config.oi_increase_threshold:
                score += Decimal("0.4")
                messages.append(f"OI increased {oi_change*100:.1f}%")
            else:
                messages.append(f"OI change {oi_change*100:.1f}% insufficient")

        # Funding Rate Check
        if self.current_funding_rate is not None:
            if (self.current_funding_rate >= self.config.funding_rate_positive_min and
                self.current_funding_rate <= self.config.funding_rate_extreme_max):
                score += Decimal("0.3")
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% positive")
            elif self.current_funding_rate > self.config.funding_rate_extreme_max:
                score -= Decimal("0.3")
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% extreme")
            else:
                messages.append(f"Funding rate {self.current_funding_rate*100:.3f}% not bullish")

        # Put/Call Ratio Check
        if self.current_put_call_ratio is not None:
            if self.current_put_call_ratio < self.config.put_call_bullish_threshold:
                score += Decimal("0.3")
                messages.append(f"P/C ratio {self.current_put_call_ratio:.2f} bullish")
            else:
                messages.append(f"P/C ratio {self.current_put_call_ratio:.2f} not bullish")

        if not messages:
            return Decimal("0"), "No derivatives data available"

        return score, ", ".join(messages)

    def _check_risk_filters(self) -> tuple[bool, str]:
        """
        Check for overextension and trap conditions.

        Returns:
            (passed, message): True if all risk filters passed, False otherwise
        """
        if len(self.rsi_values) == 0:
            return True, "Risk filters passed (no RSI data)"

        current_rsi = self.rsi_values[-1]

        # Overextended RSI
        if current_rsi > self.config.rsi_overbought_threshold:
            return False, f"RSI {current_rsi:.0f} overextended (>{self.config.rsi_overbought_threshold})"

        # OI Spike + Flat Price = Possible Trap
        oi_change = self._get_oi_change_pct()
        if oi_change is not None and oi_change >= self.config.oi_increase_threshold:
            # Check if price is flat (low volatility despite OI spike)
            if len(self.closes) >= 5:
                price_change_pct = abs((self.closes[-1] - self.closes[-5]) / self.closes[-5]) * Decimal("100")
                if price_change_pct < self.config.trap_detection_price_move_pct:
                    return False, f"OI spike +{oi_change*100:.0f}% but price flat (trap?)"

        return True, "Risk filters passed"

    def _get_nearest_resistance(self, price: Decimal) -> Optional[Decimal]:
        """
        Get nearest resistance level above current price.

        Returns:
            Resistance level above price, or None if price exceeds all levels.

        Note: When price exceeds all stored resistance levels, this returns None
        to indicate a true breakout beyond all known resistance, not a routine
        price move within historical ranges.
        """
        if not self.resistance_levels:
            return None

        # Find first resistance above current price (search ascending order)
        for level in sorted(self.resistance_levels):
            if level >= price * (Decimal("1") - self.config.sr_tolerance_pct / Decimal("100")):
                return level

        # Price exceeds all resistance levels - return None
        # This prevents falsely classifying routine price action as breakouts
        # when comparing against irrelevant low historical levels
        return None

    def _get_oi_change_pct(self) -> Optional[Decimal]:
        """Calculate Open Interest change percentage over last 24 data points."""
        if len(self.open_interest_history) < 2:
            return None

        old_oi = self.open_interest_history[0]
        new_oi = self.open_interest_history[-1]

        # Robust zero check: use small threshold instead of exact zero
        if old_oi <= Decimal("0.000001"):
            return None

        return (new_oi - old_oi) / old_oi

    def _create_signal_from_setup(self, setup: SetupSignal, bar: Bar) -> Signal:
        """Convert SetupSignal to standard Signal format."""
        # Calculate position size
        qty = self.config.position_size_usd / bar.close

        # Set stop loss below resistance (or recent support)
        if setup.resistance_level:
            sl_price = setup.resistance_level * self.config.stop_loss_pct_below_resistance
        else:
            sl_price = bar.close * self.config.stop_loss_pct_fallback

        # Set take profit based on R:R ratio
        risk = bar.close - sl_price
        tp_price = bar.close + (risk * self.config.take_profit_risk_reward_ratio)

        signal = Signal(
            symbol=self.symbol,
            side="buy",
            qty=qty,
            price=bar.close,
            sl=sl_price,
            tp=tp_price,
            reason=f"Breakout setup: {', '.join(setup.conditions_met[:3])}"
        )

        return signal

    def update_derivatives_data(
        self,
        open_interest: Optional[Decimal] = None,
        funding_rate: Optional[Decimal] = None,
        put_call_ratio: Optional[Decimal] = None
    ) -> None:
        """
        Update derivatives data (call externally when data available).

        Args:
            open_interest: Current open interest value
            funding_rate: Current funding rate (per 8h for perps)
            put_call_ratio: Current put/call ratio for options
        """
        current_time = int(time.time())

        if open_interest is not None:
            self.open_interest_history.append(open_interest)
            self.oi_last_update = current_time

        if funding_rate is not None:
            self.current_funding_rate = funding_rate
            self.funding_last_update = current_time

        if put_call_ratio is not None:
            self.current_put_call_ratio = put_call_ratio
            self.put_call_last_update = current_time

    def reset(self) -> None:
        """Reset strategy state."""
        self.closes.clear()
        self.highs.clear()
        self.lows.clear()
        self.volumes.clear()
        self.rsi_values.clear()
        self.macd_values.clear()
        self.macd_signal_values.clear()
        self.macd_histogram_values.clear()
        self.resistance_levels.clear()
        self.support_levels.clear()
        self.open_interest_history.clear()
        self.current_funding_rate = None
        self.current_put_call_ratio = None
        self.oi_last_update = None
        self.funding_last_update = None
        self.put_call_last_update = None
        self._prev_avg_gain = None
        self._prev_avg_loss = None
        self.last_signal_time = 0
        self.signal_count = 0

        logger.info(f"BreakoutSetupDetector reset: {self.symbol}")
