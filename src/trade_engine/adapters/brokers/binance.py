"""
Binance Futures broker adapter (paper & live).

Implements Broker interface for Binance Futures (USDⓈ-M perpetual contracts).
Supports both testnet (paper trading) and production.
"""

import os
import time
import hmac
import hashlib
from decimal import Decimal
from typing import Dict
import requests
from loguru import logger

from trade_engine.core.constants import (
    BINANCE_API_KEY_LENGTH,
    BINANCE_API_SECRET_LENGTH,
    BINANCE_DEFAULT_RECV_WINDOW_MS,
    BINANCE_REQUEST_TIMEOUT_SECONDS
)
from trade_engine.core.types import Broker, Position


class BinanceError(Exception):
    """Binance API errors."""
    pass


class BinanceFuturesBroker(Broker):
    """
    Binance Futures broker (testnet or live).

    Usage:
        # Testnet (paper trading)
        broker = BinanceFuturesBroker(testnet=True)

        # Live (real money)
        broker = BinanceFuturesBroker(testnet=False)

    Environment variables required:
        BINANCE_API_KEY       (or BINANCE_TESTNET_API_KEY for testnet)
        BINANCE_API_SECRET    (or BINANCE_TESTNET_API_SECRET for testnet)
    """

    TESTNET_BASE = "https://testnet.binancefuture.com"
    LIVE_BASE = "https://fapi.binance.com"

    def __init__(self, testnet: bool = True, recv_window: int = BINANCE_DEFAULT_RECV_WINDOW_MS):
        """
        Initialize broker.

        Args:
            testnet: If True, use testnet. If False, use live (DANGEROUS!)
            recv_window: API request valid window (ms), default 5000ms
        """
        self.testnet = testnet
        self.recv_window = recv_window

        # Base URL
        self.base_url = self.TESTNET_BASE if testnet else self.LIVE_BASE

        # API credentials (from environment)
        env_prefix = "BINANCE_TESTNET" if testnet else "BINANCE"
        self.api_key = os.getenv(f"{env_prefix}_API_KEY")
        self.api_secret = os.getenv(f"{env_prefix}_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise BinanceError(
                f"Missing API credentials. Set {env_prefix}_API_KEY and {env_prefix}_API_SECRET"
            )

        # Validate API key format
        if len(self.api_key) != BINANCE_API_KEY_LENGTH:
            testnet_url = "https://testnet.binancefuture.com/en/futures/BTCUSDT"
            live_url = "https://www.binance.com/en/my/settings/api-management"
            help_url = testnet_url if testnet else live_url

            raise BinanceError(
                f"Invalid API key format. Binance API keys should be {BINANCE_API_KEY_LENGTH} characters.\n"
                f"Your key is {len(self.api_key)} characters.\n"
                f"Get your API key from: {help_url}"
            )

        if len(self.api_secret) != BINANCE_API_SECRET_LENGTH:
            raise BinanceError(
                f"Invalid API secret format. Binance API secrets should be {BINANCE_API_SECRET_LENGTH} characters.\n"
                f"Your secret is {len(self.api_secret)} characters."
            )

        logger.info(
            f"BinanceFuturesBroker initialized ({'TESTNET' if testnet else '⚠️ LIVE'})"
        )

    def _sign(self, params: dict) -> str:
        """Generate HMAC SHA256 signature."""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, signed: bool = False, **params):
        """
        Make API request.

        Args:
            method: "GET" | "POST" | "DELETE"
            endpoint: API endpoint (e.g., "/fapi/v1/order")
            signed: If True, add signature
            **params: Query/body parameters
        """
        url = self.base_url + endpoint
        headers = {"X-MBX-APIKEY": self.api_key}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = self.recv_window
            params["signature"] = self._sign(params)

        try:
            timeout = BINANCE_REQUEST_TIMEOUT_SECONDS
            if method == "GET":
                r = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method == "POST":
                r = requests.post(url, headers=headers, params=params, timeout=timeout)
            elif method == "DELETE":
                r = requests.delete(url, headers=headers, params=params, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            r.raise_for_status()
            return r.json()

        except requests.HTTPError as e:
            logger.error(f"Binance API error: {e.response.text}")
            raise BinanceError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise BinanceError(f"Request failed: {e}")

    # ========== Broker Interface Implementation ==========

    def buy(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """
        Place buy order (long entry or short close).

        Uses MARKET order for immediate execution.
        If SL/TP provided, places them as separate stop orders.

        Args:
            qty: Quantity (Decimal for precision)
            sl: Stop loss price (Decimal)
            tp: Take profit price (Decimal)

        Returns:
            order_id: Binance order ID (as string)
        """
        # Place market buy
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": str(qty)  # Convert Decimal to string for API
        }

        result = self._request("POST", "/fapi/v1/order", signed=True, **params)
        order_id = str(result["orderId"])

        logger.info(f"BUY {qty} {symbol} | Order ID: {order_id}")

        # TODO: Add SL/TP as STOP_MARKET orders if provided
        # (Requires position tracking to set correct side)

        return order_id

    def sell(self, symbol: str, qty: Decimal, sl: Decimal | None = None, tp: Decimal | None = None) -> str:
        """
        Place sell order (short entry or long close).

        Uses MARKET order for immediate execution.

        Args:
            qty: Quantity (Decimal for precision)
            sl: Stop loss price (Decimal)
            tp: Take profit price (Decimal)

        Returns:
            order_id: Binance order ID (as string)
        """
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(qty)  # Convert Decimal to string for API
        }

        result = self._request("POST", "/fapi/v1/order", signed=True, **params)
        order_id = str(result["orderId"])

        logger.info(f"SELL {qty} {symbol} | Order ID: {order_id}")

        return order_id

    def close_all(self, symbol: str):
        """
        Flatten position (close all open positions for symbol).

        Fetches current position, places opposite market order.
        """
        positions = self.positions()

        if symbol not in positions:
            logger.warning(f"No position to close for {symbol}")
            return

        pos = positions[symbol]

        # Close with opposite side
        if pos.side == "long":
            logger.info(f"Closing LONG position: {pos}")
            self.sell(symbol, pos.qty)
        else:
            logger.info(f"Closing SHORT position: {pos}")
            self.buy(symbol, pos.qty)

    def positions(self) -> Dict[str, Position]:
        """
        Get current positions.

        Returns:
            Dict[symbol → Position]
            Empty dict if no positions
        """
        result = self._request("GET", "/fapi/v2/positionRisk", signed=True)

        positions = {}
        for pos_data in result:
            symbol = pos_data["symbol"]
            qty = abs(Decimal(pos_data["positionAmt"]))

            # Skip if no position
            if qty == 0:
                continue

            entry_price = Decimal(pos_data["entryPrice"])
            mark_price = Decimal(pos_data["markPrice"])
            unrealized_pnl = Decimal(pos_data["unRealizedProfit"])

            # Determine side
            side = "long" if Decimal(pos_data["positionAmt"]) > 0 else "short"

            # Calculate PnL %
            if entry_price > 0:
                if side == "long":
                    pnl_pct = ((mark_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - mark_price) / entry_price) * 100
            else:
                pnl_pct = Decimal("0.0")

            # Position now uses Decimal (updated core types)
            positions[symbol] = Position(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry_price,
                current_price=mark_price,
                pnl=unrealized_pnl,
                pnl_pct=pnl_pct
            )

        return positions

    def balance(self) -> Decimal:
        """
        Get available USDT balance.

        Returns:
            Available balance (USDT) as Decimal for precision
        """
        result = self._request("GET", "/fapi/v2/balance", signed=True)

        for asset in result:
            if asset["asset"] == "USDT":
                return Decimal(str(asset["availableBalance"]))

        return Decimal("0.0")

    # ========== Helper Methods ==========

    def get_ticker_price(self, symbol: str) -> Decimal:
        """
        Get current mark price.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current mark price as Decimal for precision
        """
        result = self._request("GET", "/fapi/v1/premiumIndex", symbol=symbol)
        return Decimal(str(result["markPrice"]))

    def cancel_all_orders(self, symbol: str):
        """
        Cancel all open orders for symbol.

        Useful for cleanup/emergency situations.
        """
        params = {"symbol": symbol}
        result = self._request("DELETE", "/fapi/v1/allOpenOrders", signed=True, **params)
        logger.info(f"Cancelled all orders for {symbol}: {result}")
        return result

    def set_leverage(self, symbol: str, leverage: int):
        """
        Set leverage for symbol.

        Args:
            symbol: Trading pair
            leverage: Leverage (1-125 depending on symbol)
        """
        params = {"symbol": symbol, "leverage": leverage}
        result = self._request("POST", "/fapi/v1/leverage", signed=True, **params)
        logger.info(f"Set leverage {leverage}x for {symbol}")
        return result

    def set_margin_type(self, symbol: str, margin_type: str):
        """
        Set margin type (ISOLATED or CROSSED).

        Args:
            symbol: Trading pair
            margin_type: "ISOLATED" | "CROSSED"
        """
        params = {"symbol": symbol, "marginType": margin_type}
        result = self._request("POST", "/fapi/v1/marginType", signed=True, **params)
        logger.info(f"Set margin type {margin_type} for {symbol}")
        return result
