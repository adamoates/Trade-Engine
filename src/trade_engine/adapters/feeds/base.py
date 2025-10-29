"""Base data feed adapter interface.

All real-time feed implementations should inherit from this base class to ensure
consistent interface for streaming market data.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Dict, List, Optional
from datetime import datetime


class DataFeedAdapter(ABC):
    """Base class for all real-time data feed adapters.

    This defines the interface that all feed implementations must follow.
    Feeds provide real-time streaming data (order books, trades, tickers).
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data feed.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the data feed."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        symbol: str,
        channel: str,
        callback: Optional[Callable] = None
    ) -> None:
        """Subscribe to a data channel.

        Args:
            symbol: Trading pair
            channel: Data type ("ticker", "trades", "orderbook", etc.)
            callback: Optional callback function for each message
        """
        pass

    @abstractmethod
    async def unsubscribe(self, symbol: str, channel: str) -> None:
        """Unsubscribe from a data channel.

        Args:
            symbol: Trading pair
            channel: Data type
        """
        pass

    @abstractmethod
    async def stream(self) -> AsyncIterator[Dict]:
        """Stream incoming data messages.

        Yields:
            Normalized data messages
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if feed is currently connected.

        Returns:
            True if connected
        """
        pass

    @abstractmethod
    def get_subscriptions(self) -> List[tuple[str, str]]:
        """Get list of active subscriptions.

        Returns:
            List of (symbol, channel) tuples
        """
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Send ping to keep connection alive.

        Returns:
            True if successful
        """
        pass
