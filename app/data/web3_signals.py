"""
Web3 data source for on-chain trading signals.

This module provides read-only access to blockchain data using 100% FREE APIs:
- Gas prices (Etherscan API - no key required)
- DEX liquidity (The Graph - decentralized, no key)
- Funding rates (dYdX public API - no key)

All data sources are free with generous rate limits. No paid subscriptions needed.

V2 Update: Added signal normalization to convert raw values to [-1.0, +1.0] range
for consistent signal combination.
"""

import requests
from typing import Dict, Optional, List, Literal
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from loguru import logger
from app.data.signal_normalizer import SignalNormalizer


@dataclass
class GasData:
    """Current gas price information."""
    safe_gas_price: float  # gwei
    propose_gas_price: float  # gwei
    fast_gas_price: float  # gwei
    timestamp: datetime


@dataclass
class LiquidityData:
    """DEX liquidity information."""
    pool_address: str
    token0: str
    token1: str
    liquidity: float
    volume_24h_usd: float
    timestamp: datetime


@dataclass
class FundingRateData:
    """Perpetual funding rate data."""
    symbol: str
    funding_rate: float  # As decimal (0.01 = 1%)
    next_funding_time: datetime
    timestamp: datetime


@dataclass
class Web3Signal:
    """
    Combined Web3 signal score.

    V2: Now includes normalized signal values in [-1.0, +1.0] range for
    consistent signal combination with L2 order book imbalance.
    """
    score: float  # -3.0 to +3.0 (sum of normalized signals)
    gas_data: Optional[GasData]
    liquidity_data: Optional[LiquidityData]
    funding_data: Optional[FundingRateData]
    signal: str  # "BUY", "SELL", "NEUTRAL"
    confidence: float  # 0.0 to 1.0
    timestamp: datetime
    # V2: Normalized signal values
    normalized_gas: Optional[float] = None  # -1.0 to +1.0
    normalized_liquidity: Optional[float] = None  # -1.0 to +1.0
    normalized_funding: Optional[float] = None  # -1.0 to +1.0


class Web3DataSource:
    """
    Free Web3 data source for trading signals.

    Uses only free public APIs:
    - Etherscan (no API key required for basic calls)
    - The Graph (decentralized subgraphs - completely free)
    - dYdX public API (no authentication)

    All methods include error handling and return None on failure.
    """

    # Free public endpoints (no API keys required)
    ETHERSCAN_API = "https://api.etherscan.io/api"
    # The Graph decentralized gateway (more reliable)
    UNISWAP_SUBGRAPH = "https://gateway-arbitrum.network.thegraph.com/api/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
    # dYdX v4 public API (v3 deprecated)
    DYDX_API = "https://indexer.dydx.trade/v4"

    # Known Uniswap V3 pool addresses
    POOLS = {
        "WBTC/USDC": "0x9db9e0e53058c89e5b94e29621a205198648425b",
        "ETH/USDC": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "WBTC/ETH": "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed",
    }

    def __init__(
        self,
        timeout: int = 5,
        retry_attempts: int = 2,
        normalize: bool = True,
        normalization_method: Literal["zscore", "percentile"] = "zscore"
    ):
        """
        Initialize Web3 data source.

        Args:
            timeout: Request timeout in seconds (default: 5)
            retry_attempts: Number of retry attempts on failure (default: 2)
            normalize: Enable signal normalization (default: True)
            normalization_method: "zscore" or "percentile" (default: "zscore")
        """
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.normalize = normalize
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MFT-Bot/1.0",
            "Accept": "application/json"
        })

        # Initialize signal normalizer if enabled
        if self.normalize:
            self.normalizer = SignalNormalizer(
                method=normalization_method,
                lookback_days=30
            )
        else:
            self.normalizer = None

    def _make_request(
        self,
        url: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        method: str = "GET"
    ) -> Optional[Dict]:
        """
        Make HTTP request with retry logic.

        Args:
            url: Request URL
            params: Query parameters (for GET)
            json_data: JSON body (for POST)
            method: HTTP method (GET or POST)

        Returns:
            JSON response dict or None on failure
        """
        for attempt in range(self.retry_attempts):
            try:
                if method == "GET":
                    response = self.session.get(
                        url,
                        params=params,
                        timeout=self.timeout
                    )
                else:  # POST
                    response = self.session.post(
                        url,
                        json=json_data,
                        timeout=self.timeout
                    )

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.retry_attempts}): {url}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")

            if attempt < self.retry_attempts - 1:
                # Brief pause before retry
                import time
                time.sleep(0.5)

        logger.error(f"All retry attempts failed for: {url}")
        return None

    def get_gas_prices(self) -> Optional[GasData]:
        """
        Get current Ethereum gas prices from Etherscan (free).

        Returns gas price recommendations in gwei:
        - safe_gas_price: Low priority (slower, cheaper)
        - propose_gas_price: Standard priority
        - fast_gas_price: High priority (faster, expensive)

        Returns:
            GasData object or None on failure

        Example:
            >>> source = Web3DataSource()
            >>> gas = source.get_gas_prices()
            >>> if gas and gas.safe_gas_price > 100:
            ...     print("Gas too high - avoid trading")
        """
        params = {
            "module": "gastracker",
            "action": "gasoracle"
        }

        data = self._make_request(self.ETHERSCAN_API, params=params)

        if not data or data.get("status") != "1":
            logger.warning("Failed to fetch gas prices from Etherscan")
            return None

        result = data["result"]

        return GasData(
            safe_gas_price=float(result["SafeGasPrice"]),
            propose_gas_price=float(result["ProposeGasPrice"]),
            fast_gas_price=float(result["FastGasPrice"]),
            timestamp=datetime.now(timezone.utc)
        )

    def get_dex_liquidity(
        self,
        pool: str = "WBTC/USDC"
    ) -> Optional[LiquidityData]:
        """
        Get DEX liquidity data from Uniswap V3 via The Graph (free).

        The Graph is a decentralized indexing protocol - completely free,
        no API key required, no rate limits.

        Args:
            pool: Pool name (e.g., "WBTC/USDC", "ETH/USDC")

        Returns:
            LiquidityData object or None on failure

        Example:
            >>> source = Web3DataSource()
            >>> liquidity = source.get_dex_liquidity("WBTC/USDC")
            >>> if liquidity and liquidity.volume_24h_usd < 1_000_000:
            ...     print("Low liquidity - risky trading conditions")
        """
        pool_address = self.POOLS.get(pool)
        if not pool_address:
            logger.error(f"Unknown pool: {pool}. Available: {list(self.POOLS.keys())}")
            return None

        # GraphQL query for pool data
        query = """
        {
          pool(id: "%s") {
            token0 {
              symbol
            }
            token1 {
              symbol
            }
            liquidity
            volumeUSD
            feeTier
          }
        }
        """ % pool_address.lower()

        data = self._make_request(
            self.UNISWAP_SUBGRAPH,
            json_data={"query": query},
            method="POST"
        )

        if not data or "errors" in data:
            logger.warning(f"Failed to fetch liquidity from The Graph: {data}")
            return None

        pool_data = data.get("data", {}).get("pool")
        if not pool_data:
            logger.warning(f"No pool data returned for {pool}")
            return None

        return LiquidityData(
            pool_address=pool_address,
            token0=pool_data["token0"]["symbol"],
            token1=pool_data["token1"]["symbol"],
            liquidity=float(pool_data["liquidity"]),
            volume_24h_usd=float(pool_data["volumeUSD"]),
            timestamp=datetime.now(timezone.utc)
        )

    def get_funding_rate(
        self,
        symbol: str = "BTC-USD"
    ) -> Optional[FundingRateData]:
        """
        Get perpetual funding rate from dYdX (free public API).

        Funding rate indicates market sentiment:
        - Positive (> 0.01%): Longs paying shorts → Too many longs (bearish)
        - Negative (< -0.01%): Shorts paying longs → Too many shorts (bullish)
        - Near zero: Balanced market

        Args:
            symbol: Market symbol (e.g., "BTC-USD", "ETH-USD")

        Returns:
            FundingRateData object or None on failure

        Example:
            >>> source = Web3DataSource()
            >>> funding = source.get_funding_rate("BTC-USD")
            >>> if funding and funding.funding_rate > 0.01:
            ...     print("Overleveraged longs - bearish signal")
        """
        url = f"{self.DYDX_API}/markets/{symbol}"

        data = self._make_request(url)

        if not data or "market" not in data:
            logger.warning(f"Failed to fetch funding rate for {symbol}")
            return None

        market = data["market"]

        # Parse next funding time
        next_funding = datetime.fromisoformat(
            market["nextFundingAt"].replace("Z", "+00:00")
        )

        return FundingRateData(
            symbol=symbol,
            funding_rate=float(market["nextFundingRate"]),
            next_funding_time=next_funding,
            timestamp=datetime.now(timezone.utc)
        )

    def get_combined_signal(
        self,
        pool: str = "WBTC/USDC",
        funding_symbol: str = "BTC-USD"
    ) -> Web3Signal:
        """
        Combine all Web3 signals into a single trading signal.

        V2: Now uses normalized signal values in [-1.0, +1.0] range for
        consistent signal combination. Normalization builds up history
        over time for better signal quality.

        Signal scoring (with normalization enabled):
        - Gas price: Normalized to [-1.0, +1.0] (high gas → negative)
        - Funding rate: Normalized to [-1.0, +1.0] (positive → negative)
        - Liquidity: Normalized to [-1.0, +1.0] (low volume → negative)

        Signal scoring (legacy mode, normalize=False):
        - Gas price: -1 if extreme (>100 gwei)
        - Funding rate: +1 if negative (bullish), -1 if positive (bearish)
        - Liquidity: -1 if low volume (<$1M)

        Final signal:
        - score > 0: BUY (bullish signals dominant)
        - score < 0: SELL (bearish signals dominant)
        - score = 0: NEUTRAL (conflicting or weak signals)

        Args:
            pool: DEX pool to monitor
            funding_symbol: Perpetual market symbol

        Returns:
            Web3Signal with combined score and recommendation

        Example:
            >>> source = Web3DataSource(normalize=True)
            >>> signal = source.get_combined_signal()
            >>> print(f"Signal: {signal.signal} (score: {signal.score:.2f})")
            >>> print(f"Normalized gas: {signal.normalized_gas:.2f}")
        """
        score = 0.0
        signals_available = 0

        # Fetch all data sources
        gas = self.get_gas_prices()
        liquidity = self.get_dex_liquidity(pool)
        funding = self.get_funding_rate(funding_symbol)

        # Track normalized values
        normalized_gas = None
        normalized_liquidity = None
        normalized_funding = None

        if self.normalize and self.normalizer:
            # === V2: Normalized signal scoring ===
            # All signals normalized to [-1.0, +1.0] range

            # Score: Gas prices (inverted - high gas is bearish)
            if gas:
                signals_available += 1
                normalized_gas = -self.normalizer.normalize(
                    gas.propose_gas_price,
                    "gas_price"
                )
                score += normalized_gas
                logger.info(f"Gas: {gas.propose_gas_price:.0f} gwei → normalized: {normalized_gas:.3f}")

            # Score: Funding rate (inverted - positive funding is bearish)
            if funding:
                signals_available += 1
                normalized_funding = -self.normalizer.normalize(
                    funding.funding_rate,
                    "funding_rate"
                )
                score += normalized_funding
                logger.info(f"Funding: {funding.funding_rate:.4f} → normalized: {normalized_funding:.3f}")

            # Score: Liquidity (inverted - low liquidity is bearish)
            if liquidity:
                signals_available += 1
                normalized_liquidity = -self.normalizer.normalize(
                    1_000_000 - liquidity.volume_24h_usd,  # Invert so low volume = high value
                    "liquidity_deficit"
                )
                score += normalized_liquidity
                logger.info(f"Liquidity: ${liquidity.volume_24h_usd:,.0f} → normalized: {normalized_liquidity:.3f}")

        else:
            # === Legacy: Threshold-based scoring ===
            # Score: Gas prices
            if gas:
                signals_available += 1
                if gas.propose_gas_price > 100:
                    score -= 1  # Extreme gas = volatility, avoid trading
                    logger.info(f"High gas detected: {gas.propose_gas_price} gwei (bearish)")

            # Score: Funding rate
            if funding:
                signals_available += 1
                if funding.funding_rate < -0.01:  # -1% or more
                    score += 1  # Shorts paying longs = bullish
                    logger.info(f"Negative funding: {funding.funding_rate:.4f} (bullish)")
                elif funding.funding_rate > 0.01:  # +1% or more
                    score -= 1  # Longs paying shorts = bearish
                    logger.info(f"Positive funding: {funding.funding_rate:.4f} (bearish)")

            # Score: Liquidity
            if liquidity:
                signals_available += 1
                if liquidity.volume_24h_usd < 1_000_000:
                    score -= 1  # Low liquidity = risky
                    logger.info(f"Low liquidity: ${liquidity.volume_24h_usd:,.0f} (bearish)")

        # Determine signal
        if score > 0:
            signal = "BUY"
        elif score < 0:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        # Calculate confidence based on data availability
        confidence = signals_available / 3.0  # 3 signals max

        return Web3Signal(
            score=score,
            gas_data=gas,
            liquidity_data=liquidity,
            funding_data=funding,
            signal=signal,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            normalized_gas=normalized_gas,
            normalized_liquidity=normalized_liquidity,
            normalized_funding=normalized_funding
        )

    def is_high_volatility(self) -> bool:
        """
        Check if current conditions indicate high volatility.

        High volatility conditions (avoid trading):
        - Gas price > 100 gwei (network congestion)
        - Funding rate magnitude > 2% (extreme leverage)

        Returns:
            True if high volatility detected, False otherwise

        Example:
            >>> source = Web3DataSource()
            >>> if source.is_high_volatility():
            ...     print("Skip trading - market too volatile")
        """
        gas = self.get_gas_prices()
        funding = self.get_funding_rate()

        # Check gas price
        if gas and gas.propose_gas_price > 100:
            logger.warning(f"High volatility: Gas = {gas.propose_gas_price} gwei")
            return True

        # Check funding rate extremes
        if funding and abs(funding.funding_rate) > 0.02:  # 2%
            logger.warning(f"High volatility: Funding = {funding.funding_rate:.4f}")
            return True

        return False


# Convenience function for quick signal checks
def get_web3_signal() -> Web3Signal:
    """
    Quick helper to get current Web3 signal.

    Returns:
        Web3Signal with current market conditions

    Example:
        >>> from app.data.web3_signals import get_web3_signal
        >>> signal = get_web3_signal()
        >>> if signal.signal == "BUY" and signal.confidence > 0.7:
        ...     print("Strong bullish signal from on-chain data")
    """
    source = Web3DataSource()
    return source.get_combined_signal()
