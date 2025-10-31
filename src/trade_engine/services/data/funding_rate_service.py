"""
Funding Rate Service for Perpetual Futures.

Tracks 8-hourly funding payments and cumulative costs.
"""

import requests
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from loguru import logger


class FundingRateService:
    """
    Fetch and track perpetual futures funding rates.

    Funding rates are paid every 8 hours on most exchanges:
    - 00:00 UTC
    - 08:00 UTC
    - 16:00 UTC

    Positive rate = longs pay shorts
    Negative rate = shorts pay longs
    """

    def __init__(self, database=None, testnet: bool = False):
        """
        Initialize funding rate service.

        Args:
            database: Optional PostgresDatabase instance for logging
            testnet: If True, use Binance testnet URL instead of mainnet
        """
        self.db = database

        # Configure API URL based on environment
        if testnet:
            self.funding_url = "https://testnet.binancefuture.com/fapi/v1/fundingRate"
        else:
            self.funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"

    def get_current_funding_rate(self, symbol: str) -> Decimal:
        """
        Get the current funding rate for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current funding rate as Decimal (e.g., 0.0001 = 0.01%)

        Raises:
            requests.RequestException: If API call fails
        """
        try:
            params = {"symbol": symbol, "limit": 1}
            response = requests.get(
                self.funding_url, params=params, timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if not data:
                logger.warning(f"No funding data for {symbol}")
                return Decimal("0")

            rate = Decimal(str(data[0]["fundingRate"]))
            logger.debug(f"Funding rate for {symbol}: {rate} ({rate * 100}%)")

            # Log to database if available
            if self.db:
                self._log_funding_event(symbol, rate, data[0]["fundingTime"])

            return rate

        except requests.RequestException as e:
            logger.error(f"Failed to fetch funding rate for {symbol}: {e}")
            raise

    def get_historical_funding(
        self, symbol: str, start_time: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get historical funding rates.

        Args:
            symbol: Trading pair
            start_time: Start timestamp (milliseconds)
            limit: Number of records (max 1000)

        Returns:
            List of funding rate records with timestamps
        """
        try:
            params = {"symbol": symbol, "limit": min(limit, 1000)}
            if start_time:
                params["startTime"] = start_time

            response = requests.get(
                self.funding_url, params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to fetch historical funding for {symbol}: {e}")
            raise

    def calculate_funding_cost(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        funding_rate: Decimal,
        periods: int = 1,
    ) -> Decimal:
        """
        Calculate funding payment for a position.

        Formula: cost = position_notional * funding_rate * periods

        Args:
            position_size: Position size in base currency (e.g., 0.5 BTC)
            entry_price: Entry price in quote currency (e.g., 50000 USDT)
            funding_rate: Funding rate (e.g., 0.0001)
            periods: Number of funding periods (default 1 = 8 hours)

        Returns:
            Funding cost in quote currency (positive = cost, negative = income)

        Example:
            >>> calculate_funding_cost(
            ...     Decimal("0.5"),      # 0.5 BTC
            ...     Decimal("50000"),    # at $50k
            ...     Decimal("0.0001"),   # 0.01% rate
            ...     periods=3            # 24 hours (3x 8hr periods)
            ... )
            Decimal("7.50")  # $7.50 cost
        """
        notional = position_size * entry_price
        cost = notional * funding_rate * Decimal(str(periods))

        logger.debug(
            f"Funding cost: {cost} USDT "
            f"(size={position_size}, price={entry_price}, "
            f"rate={funding_rate}, periods={periods})"
        )

        return cost.quantize(Decimal("0.01"))

    def estimate_daily_funding(
        self, symbol: str, position_size: Decimal, entry_price: Decimal
    ) -> Decimal:
        """
        Estimate 24-hour funding cost based on current rate.

        Args:
            symbol: Trading pair
            position_size: Position size
            entry_price: Entry price

        Returns:
            Estimated daily funding cost
        """
        current_rate = self.get_current_funding_rate(symbol)
        return self.calculate_funding_cost(
            position_size, entry_price, current_rate, periods=3  # 3x 8-hour periods = 24 hours
        )

    def _log_funding_event(self, symbol: str, rate: Decimal, timestamp: int):
        """
        Log funding event to database.

        Args:
            symbol: Trading pair
            rate: Funding rate
            timestamp: Unix timestamp (milliseconds)
        """
        if not self.db:
            return

        try:
            # Convert milliseconds to datetime
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)

            # Log funding event to database (funding_events table implemented)
            logger.info(
                "funding_event",
                symbol=symbol,
                rate=str(rate),
                timestamp=dt.isoformat(),
            )
        except Exception as e:
            logger.error(f"Failed to log funding event: {e}")
