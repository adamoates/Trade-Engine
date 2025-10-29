"""Base broker adapter interface.

All broker implementations should inherit from this base class to ensure
consistent interface across different exchanges.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime


class BrokerAdapter(ABC):
    """Base class for all broker adapters.

    This defines the interface that all broker implementations must follow.
    Brokers handle order execution and position management with live exchanges.
    """

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        order_type: str,  # "market", "limit", etc.
        quantity: Decimal,
        price: Optional[Decimal] = None,
        **kwargs
    ) -> Dict:
        """Place an order on the exchange.

        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            side: "buy" or "sell"
            order_type: "market", "limit", etc.
            quantity: Order size
            price: Limit price (required for limit orders)
            **kwargs: Additional exchange-specific parameters

        Returns:
            Order response with order_id, status, filled_qty, etc.
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel an existing order.

        Args:
            order_id: Exchange order ID
            symbol: Trading pair

        Returns:
            Cancellation response
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Get the status of an order.

        Args:
            order_id: Exchange order ID
            symbol: Trading pair

        Returns:
            Order status (open, filled, cancelled, etc.)
        """
        pass

    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> Dict:
        """Get account balance.

        Args:
            asset: Specific asset to query (None = all assets)

        Returns:
            Balance information
        """
        pass

    @abstractmethod
    async def get_position(self, symbol: Optional[str] = None) -> Dict:
        """Get current position(s).

        Args:
            symbol: Specific symbol to query (None = all positions)

        Returns:
            Position information
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Get current market price.

        Args:
            symbol: Trading pair

        Returns:
            Current bid, ask, last price
        """
        pass

    @abstractmethod
    def supports_shorting(self) -> bool:
        """Check if broker supports short selling.

        Returns:
            True if shorting is supported
        """
        pass

    @abstractmethod
    def get_min_order_size(self, symbol: str) -> Decimal:
        """Get minimum order size for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Minimum order size
        """
        pass

    @abstractmethod
    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate an order before submission.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            quantity: Order size
            price: Limit price

        Returns:
            (is_valid, error_message)
        """
        pass
