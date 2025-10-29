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

from trade_engine.core.constants import BINANCE_REQUEST_TIMEOUT_SECONDS
from trade_engine.core.types import Broker, Position
from trade_engine.core.position_database import PositionDatabase, PositionDatabaseError


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

        # Validate credentials
        self._validate_credentials()

        # Position database for entry price tracking
        self.position_db = PositionDatabase(db_path=db_path)

        logger.info(
            "BinanceUSSpotBroker initialized (SPOT ONLY - LONG ONLY) | "
            f"Entry price tracking: {db_path}"
        )

    def _validate_credentials(self) -> None:
        """
        Validate API credentials format and presence.

        Raises:
            BinanceUSError: If credentials are missing or invalid

        Security notes:
            - Never logs actual credential values
            - Only validates format, not authenticity (API will reject invalid creds)
        """
        # Check for missing credentials
        if not self.api_key:
            raise BinanceUSError(
                "Missing BINANCE_US_API_KEY environment variable. "
                "Set it before initializing the broker."
            )

        if not self.api_secret:
            raise BinanceUSError(
                "Missing BINANCE_US_API_SECRET environment variable. "
                "Set it before initializing the broker."
            )

        # Validate API key format (Binance keys are 64-character hex strings)
        if len(self.api_key) < 32:
            raise BinanceUSError(
                f"Invalid API key format: too short ({len(self.api_key)} chars, expected 64+). "
                f"Key prefix: {self.api_key[:8]}..."
            )

        if not all(c in "0123456789ABCDEFabcdef" for c in self.api_key):
            raise BinanceUSError(
                "Invalid API key format: must be hexadecimal. "
                f"Key prefix: {self.api_key[:8]}..."
            )

        # Validate API secret format
        if len(self.api_secret) < 32:
            raise BinanceUSError(
                f"Invalid API secret format: too short ({len(self.api_secret)} chars, expected 64+)"
            )

        if not all(c in "0123456789ABCDEFabcdef" for c in self.api_secret):
            raise BinanceUSError(
                "Invalid API secret format: must be hexadecimal"
            )

        logger.info(
            f"API credentials validated | Key: {self.api_key[:8]}...{self.api_key[-4:]} "
            f"(length: {len(self.api_key)})"
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

    def _wait_for_fill(
        self,
        symbol: str,
        order_id: str,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5
    ) -> dict:
        """
        Wait for order to fill with configurable timeout.

        Polls order status until FILLED or PARTIALLY_FILLED, or timeout is reached.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            order_id: Order ID to check
            timeout_seconds: Max time to wait for fill (default 10s)
            poll_interval: Time between status checks (default 0.5s)

        Returns:
            Order details dict from API

        Raises:
            BinanceUSError: If timeout reached or order rejected

        Notes:
            - Accepts FILLED and PARTIALLY_FILLED status
            - Market orders typically fill within 100-500ms
            - 10s timeout allows for volatile market conditions
        """
        import time
        start_time = time.time()
        attempts = 0

        while time.time() - start_time < timeout_seconds:
            attempts += 1

            # Query order status
            order_details = self._request(
                "GET",
                "/api/v3/order",
                params={"symbol": symbol, "orderId": order_id},
                signed=True
            )

            status = order_details.get("status")
            executed_qty = Decimal(str(order_details.get("executedQty", 0)))

            # Accept FILLED or PARTIALLY_FILLED
            if status in ["FILLED", "PARTIALLY_FILLED"]:
                elapsed = (time.time() - start_time) * 1000  # ms
                logger.debug(
                    f"Order filled: {symbol} | "
                    f"Status: {status} | "
                    f"Qty: {executed_qty} | "
                    f"Latency: {elapsed:.1f}ms | "
                    f"Attempts: {attempts}"
                )
                return order_details

            # Reject orders that failed
            if status in ["CANCELED", "REJECTED", "EXPIRED"]:
                raise BinanceUSError(
                    f"Order {order_id} failed with status: {status}"
                )

            # Wait before next poll
            time.sleep(poll_interval)

        # Timeout reached
        raise BinanceUSError(
            f"Order {order_id} did not fill within {timeout_seconds}s. "
            f"Final status: {order_details.get('status')}, "
            f"Executed qty: {executed_qty}"
        )

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
            # Wait for order to fill (with timeout)
            order_details = self._wait_for_fill(symbol, order_id, timeout_seconds=10.0)

            # Get executed quantity and status
            order_status = order_details.get("status")
            executed_qty = Decimal(str(order_details.get("executedQty", 0)))

            # Handle partial fills
            if executed_qty != qty:
                logger.warning(
                    f"Partial fill: {symbol} | "
                    f"Requested: {qty} | Executed: {executed_qty} | "
                    f"Status: {order_status}"
                )
                # Accept partial fill and update qty to actual executed amount
                qty = executed_qty

            # Reject orders with zero execution
            if executed_qty == 0:
                raise BinanceUSError(
                    f"Order {order_id} executed with zero quantity. Status: {order_status}"
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
            # 🔑 FIX Issue #2: Position already exists - use weighted average entry price
            logger.info(f"Adding to existing position: {symbol}")
            try:
                updated_position = self.position_db.add_to_position(
                    symbol=symbol,
                    additional_qty=qty,
                    additional_price=avg_fill_price,
                    broker="binance_us"
                )
                logger.info(
                    f"Position averaged: {symbol} | "
                    f"New entry: {updated_position['entry_price']} | "
                    f"New qty: {updated_position['qty']}"
                )
            except Exception as add_error:
                logger.error(f"Failed to average position {symbol}: {add_error}")
                raise BinanceUSError(
                    f"Position tracking failed for {symbol}: {add_error}"
                ) from add_error
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
            # Wait for order to fill (with timeout)
            order_details = self._wait_for_fill(symbol, order_id, timeout_seconds=10.0)

            # Get executed quantity and status
            order_status = order_details.get("status")
            executed_qty = Decimal(str(order_details.get("executedQty", 0)))

            # Handle partial fills
            if executed_qty != qty:
                logger.warning(
                    f"Partial fill: {symbol} | "
                    f"Requested: {qty} | Executed: {executed_qty} | "
                    f"Status: {order_status}"
                )
                # Accept partial fill and update qty for P&L calculation
                qty = executed_qty

            # Reject orders with zero execution
            if executed_qty == 0:
                raise BinanceUSError(
                    f"Order {order_id} executed with zero quantity. Status: {order_status}"
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
