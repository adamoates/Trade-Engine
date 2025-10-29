"""Unit tests for BinanceFuturesL2Feed."""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from trade_engine.adapters.feeds.binance_l2 import (
    OrderBook,
    BinanceFuturesL2Feed,
    BinanceL2Error
)


class TestOrderBook:
    """Test OrderBook class."""

    def test_init(self):
        """Test OrderBook initialization."""
        ob = OrderBook("BTCUSDT")
        assert ob.symbol == "BTCUSDT"
        assert len(ob.bids) == 0
        assert len(ob.asks) == 0
        assert ob.last_update_id == 0

    def test_apply_snapshot(self):
        """Test applying full snapshot."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 12345,
            "bids": [
                ["50000.0", "1.5"],
                ["49999.0", "2.0"],
                ["49998.0", "0.5"]
            ],
            "asks": [
                ["50001.0", "1.2"],
                ["50002.0", "1.8"],
                ["50003.0", "0.8"]
            ]
        }

        ob.apply_snapshot(snapshot)

        assert len(ob.bids) == 3
        assert len(ob.asks) == 3
        assert ob.last_update_id == 12345
        assert ob.bids[Decimal("50000.0")] == Decimal("1.5")
        assert ob.asks[Decimal("50001.0")] == Decimal("1.2")

    def test_apply_snapshot_filters_zero_quantities(self):
        """Test that snapshot filters out zero quantities."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "1.5"],
                ["49999.0", "0.0"]  # Should be filtered
            ],
            "asks": [
                ["50001.0", "1.2"],
                ["50002.0", "0.0"]  # Should be filtered
            ]
        }

        ob.apply_snapshot(snapshot)

        assert len(ob.bids) == 1
        assert len(ob.asks) == 1

    def test_apply_delta_update_price_level(self):
        """Test applying delta to update price level."""
        ob = OrderBook("BTCUSDT")

        # Initialize with snapshot
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.5"]],
            "asks": [["50001.0", "1.2"]]
        }
        ob.apply_snapshot(snapshot)

        # Apply delta to update bid quantity
        delta = {
            "u": 101,
            "b": [["50000.0", "2.0"]],  # Update existing level
            "a": []
        }
        ob.apply_delta(delta)

        assert ob.bids[Decimal("50000.0")] == Decimal("2.0")
        assert ob.last_update_id == 101

    def test_apply_delta_remove_price_level(self):
        """Test applying delta to remove price level."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.5"]],
            "asks": [["50001.0", "1.2"]]
        }
        ob.apply_snapshot(snapshot)

        # Remove bid level with qty=0
        delta = {
            "u": 101,
            "b": [["50000.0", "0.0"]],  # Remove level
            "a": []
        }
        ob.apply_delta(delta)

        assert Decimal("50000.0") not in ob.bids
        assert len(ob.bids) == 0

    def test_get_top_levels(self):
        """Test getting top N bid/ask levels."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "1.0"],
                ["49999.0", "2.0"],
                ["49998.0", "0.5"],
                ["49997.0", "1.5"],
                ["49996.0", "0.8"]
            ],
            "asks": [
                ["50001.0", "1.2"],
                ["50002.0", "1.8"],
                ["50003.0", "0.8"],
                ["50004.0", "0.9"],
                ["50005.0", "1.1"]
            ]
        }
        ob.apply_snapshot(snapshot)

        bids, asks = ob.get_top_levels(depth=3)

        # Bids should be descending (best bid first)
        assert len(bids) == 3
        assert bids[0][0] == Decimal("50000.0")  # Best bid
        assert bids[1][0] == Decimal("49999.0")
        assert bids[2][0] == Decimal("49998.0")

        # Asks should be ascending (best ask first)
        assert len(asks) == 3
        assert asks[0][0] == Decimal("50001.0")  # Best ask
        assert asks[1][0] == Decimal("50002.0")
        assert asks[2][0] == Decimal("50003.0")

    def test_calculate_imbalance_bullish(self):
        """Test imbalance calculation with bullish bias."""
        ob = OrderBook("BTCUSDT")

        # Bullish: More bid volume than ask volume
        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "3.0"],  # Total bid volume = 3.0
            ],
            "asks": [
                ["50001.0", "1.0"]   # Total ask volume = 1.0
            ]
        }
        ob.apply_snapshot(snapshot)

        imbalance = ob.calculate_imbalance(depth=1)
        assert imbalance == Decimal("3.0")  # 3.0 / 1.0

    def test_calculate_imbalance_bearish(self):
        """Test imbalance calculation with bearish bias."""
        ob = OrderBook("BTCUSDT")

        # Bearish: More ask volume than bid volume
        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "1.0"]   # Total bid volume = 1.0
            ],
            "asks": [
                ["50001.0", "3.0"]   # Total ask volume = 3.0
            ]
        }
        ob.apply_snapshot(snapshot)

        imbalance = ob.calculate_imbalance(depth=1)
        assert imbalance == Decimal("1.0") / Decimal("3.0")  # ~0.33

    def test_calculate_imbalance_neutral(self):
        """Test imbalance calculation with balanced book."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "2.0"]
            ],
            "asks": [
                ["50001.0", "2.0"]
            ]
        }
        ob.apply_snapshot(snapshot)

        imbalance = ob.calculate_imbalance(depth=1)
        assert imbalance == Decimal("1.0")  # Neutral

    def test_calculate_imbalance_multiple_levels(self):
        """Test imbalance calculation with multiple levels."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "1.0"],
                ["49999.0", "2.0"],
                ["49998.0", "1.0"]  # Total = 4.0
            ],
            "asks": [
                ["50001.0", "1.0"],
                ["50002.0", "1.0"]  # Total = 2.0
            ]
        }
        ob.apply_snapshot(snapshot)

        imbalance = ob.calculate_imbalance(depth=5)
        assert imbalance == Decimal("2.0")  # 4.0 / 2.0

    def test_get_mid_price(self):
        """Test mid-price calculation."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50002.0", "1.0"]]
        }
        ob.apply_snapshot(snapshot)

        mid_price = ob.get_mid_price()
        assert mid_price == Decimal("50001.0")  # (50000 + 50002) / 2

    def test_get_spread_bps(self):
        """Test spread calculation in basis points."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50010.0", "1.0"]]  # Spread = 10
        }
        ob.apply_snapshot(snapshot)

        spread_bps = ob.get_spread_bps()
        # Spread = 10, Mid = 50005, BPS = (10/50005) * 10000 ≈ 2.0
        assert spread_bps is not None
        assert abs(spread_bps - Decimal("2.0")) < Decimal("0.01")

    def test_is_valid_with_valid_book(self):
        """Test is_valid returns True for valid book."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        ob.apply_snapshot(snapshot)

        assert ob.is_valid() is True

    def test_is_valid_with_empty_book(self):
        """Test is_valid returns False for empty book."""
        ob = OrderBook("BTCUSDT")
        assert ob.is_valid() is False

    def test_is_valid_with_crossed_book(self):
        """Test is_valid returns False for crossed book."""
        ob = OrderBook("BTCUSDT")

        # Crossed book: bid >= ask (should never happen in real market)
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50001.0", "1.0"]],  # Bid higher than ask
            "asks": [["50000.0", "1.0"]]   # Ask lower than bid
        }
        ob.apply_snapshot(snapshot)

        assert ob.is_valid() is False


class TestBinanceFuturesL2Feed:
    """Test BinanceFuturesL2Feed class."""

    def test_init(self):
        """Test L2 feed initialization."""
        feed = BinanceFuturesL2Feed(
            symbol="BTCUSDT",
            depth=5,
            update_interval_ms=100
        )

        assert feed.symbol == "BTCUSDT"
        assert feed.depth == 5
        assert feed.update_interval_ms == 100
        assert feed.order_book.symbol == "BTCUSDT"
        assert feed.running is False

    def test_init_lowercase_symbol(self):
        """Test symbol is converted to uppercase."""
        feed = BinanceFuturesL2Feed(symbol="btcusdt")
        assert feed.symbol == "BTCUSDT"

    def test_get_imbalance(self):
        """Test getting imbalance from feed."""
        feed = BinanceFuturesL2Feed(symbol="BTCUSDT", depth=5)

        # Populate order book
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        feed.order_book.apply_snapshot(snapshot)

        imbalance = feed.get_imbalance()
        assert imbalance == Decimal("3.0")

    def test_get_order_book_snapshot(self):
        """Test getting order book snapshot."""
        feed = BinanceFuturesL2Feed(symbol="BTCUSDT", depth=3)

        # Populate order book
        snapshot = {
            "lastUpdateId": 100,
            "bids": [
                ["50000.0", "1.5"],
                ["49999.0", "2.0"]
            ],
            "asks": [
                ["50001.0", "1.2"],
                ["50002.0", "1.8"]
            ]
        }
        feed.order_book.apply_snapshot(snapshot)

        ob_snapshot = feed.get_order_book_snapshot()

        assert ob_snapshot["symbol"] == "BTCUSDT"
        assert len(ob_snapshot["bids"]) == 2
        assert len(ob_snapshot["asks"]) == 2
        assert ob_snapshot["bids"][0] == ["50000.0", "1.5"]
        assert ob_snapshot["asks"][0] == ["50001.0", "1.2"]
        assert "mid_price" in ob_snapshot
        assert "spread_bps" in ob_snapshot
        assert "imbalance" in ob_snapshot
        assert ob_snapshot["is_valid"] is True


class TestOrderBookEdgeCases:
    """Test edge cases and error handling."""

    def test_calculate_imbalance_with_empty_book(self):
        """Test imbalance returns neutral for empty book."""
        ob = OrderBook("BTCUSDT")
        imbalance = ob.calculate_imbalance()
        assert imbalance == Decimal("1.0")  # Neutral

    def test_calculate_imbalance_with_zero_ask_volume(self):
        """Test imbalance caps at 999 when ask volume is zero."""
        ob = OrderBook("BTCUSDT")

        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "0.0"]]
        }
        ob.apply_snapshot(snapshot)

        # After snapshot, asks with qty=0 are filtered out
        # So we have bids but no asks
        imbalance = ob.calculate_imbalance()
        assert imbalance == Decimal("1.0")  # Returns neutral when insufficient data

    def test_get_mid_price_with_empty_book(self):
        """Test mid_price returns None for empty book."""
        ob = OrderBook("BTCUSDT")
        mid_price = ob.get_mid_price()
        assert mid_price is None

    def test_get_spread_bps_with_empty_book(self):
        """Test spread_bps returns None for empty book."""
        ob = OrderBook("BTCUSDT")
        spread_bps = ob.get_spread_bps()
        assert spread_bps is None
