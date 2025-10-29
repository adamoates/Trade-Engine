"""
Kraken Futures broker adapter (US-accessible).

Implements Broker interface for Kraken Futures perpetual contracts.
Supports both demo environment (paper trading) and production.

CRITICAL: All price/quantity conversions use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

import os
import time
import hmac
import hashlib
import base64
from decimal import Decimal
from typing import Dict, Optional
import requests
from loguru import logger

from trade_engine.core.types import Broker, Position


class KrakenError(Exception):
    """Kraken API errors."""
    pass


class KrakenFuturesBroker(Broker):
    """
    Kraken Futures broker (demo or live).

    Usage:
        # Demo environment (paper trading)
        broker = KrakenFuturesBroker(demo=True)

        # Live (real money)
        broker = KrakenFuturesBroker(demo=False)

    Environment variables required:
        KRAKEN_API_KEY       (or KRAKEN_DEMO_API_KEY for demo)
        KRAKEN_API_SECRET    (or KRAKEN_DEMO_API_SECRET for demo)
    """

    DEMO_BASE = "https://demo-futures.kraken.com/derivatives/api/v3"
    LIVE_BASE = "https://futures.kraken.com/derivatives/api/v3"

    def __init__(self, demo: bool = True):
        """
        Initialize broker.

        Args:
            demo: If True, use demo environment. If False, use live (DANGEROUS!)
        """
        self.demo = demo
        self.nonce_counter = int(time.time() * 1000)

        # Base URL
        self.base_url = self.DEMO_BASE if demo else self.LIVE_BASE

        # API credentials (from environment)
        env_prefix = "KRAKEN_DEMO" if demo else "KRAKEN"
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise KrakenError(
                f"Missing API credentials. Set {env_prefix}_API_KEY and {env_prefix}_API_SECRET"
            )

        logger.info(
            f"KrakenFuturesBroker initialized ({'DEMO' if demo else '⚠️ LIVE'})"
        )

    def _get_nonce(self) -> str:
        """Generate unique nonce for request."""
        self.nonce_counter += 1
        return str(self.nonce_counter)

    def _sign(self, endpoint_path: str, post_data: str, nonce: str) -> str:
        """
        Generate authentication signature for Kraken Futures API.

        Kraken signature generation (as of 2024 update):
        1. Concatenate: postData + nonce + endpointPath
        2. SHA-256 hash
        3. Base64-decode API secret
        4. HMAC-SHA-512 with decoded secret
        5. Base64-encode result

        Args:
            endpoint_path: API endpoint path (e.g., "/sendorder")
            post_data: POST data as string
            nonce: Unique nonce

        Returns:
            Base64-encoded signature
        """
        # Step 1: Concatenate postData + nonce + endpointPath
        message = post_data + nonce + endpoint_path

        # Step 2: SHA-256 hash
        sha256_hash = hashlib.sha256(message.encode()).digest()

        # Step 3: Base64-decode API secret
        secret_decoded = base64.b64decode(self.api_secret)

        # Step 4: HMAC-SHA-512
        hmac_digest = hmac.new(secret_decoded, sha256_hash, hashlib.sha512).digest()

        # Step 5: Base64-encode
        signature = base64.b64encode(hmac_digest).decode()

        return signature

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> dict:
        """
        Make authenticated request to Kraken Futures API.

        Args:
            method: HTTP method (GET/POST)
            endpoint: API endpoint (e.g., "/openpositions")
            params: Request parameters
            signed: If True, add authentication headers

        Returns:
            Response JSON

        Raises:
            KrakenError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = {}
        params = params or {}

        if signed:
            # Generate nonce
            nonce = self._get_nonce()

            # Prepare POST data string
            if method == "POST":
                post_data = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            else:
                post_data = ""

            # Generate signature
            signature = self._sign(endpoint, post_data, nonce)

            # Add authentication headers
            headers["APIKey"] = self.api_key
            headers["Authent"] = signature
            headers["Nonce"] = nonce

        try:
            if method == "GET":
                r = requests.get(url, params=params, headers=headers, timeout=10)
            elif method == "POST":
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                r = requests.post(url, data=params, headers=headers, timeout=10)
            else:
                raise KrakenError(f"Unsupported HTTP method: {method}")

            r.raise_for_status()
            result = r.json()

            # Kraken Futures returns {"result": "success", ...}
            if result.get("result") != "success":
                error_msg = result.get("error", "Unknown error")
                raise KrakenError(f"Kraken API error: {error_msg}")

            return result

        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", e.response.text)
                    logger.error(f"Kraken API error: {error_msg}")
                except:
                    error_msg = e.response.text

                raise KrakenError(f"HTTP {e.response.status_code}: {error_msg}")
            else:
                raise KrakenError(f"Request failed: {e}")

    def buy(
        self,
        symbol: str,
        qty: Decimal,
        sl: Optional[Decimal] = None,
        tp: Optional[Decimal] = None
    ) -> str:
        """
        Place market BUY order (long).

        Args:
            symbol: Trading pair (e.g., "PF_XBTUSD" for BTC perpetual)
            qty: Quantity in base currency (Decimal)
            sl: Stop loss price (optional)
            tp: Take profit price (optional)

        Returns:
            Order ID

        Raises:
            KrakenError: If order fails
        """
        params = {
            "orderType": "mkt",  # Market order
            "symbol": symbol,
            "side": "buy",
            "size": str(qty)  # Convert Decimal to string
        }

        # Note: Kraken Futures handles SL/TP differently (separate orders)
        # For simplicity, we'll place main order first
        # TODO: Implement SL/TP as separate linked orders

        result = self._request("POST", "/sendorder", params=params, signed=True)

        order_id = result.get("sendStatus", {}).get("order_id")
        if not order_id:
            raise KrakenError("Order placed but no order_id returned")

        logger.info(f"BUY order placed: {symbol} | Qty: {qty} | OrderID: {order_id}")
        return order_id

    def sell(
        self,
        symbol: str,
        qty: Decimal,
        sl: Optional[Decimal] = None,
        tp: Optional[Decimal] = None
    ) -> str:
        """
        Place market SELL order (short).

        Args:
            symbol: Trading pair (e.g., "PF_XBTUSD")
            qty: Quantity in base currency (Decimal)
            sl: Stop loss price (optional)
            tp: Take profit price (optional)

        Returns:
            Order ID

        Raises:
            KrakenError: If order fails
        """
        params = {
            "orderType": "mkt",
            "symbol": symbol,
            "side": "sell",
            "size": str(qty)
        }

        result = self._request("POST", "/sendorder", params=params, signed=True)

        order_id = result.get("sendStatus", {}).get("order_id")
        if not order_id:
            raise KrakenError("Order placed but no order_id returned")

        logger.info(f"SELL order placed: {symbol} | Qty: {qty} | OrderID: {order_id}")
        return order_id

    def close_all(self, symbol: str):
        """
        Close all positions for a symbol.

        Args:
            symbol: Trading pair

        Raises:
            KrakenError: If close fails
        """
        # Get current positions
        positions = self.positions()

        if symbol not in positions:
            logger.info(f"No open position to close: {symbol}")
            return

        position = positions[symbol]

        # Close by placing opposite order
        if position.side == "long":
            self.sell(symbol=symbol, qty=position.qty)
        else:
            self.buy(symbol=symbol, qty=position.qty)

        logger.info(f"Position closed: {symbol}")

    def positions(self) -> Dict[str, Position]:
        """
        Get all open positions.

        Returns:
            Dict mapping symbol to Position

        Raises:
            KrakenError: If query fails
        """
        result = self._request("GET", "/openpositions", signed=True)

        positions_data = result.get("openPositions", [])
        positions = {}

        for pos_data in positions_data:
            symbol = pos_data.get("symbol")
            if not symbol:
                continue

            # Parse position data
            size = Decimal(str(pos_data.get("size", 0)))
            if size == 0:
                continue

            side = pos_data.get("side", "").lower()  # "long" or "short"
            entry_price = Decimal(str(pos_data.get("price", 0)))

            # Get current mark price (TODO: fetch from market data)
            # For now, use entry price as placeholder
            current_price = entry_price

            # Calculate P&L
            if side == "long":
                pnl = (current_price - entry_price) * size
                pnl_pct = ((current_price - entry_price) / entry_price) * Decimal("100")
            else:  # short
                pnl = (entry_price - current_price) * size
                pnl_pct = ((entry_price - current_price) / entry_price) * Decimal("100")

            position = Position(
                symbol=symbol,
                side=side,
                qty=size,
                entry_price=entry_price,
                current_price=current_price,
                pnl=pnl,
                pnl_pct=pnl_pct
            )

            positions[symbol] = position

        return positions

    def balance(self) -> Decimal:
        """
        Get account balance (available margin).

        Returns:
            Available balance in USD (Decimal)

        Raises:
            KrakenError: If query fails
        """
        result = self._request("GET", "/accounts", signed=True)

        accounts_data = result.get("accounts", {})

        # Kraken returns: {"flex": {"...": "...", "balance": 123.45}}
        flex_account = accounts_data.get("flex", {})
        balance_value = flex_account.get("balanceValue", 0)

        balance_decimal = Decimal(str(balance_value))

        logger.debug(f"Account balance: ${balance_decimal}")
        return balance_decimal
