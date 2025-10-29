"""
Binance.us Spot broker adapter (US-only, spot trading).

Implements Broker interface for Binance.us spot market.
**NOTE**: Spot trading = LONG ONLY (no shorting, no leverage).

CRITICAL: All price/quantity conversions use Decimal (NON-NEGOTIABLE per CLAUDE.md).

**Entry Price Tracking**: Uses PositionDatabase for persistent entry price storage,
enabling accurate P&L calculations for spot holdings (which exchanges don't track natively).
"""

import os
import time
import hmac
import hashlib
from decimal import Decimal
from typing import Dict, Optional
import requests
from loguru import logger

from app.constants import BINANCE_REQUEST_TIMEOUT_SECONDS
from app.engine.types import Broker, Position
from app.engine.position_database import PositionDatabase, PositionDatabaseError


class BinanceUSError(Exception):
    """Binance.us API errors."""
    pass


class BinanceUSSpotBroker(Broker):
    """
    Binance.us Spot broker (long-only trading).

    **IMPORTANT**: This is spot trading only - NO SHORTING.
    - buy() = Opens long position
    - sell() = Closes long position (sells holdings)
    - Short signals are ignored/rejected

    Usage:
        broker = BinanceUSSpotBroker()

    Environment variables required:
        BINANCE_US_API_KEY
        BINANCE_US_API_SECRET
    """

    BASE_URL = "https://api.binance.us"

    def __init__(
        self,
        recv_window: int = 5000,
        db_path: str = "data/positions_binance_us.db"
    ):
        """
        Initialize broker.

        Args:
            recv_window: API request valid window (ms), default 5000ms
            db_path: Path to position database for entry price tracking
        """
        self.recv_window = recv_window

        # API credentials
        self.api_key = os.getenv("BINANCE_US_API_KEY")
        self.api_secret = os.getenv("BINANCE_US_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise BinanceUSError(
                "Missing API credentials. Set BINANCE_US_API_KEY and BINANCE_US_API_SECRET"
            )

        # Position database for entry price tracking
        self.position_db = PositionDatabase(db_path=db_path)

        logger.info(
            "BinanceUSSpotBroker initialized (SPOT ONLY - LONG ONLY) | "
            f"Entry price tracking: {db_path}"
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

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> dict:
        """
        Make authenticated request to Binance.us API.

        Args:
            method: HTTP method (GET/POST/DELETE)
            endpoint: API endpoint (e.g., "/api/v3/order")
            params: Request parameters
            signed: If True, add timestamp and signature

        Returns:
            Response JSON

        Raises:
            BinanceUSError: If request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key}
        params = params or {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = self.recv_window
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                r = requests.get(url, params=params, headers=headers,
                               timeout=BINANCE_REQUEST_TIMEOUT_SECONDS)
            elif method == "POST":
                r = requests.post(url, params=params, headers=headers,
                                timeout=BINANCE_REQUEST_TIMEOUT_SECONDS)
            elif method == "DELETE":
                r = requests.delete(url, params=params, headers=headers,
                                  timeout=BINANCE_REQUEST_TIMEOUT_SECONDS)
            else:
                raise BinanceUSError(f"Unsupported HTTP method: {method}")

            r.raise_for_status()
            return r.json()

        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                error_msg = e.response.text
                logger.error(f"Binance.us API error: {error_msg}")
                raise BinanceUSError(f"HTTP {e.response.status_code}: {error_msg}")
            else:
                raise BinanceUSError(f"Request failed: {e}")

    def buy(
        self,
        symbol: str,
        qty: Decimal,
        sl: Optional[Decimal] = None,
        tp: Optional[Decimal] = None
    ) -> str:
        """
        Place market BUY order (long position, spot trading).

        **Entry Price Tracking**: Queries fill price after execution and stores
        in database for accurate P&L calculation.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            qty: Quantity in base currency (Decimal)
            sl: Stop loss price (optional, not implemented for spot)
            tp: Take profit price (optional, not implemented for spot)

        Returns:
            Order ID

        Raises:
            BinanceUSError: If order fails
        """
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": str(qty)  # Convert Decimal to string
        }

        # Note: SL/TP in spot requires OCO orders (not implemented yet)
        # TODO: Implement OCO orders for SL/TP

        result = self._request("POST", "/api/v3/order", params=params, signed=True)

        order_id = result.get("orderId")
        if not order_id:
            raise BinanceUSError("Order placed but no orderId returned")

        order_id = str(order_id)

        # Get actual fill price for entry price tracking
        try:
            # Query order details to get fill price
            order_details = self._request(
                "GET",
                "/api/v3/order",
                params={"symbol": symbol, "orderId": order_id},
                signed=True
            )

            # Calculate average fill price from fills
            fills = order_details.get("fills", [])
            if fills:
                total_qty = Decimal("0")
                total_cost = Decimal("0")

                for fill in fills:
                    fill_price = Decimal(str(fill["price"]))
                    fill_qty = Decimal(str(fill["qty"]))
                    total_qty += fill_qty
                    total_cost += fill_price * fill_qty

                avg_fill_price = total_cost / total_qty if total_qty > 0 else Decimal("0")
            else:
                # Fallback: use current market price
                ticker_result = self._request(
                    "GET",
                    "/api/v3/ticker/price",
                    params={"symbol": symbol}
                )
                avg_fill_price = Decimal(str(ticker_result.get("price", 0)))

            # Store position in database
            self.position_db.open_position(
                symbol=symbol,
                side="long",
                entry_price=avg_fill_price,
                qty=qty,
                broker="binance_us"
            )

            logger.info(
                f"BUY order placed: {symbol} | Qty: {qty} | "
                f"Entry price: {avg_fill_price} | OrderID: {order_id}"
            )

        except PositionDatabaseError as e:
            logger.warning(
                f"Position already tracked for {symbol}: {e} | "
                "P&L may be inaccurate if adding to position"
            )
        except Exception as e:
            logger.error(f"Failed to track entry price for {symbol}: {e}")

        return order_id

    def sell(
        self,
        symbol: str,
        qty: Decimal,
        sl: Optional[Decimal] = None,
        tp: Optional[Decimal] = None
    ) -> str:
        """
        Place market SELL order (close long position, spot trading).

        **NOTE**: This SELLS your holdings, NOT opening a short position.
        Binance.us spot does not support shorting.

        **P&L Tracking**: Calculates realized P&L using stored entry price
        and closes position in database.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            qty: Quantity in base currency (Decimal)
            sl: Stop loss price (ignored for spot)
            tp: Take profit price (ignored for spot)

        Returns:
            Order ID

        Raises:
            BinanceUSError: If order fails
        """
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(qty)
        }

        result = self._request("POST", "/api/v3/order", params=params, signed=True)

        order_id = result.get("orderId")
        if not order_id:
            raise BinanceUSError("Order placed but no orderId returned")

        order_id = str(order_id)

        # Get actual fill price for P&L calculation
        try:
            # Query order details to get fill price
            order_details = self._request(
                "GET",
                "/api/v3/order",
                params={"symbol": symbol, "orderId": order_id},
                signed=True
            )

            # Calculate average fill price from fills
            fills = order_details.get("fills", [])
            if fills:
                total_qty = Decimal("0")
                total_cost = Decimal("0")

                for fill in fills:
                    fill_price = Decimal(str(fill["price"]))
                    fill_qty = Decimal(str(fill["qty"]))
                    total_qty += fill_qty
                    total_cost += fill_price * fill_qty

                avg_fill_price = total_cost / total_qty if total_qty > 0 else Decimal("0")
            else:
                # Fallback: use current market price
                ticker_result = self._request(
                    "GET",
                    "/api/v3/ticker/price",
                    params={"symbol": symbol}
                )
                avg_fill_price = Decimal(str(ticker_result.get("price", 0)))

            # Close position in database and calculate P&L
            trade = self.position_db.close_position(
                symbol=symbol,
                exit_price=avg_fill_price,
                exit_reason="manual_close",
                broker="binance_us"
            )

            logger.info(
                f"SELL order placed: {symbol} | Qty: {qty} | "
                f"Exit price: {avg_fill_price} | OrderID: {order_id} | "
                f"P&L: {trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)"
            )

        except PositionDatabaseError as e:
            logger.warning(
                f"No position tracked for {symbol}: {e} | "
                "P&L not calculated"
            )
        except Exception as e:
            logger.error(f"Failed to calculate P&L for {symbol}: {e}")

        return order_id

    def close_all(self, symbol: str):
        """
        Close all positions for a symbol (sell all holdings).

        Args:
            symbol: Trading pair

        Raises:
            BinanceUSError: If close fails
        """
        # Get current balance for this symbol
        positions = self.positions()

        if symbol not in positions:
            logger.info(f"No holdings to sell: {symbol}")
            return

        position = positions[symbol]

        # Sell all holdings
        self.sell(symbol=symbol, qty=position.qty)
        logger.info(f"Holdings sold: {symbol}")

    def positions(self) -> Dict[str, Position]:
        """
        Get all open positions (holdings in spot trading).

        **Entry Price Tracking**: Uses PositionDatabase to retrieve stored entry
        prices and calculate accurate P&L for spot holdings.

        Returns:
            Dict mapping symbol to Position (only long positions)

        Raises:
            BinanceUSError: If query fails
        """
        result = self._request("GET", "/api/v3/account", signed=True)

        balances = result.get("balances", [])
        positions = {}

        # Iterate through all balances and find non-zero holdings
        for balance in balances:
            asset = balance.get("asset")
            free = Decimal(str(balance.get("free", 0)))
            locked = Decimal(str(balance.get("locked", 0)))

            total = free + locked
            if total == 0:
                continue

            # For simplicity, we'll report positions as "ASSETUSDT" symbols
            # (e.g., "BTCUSDT" if holding BTC)
            if asset == "USDT" or asset == "USD":
                continue  # Skip quote currency

            symbol = f"{asset}USDT"

            # Get current price (simplified - using ticker)
            try:
                ticker_result = self._request("GET", "/api/v3/ticker/price",
                                             params={"symbol": symbol})
                current_price = Decimal(str(ticker_result.get("price", 0)))
            except:
                logger.warning(f"Could not fetch price for {symbol}")
                current_price = Decimal("0")

            # Try to get entry price from database
            try:
                db_position = self.position_db.get_position(symbol, broker="binance_us")

                if db_position:
                    # Calculate real P&L using stored entry price
                    entry_price = db_position["entry_price"]
                    pnl = (current_price - entry_price) * total
                    pnl_pct = ((current_price - entry_price) / entry_price) * Decimal("100")

                    logger.debug(
                        f"Position P&L: {symbol} | "
                        f"Entry: {entry_price} → Current: {current_price} | "
                        f"P&L: {pnl:.2f} ({pnl_pct:.2f}%)"
                    )
                else:
                    # No entry price tracked - use current price as entry (no P&L)
                    entry_price = current_price
                    pnl = Decimal("0")
                    pnl_pct = Decimal("0")

                    logger.warning(
                        f"No entry price tracked for {symbol} | "
                        "P&L calculation not available"
                    )

            except Exception as e:
                logger.error(f"Failed to retrieve entry price for {symbol}: {e}")
                # Fallback to no P&L calculation
                entry_price = current_price
                pnl = Decimal("0")
                pnl_pct = Decimal("0")

            # Create position object with accurate P&L
            position = Position(
                symbol=symbol,
                side="long",  # Spot is always long
                qty=total,
                entry_price=entry_price,
                current_price=current_price,
                pnl=pnl,
                pnl_pct=pnl_pct
            )

            positions[symbol] = position

        return positions

    def balance(self) -> Decimal:
        """
        Get account balance (USDT/USD balance).

        Returns:
            Available balance in USDT (Decimal)

        Raises:
            BinanceUSError: If query fails
        """
        result = self._request("GET", "/api/v3/account", signed=True)

        balances = result.get("balances", [])

        # Find USDT balance
        for balance in balances:
            if balance.get("asset") in ["USDT", "USD"]:
                free = Decimal(str(balance.get("free", 0)))
                logger.debug(f"Account balance: ${free}")
                return free

        return Decimal("0")
