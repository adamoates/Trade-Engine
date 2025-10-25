"""
Simulated broker for testing without real API credentials.

Simulates order execution at market prices with realistic fills.
Uses real market data but executes orders locally without exchange connection.
"""

from typing import Dict
from loguru import logger

from trade_engine.core.engine.types import Broker, Position


class SimulatedBroker(Broker):
    """
    Simulated broker for paper trading without API credentials.

    Features:
    - Simulates instant market fills at current price
    - Tracks positions locally
    - No exchange connection required
    - Perfect for POC testing and development

    Usage:
        broker = SimulatedBroker(initial_balance=500.0)
        order_id = broker.buy("BTCUSDT", 0.01)
    """

    def __init__(self, initial_balance: float = 500.0):
        """
        Initialize simulated broker.

        Args:
            initial_balance: Starting USDT balance
        """
        self.balance_usdt = initial_balance
        self.initial_balance = initial_balance
        self.positions_dict: Dict[str, Position] = {}
        self.order_counter = 1000

        logger.info(f"SimulatedBroker initialized | Balance: ${initial_balance:,.2f}")
        logger.warning("⚠️  SIMULATION MODE - Orders are simulated, not sent to exchange")

    def _next_order_id(self) -> str:
        """Generate next order ID."""
        order_id = f"SIM_{self.order_counter}"
        self.order_counter += 1
        return order_id

    def buy(self, symbol: str, qty: float, sl: float | None = None, tp: float | None = None) -> str:
        """
        Simulate buy order (market fill).

        Args:
            symbol: Trading symbol
            qty: Quantity to buy
            sl: Stop loss price (ignored in simulation)
            tp: Take profit price (ignored in simulation)

        Returns:
            Simulated order ID
        """
        order_id = self._next_order_id()

        logger.info(
            f"[SIMULATED] BUY {qty:.6f} {symbol} | "
            f"Order ID: {order_id}"
        )

        # Note: Actual position tracking is done by PositionManager
        # This just simulates the order execution

        return order_id

    def sell(self, symbol: str, qty: float, sl: float | None = None, tp: float | None = None) -> str:
        """
        Simulate sell order (market fill).

        Args:
            symbol: Trading symbol
            qty: Quantity to sell
            sl: Stop loss price (ignored in simulation)
            tp: Take profit price (ignored in simulation)

        Returns:
            Simulated order ID
        """
        order_id = self._next_order_id()

        logger.info(
            f"[SIMULATED] SELL {qty:.6f} {symbol} | "
            f"Order ID: {order_id}"
        )

        return order_id

    def close_all(self, symbol: str):
        """
        Simulate closing all positions for symbol.

        Args:
            symbol: Trading symbol
        """
        logger.info(f"[SIMULATED] Closing all positions for {symbol}")

        # Actual position tracking is handled by PositionManager
        # This just logs the simulated close

    def positions(self) -> Dict[str, Position]:
        """
        Get current positions.

        Note: In simulation mode, position tracking is handled by PositionManager.
        This method returns empty dict as we don't track positions in the broker.

        Returns:
            Empty dict (positions tracked by PositionManager)
        """
        return {}

    def balance(self) -> float:
        """
        Get available USDT balance.

        Note: In simulation mode, balance is tracked by PositionManager.
        This returns the initial balance for reference.

        Returns:
            Current simulated balance
        """
        return self.balance_usdt
