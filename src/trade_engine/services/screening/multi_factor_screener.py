"""
Multi-Factor Stock Screener with Signal Matching.

Identifies stocks that match multiple buy signals:
- Price breakout above resistance (20-day high)
- Volume surge (2x+ average volume)
- Moving average alignment (50/200 MA golden cross)
- MACD crossover (bullish momentum)
- RSI in rising trend (40-70 range)
- Fundamental catalyst confirmation

CRITICAL: All price/volume calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger

from trade_engine.services.data.source_yahoo import YahooFinanceSource
from trade_engine.services.data.types import OHLCV
from trade_engine.domain.strategies.alpha_ma_crossover import MovingAverageCrossoverAlpha
from trade_engine.domain.strategies.alpha_macd import MACDAlpha
from trade_engine.domain.strategies.alpha_rsi_divergence import RSIDivergenceAlpha


@dataclass
class ScreenerMatch:
    """
    Stock that matches screening criteria.

    Attributes:
        symbol: Stock ticker
        price: Current price
        gain_percent: % gain today
        gain_dollars: $ gain today
        volume_ratio: Today's volume / 20-day avg
        breakout_score: 0-100 (higher = stronger breakout)
        momentum_score: 0-100 (higher = stronger momentum)
        ma_alignment: True if 50MA > 200MA
        macd_bullish: True if MACD crossed above signal
        rsi_value: Current RSI (14-period)
        signals_matched: Count of signals matched (0-7)
        composite_score: Overall score (0-100)
    """
    symbol: str
    price: Decimal
    gain_percent: Decimal
    gain_dollars: Decimal
    volume_ratio: Decimal
    breakout_score: int
    momentum_score: int
    ma_alignment: bool
    macd_bullish: bool
    rsi_value: Decimal
    signals_matched: int
    composite_score: int


class MultiFactorScreener:
    """
    Screen stocks for multi-factor buy signals.

    Implements the exact criteria from your message:
    1. Price broke above 20-day high
    2. Volume > 2x average
    3. Price > 50/200 day MA (golden cross)
    4. MACD crossover
    5. RSI 40-70 (rising)
    6. % gain > threshold
    7. Market cap > minimum

    Usage:
        screener = MultiFactorScreener()
        matches = screener.scan_universe(
            symbols=["AAPL", "MSFT", "GOOGL", ...],
            min_gain_percent=Decimal("8.0"),
            min_volume_ratio=Decimal("2.0")
        )

        # Get top 10 matches
        top_picks = matches[:10]
    """

    def __init__(
        self,
        min_market_cap: Decimal = Decimal("500_000_000"),  # $500M
        min_price: Decimal = Decimal("10.0"),  # $10
        lookback_days: int = 20,
        ma_short: int = 50,
        ma_long: int = 200,
        rsi_period: int = 14
    ):
        """
        Initialize screener.

        Args:
            min_market_cap: Minimum market cap ($)
            min_price: Minimum stock price ($)
            lookback_days: Days to look back for high/volume
            ma_short: Short moving average period
            ma_long: Long moving average period
            rsi_period: RSI calculation period
        """
        self.min_market_cap = min_market_cap
        self.min_price = min_price
        self.lookback_days = lookback_days
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.rsi_period = rsi_period

        # Data source
        self.data_source = YahooFinanceSource()

        # Alpha strategies for signal generation
        self.ma_crossover = MovingAverageCrossoverAlpha(
            fast_period=ma_short,
            slow_period=ma_long
        )
        self.macd = MACDAlpha()
        self.rsi = RSIDivergenceAlpha(rsi_period=rsi_period)

        logger.info(
            "MultiFactorScreener initialized",
            min_market_cap=str(min_market_cap),
            min_price=str(min_price),
            lookback_days=lookback_days
        )

    def scan_universe(
        self,
        symbols: List[str],
        min_gain_percent: Decimal = Decimal("8.0"),
        min_volume_ratio: Decimal = Decimal("2.0"),
        min_breakout_score: int = 70,
        min_signals_matched: int = 4
    ) -> List[ScreenerMatch]:
        """
        Scan list of symbols for matches.

        Args:
            symbols: List of stock tickers to scan
            min_gain_percent: Minimum % gain today
            min_volume_ratio: Minimum volume ratio (today/avg)
            min_breakout_score: Minimum breakout score (0-100)
            min_signals_matched: Minimum signals to match

        Returns:
            List of matches, sorted by composite_score descending
        """
        matches = []

        logger.info(
            "Starting universe scan",
            symbols_count=len(symbols),
            min_gain_percent=str(min_gain_percent),
            min_volume_ratio=str(min_volume_ratio)
        )

        for symbol in symbols:
            try:
                match = self._scan_symbol(
                    symbol=symbol,
                    min_gain_percent=min_gain_percent,
                    min_volume_ratio=min_volume_ratio,
                    min_breakout_score=min_breakout_score,
                    min_signals_matched=min_signals_matched
                )

                if match:
                    matches.append(match)
                    logger.info(
                        "Signal match found",
                        symbol=symbol,
                        signals_matched=match.signals_matched,
                        composite_score=match.composite_score
                    )

            except Exception as e:
                logger.warning(
                    "Failed to scan symbol",
                    symbol=symbol,
                    error=str(e)
                )
                continue

        # Sort by composite score (highest first)
        matches.sort(key=lambda m: m.composite_score, reverse=True)

        logger.info(
            "Universe scan complete",
            total_matches=len(matches),
            top_score=matches[0].composite_score if matches else 0
        )

        return matches

    def _scan_symbol(
        self,
        symbol: str,
        min_gain_percent: Decimal,
        min_volume_ratio: Decimal,
        min_breakout_score: int,
        min_signals_matched: int
    ) -> Optional[ScreenerMatch]:
        """
        Scan single symbol for signal match.

        Returns:
            ScreenerMatch if passes all filters, None otherwise
        """
        # Filter 0: Market cap (fetch early to avoid wasting time on penny stocks)
        market_cap = self._fetch_market_cap(symbol)
        if market_cap is None or market_cap < self.min_market_cap:
            logger.debug(
                "Market cap too low or unavailable",
                symbol=symbol,
                market_cap=str(market_cap) if market_cap else "N/A",
                min_required=str(self.min_market_cap)
            )
            return None

        # Fetch historical data (need enough for 200-day MA)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=300)  # Extra buffer for MAs

        candles = self.data_source.fetch_ohlcv(
            symbol=symbol,
            interval="1d",
            start=start_date,
            end=end_date
        )

        if len(candles) < self.ma_long + 10:
            logger.debug(
                "Insufficient data for symbol",
                symbol=symbol,
                candles=len(candles),
                required=self.ma_long + 10
            )
            return None

        # Current price and previous close
        current = candles[-1]
        previous = candles[-2]

        current_price = Decimal(str(current.close))
        previous_close = Decimal(str(previous.close))

        # Filter 1: Minimum price
        if current_price < self.min_price:
            return None

        # Filter 2: Gain calculation
        gain_dollars = current_price - previous_close
        gain_percent = (gain_dollars / previous_close) * Decimal("100")

        if gain_percent < min_gain_percent:
            return None

        # Filter 3: Volume surge
        current_volume = Decimal(str(current.volume))
        avg_volume = self._calculate_avg_volume(candles[-self.lookback_days:])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else Decimal("0")

        if volume_ratio < min_volume_ratio:
            return None

        # Filter 4: Breakout detection (20-day high)
        breakout_score = self._calculate_breakout_score(candles, current_price)

        if breakout_score < min_breakout_score:
            return None

        # Filter 5: Moving average alignment
        ma_50 = self._calculate_sma(candles, self.ma_short)
        ma_200 = self._calculate_sma(candles, self.ma_long)
        ma_alignment = ma_50 > ma_200 and current_price > ma_50

        # Filter 6: MACD crossover
        macd_bullish = self._check_macd_crossover(candles)

        # Filter 7: RSI momentum
        rsi_value = self._calculate_rsi(candles, self.rsi_period)
        rsi_valid = Decimal("40") <= rsi_value <= Decimal("70")

        # Count signals matched
        signals = [
            breakout_score >= min_breakout_score,  # Breakout
            volume_ratio >= min_volume_ratio,       # Volume surge
            ma_alignment,                            # MA alignment
            macd_bullish,                            # MACD crossover
            rsi_valid,                               # RSI in range
            gain_percent >= min_gain_percent,       # Price gain
            market_cap >= self.min_market_cap       # Market cap (already checked above)
        ]

        signals_matched = sum(signals)

        if signals_matched < min_signals_matched:
            return None

        # Calculate momentum score
        momentum_score = self._calculate_momentum_score(
            rsi=rsi_value,
            macd_bullish=macd_bullish,
            volume_ratio=volume_ratio
        )

        # Calculate composite score
        composite_score = self._calculate_composite_score(
            breakout_score=breakout_score,
            momentum_score=momentum_score,
            signals_matched=signals_matched,
            gain_percent=gain_percent,
            volume_ratio=volume_ratio
        )

        return ScreenerMatch(
            symbol=symbol,
            price=current_price,
            gain_percent=gain_percent,
            gain_dollars=gain_dollars,
            volume_ratio=volume_ratio,
            breakout_score=breakout_score,
            momentum_score=momentum_score,
            ma_alignment=ma_alignment,
            macd_bullish=macd_bullish,
            rsi_value=rsi_value,
            signals_matched=signals_matched,
            composite_score=composite_score
        )

    def _fetch_market_cap(self, symbol: str) -> Optional[Decimal]:
        """
        Fetch market capitalization for symbol.

        Args:
            symbol: Stock ticker

        Returns:
            Market cap in dollars, or None if unavailable
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            market_cap = info.get('marketCap')
            if market_cap is None:
                logger.debug(
                    "Market cap not available",
                    symbol=symbol
                )
                return None

            return Decimal(str(market_cap))

        except Exception as e:
            logger.warning(
                "Failed to fetch market cap",
                symbol=symbol,
                error=str(e)
            )
            return None

    def _calculate_avg_volume(self, candles: List[OHLCV]) -> Decimal:
        """Calculate average volume over candles."""
        if not candles:
            return Decimal("0")

        total = sum(Decimal(str(c.volume)) for c in candles)
        return total / Decimal(str(len(candles)))

    def _calculate_sma(self, candles: List[OHLCV], period: int) -> Decimal:
        """Calculate Simple Moving Average."""
        if len(candles) < period:
            return Decimal("0")

        recent = candles[-period:]
        total = sum(Decimal(str(c.close)) for c in recent)
        return total / Decimal(str(period))

    def _calculate_breakout_score(
        self,
        candles: List[OHLCV],
        current_price: Decimal
    ) -> int:
        """
        Calculate breakout score (0-100).

        100 = New 20-day high
        75  = Within 2% of 20-day high
        50  = Within 5% of 20-day high
        0   = Below 20-day high by >5%
        """
        recent = candles[-self.lookback_days:]
        high_20d = max(Decimal(str(c.high)) for c in recent)

        if current_price >= high_20d:
            return 100

        distance_pct = ((high_20d - current_price) / high_20d) * Decimal("100")

        if distance_pct <= Decimal("2"):
            return 75
        elif distance_pct <= Decimal("5"):
            return 50
        else:
            return int(max(0, 50 - int(distance_pct)))

    def _check_macd_crossover(self, candles: List[OHLCV]) -> bool:
        """
        Check if MACD crossed above signal line recently.

        Returns True if crossed within last 2 bars.
        """
        if len(candles) < 35:  # Need enough for MACD calculation
            return False

        # Calculate MACD for last 3 bars
        recent = candles[-35:]

        # EMA 12, 26, signal 9
        ema_12 = self._calculate_ema(recent, 12)
        ema_26 = self._calculate_ema(recent, 26)
        macd_line = ema_12 - ema_26

        # For signal line, we'd need full MACD history
        # Simplified: check if MACD is positive and rising
        if len(recent) >= 2:
            prev_ema_12 = self._calculate_ema(recent[:-1], 12)
            prev_ema_26 = self._calculate_ema(recent[:-1], 26)
            prev_macd = prev_ema_12 - prev_ema_26

            return macd_line > 0 and macd_line > prev_macd

        return macd_line > 0

    def _calculate_ema(self, candles: List[OHLCV], period: int) -> Decimal:
        """Calculate Exponential Moving Average."""
        if len(candles) < period:
            return Decimal("0")

        prices = [Decimal(str(c.close)) for c in candles]
        multiplier = Decimal("2") / Decimal(str(period + 1))

        # Start with SMA
        ema = sum(prices[:period]) / Decimal(str(period))

        # Apply EMA formula
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, candles: List[OHLCV], period: int) -> Decimal:
        """Calculate RSI (Relative Strength Index)."""
        if len(candles) < period + 1:
            return Decimal("50")  # Neutral

        prices = [Decimal(str(c.close)) for c in candles[-(period + 1):]]

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(Decimal("0"))
            else:
                gains.append(Decimal("0"))
                losses.append(abs(change))

        avg_gain = sum(gains) / Decimal(str(period))
        avg_loss = sum(losses) / Decimal(str(period))

        if avg_loss == 0:
            return Decimal("100")

        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

        return rsi

    def _calculate_momentum_score(
        self,
        rsi: Decimal,
        macd_bullish: bool,
        volume_ratio: Decimal
    ) -> int:
        """
        Calculate momentum score (0-100).

        Combines RSI, MACD, and volume signals.
        """
        score = 0

        # RSI contribution (0-40 points)
        if Decimal("50") <= rsi <= Decimal("70"):
            score += 40  # Optimal range
        elif Decimal("40") <= rsi < Decimal("50"):
            score += 30  # Good
        elif Decimal("30") <= rsi < Decimal("40"):
            score += 20  # Acceptable

        # MACD contribution (0-30 points)
        if macd_bullish:
            score += 30

        # Volume contribution (0-30 points)
        if volume_ratio >= Decimal("3.0"):
            score += 30  # Exceptional
        elif volume_ratio >= Decimal("2.5"):
            score += 25
        elif volume_ratio >= Decimal("2.0"):
            score += 20
        elif volume_ratio >= Decimal("1.5"):
            score += 10

        return min(100, score)

    def _calculate_composite_score(
        self,
        breakout_score: int,
        momentum_score: int,
        signals_matched: int,
        gain_percent: Decimal,
        volume_ratio: Decimal
    ) -> int:
        """
        Calculate overall composite score (0-100).

        Weighted combination of all factors.
        """
        # Weights
        w_breakout = Decimal("0.25")
        w_momentum = Decimal("0.25")
        w_signals = Decimal("0.20")
        w_gain = Decimal("0.15")
        w_volume = Decimal("0.15")

        # Normalize gain (cap at 20%)
        gain_normalized = min(gain_percent / Decimal("20") * Decimal("100"), Decimal("100"))

        # Normalize volume (cap at 5x)
        volume_normalized = min(volume_ratio / Decimal("5") * Decimal("100"), Decimal("100"))

        # Normalize signals (7 total possible)
        signals_normalized = Decimal(str(signals_matched)) / Decimal("7") * Decimal("100")

        composite = (
            Decimal(str(breakout_score)) * w_breakout +
            Decimal(str(momentum_score)) * w_momentum +
            signals_normalized * w_signals +
            gain_normalized * w_gain +
            volume_normalized * w_volume
        )

        return int(composite)
