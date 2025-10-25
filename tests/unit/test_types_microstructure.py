"""Unit tests for market microstructure data types."""
import pytest
from datetime import datetime, timezone

from mft.services.data.types_microstructure import (
    OptionsSnapshot,
    OrderBookLevel,
    Level2Snapshot,
    MarketMicrostructure
)


class TestOptionsSnapshot:
    """Test Options market data snapshot."""

    def test_get_sentiment_signal_bullish(self):
        """Test bullish sentiment detection (PCR < 0.7)."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=100,
            call_volume=200,
            put_call_ratio=0.5,  # Bullish
            put_open_interest=1000,
            call_open_interest=2000,
            total_open_interest=3000
        )

        # ACT
        sentiment = snapshot.get_sentiment_signal()

        # ASSERT
        assert sentiment == "BULLISH"

    def test_get_sentiment_signal_bearish(self):
        """Test bearish sentiment detection (PCR > 1.2)."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=200,
            call_volume=100,
            put_call_ratio=2.0,  # Bearish
            put_open_interest=2000,
            call_open_interest=1000,
            total_open_interest=3000
        )

        # ACT
        sentiment = snapshot.get_sentiment_signal()

        # ASSERT
        assert sentiment == "BEARISH"

    def test_get_sentiment_signal_neutral(self):
        """Test neutral sentiment detection (0.7 < PCR < 1.2)."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=100,
            call_volume=100,
            put_call_ratio=1.0,  # Neutral
            put_open_interest=1000,
            call_open_interest=1000,
            total_open_interest=2000
        )

        # ACT
        sentiment = snapshot.get_sentiment_signal()

        # ASSERT
        assert sentiment == "NEUTRAL"

    def test_is_contrarian_signal_extreme_fear(self):
        """Test contrarian buy signal on extreme fear (PCR > 1.5)."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=200,
            call_volume=100,
            put_call_ratio=2.0,  # Extreme fear
            put_open_interest=2000,
            call_open_interest=1000,
            total_open_interest=3000
        )

        # ACT
        signal = snapshot.is_contrarian_signal()

        # ASSERT
        assert signal == "BUY"

    def test_is_contrarian_signal_extreme_greed(self):
        """Test contrarian sell signal on extreme greed (PCR < 0.4)."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=50,
            call_volume=200,
            put_call_ratio=0.25,  # Extreme greed
            put_open_interest=500,
            call_open_interest=2000,
            total_open_interest=2500
        )

        # ACT
        signal = snapshot.is_contrarian_signal()

        # ASSERT
        assert signal == "SELL"

    def test_is_contrarian_signal_none(self):
        """Test no contrarian signal in normal conditions."""
        # ARRANGE
        snapshot = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=100,
            call_volume=100,
            put_call_ratio=1.0,
            put_open_interest=1000,
            call_open_interest=1000,
            total_open_interest=2000
        )

        # ACT
        signal = snapshot.is_contrarian_signal()

        # ASSERT
        assert signal is None


class TestLevel2Snapshot:
    """Test Level 2 order book snapshot."""

    def _create_test_snapshot(self) -> Level2Snapshot:
        """Helper to create test L2 snapshot."""
        bids = [
            OrderBookLevel(price=100.0, quantity=10.0, order_count=5),
            OrderBookLevel(price=99.5, quantity=15.0, order_count=7),
            OrderBookLevel(price=99.0, quantity=20.0, order_count=10),
        ]
        asks = [
            OrderBookLevel(price=100.5, quantity=12.0, order_count=6),
            OrderBookLevel(price=101.0, quantity=18.0, order_count=8),
            OrderBookLevel(price=101.5, quantity=25.0, order_count=12),
        ]
        return Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

    def test_get_best_bid(self):
        """Test getting best bid price."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        best_bid = snapshot.get_best_bid()

        # ASSERT
        assert best_bid == 100.0

    def test_get_best_ask(self):
        """Test getting best ask price."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        best_ask = snapshot.get_best_ask()

        # ASSERT
        assert best_ask == 100.5

    def test_get_spread(self):
        """Test calculating bid-ask spread."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        spread = snapshot.get_spread()

        # ASSERT
        assert spread == 0.5

    def test_get_spread_percentage(self):
        """Test calculating spread as percentage."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        spread_pct = snapshot.get_spread_percentage()

        # ASSERT
        # Mid price = (100 + 100.5) / 2 = 100.25
        # Spread = 0.5 / 100.25 * 100 = 0.499%
        assert abs(spread_pct - 0.499) < 0.01

    def test_get_total_bid_volume(self):
        """Test calculating total bid volume."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        bid_volume = snapshot.get_total_bid_volume(depth=3)

        # ASSERT
        assert bid_volume == 45.0  # 10 + 15 + 20

    def test_get_total_ask_volume(self):
        """Test calculating total ask volume."""
        # ARRANGE
        snapshot = self._create_test_snapshot()

        # ACT
        ask_volume = snapshot.get_total_ask_volume(depth=3)

        # ASSERT
        assert ask_volume == 55.0  # 12 + 18 + 25

    def test_get_order_book_imbalance_buying_pressure(self):
        """Test order book imbalance with buying pressure."""
        # ARRANGE
        bids = [OrderBookLevel(price=100.0, quantity=100.0, order_count=10)]
        asks = [OrderBookLevel(price=101.0, quantity=50.0, order_count=5)]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        imbalance = snapshot.get_order_book_imbalance(depth=1)

        # ASSERT
        # (100 - 50) / (100 + 50) = 50 / 150 = 0.333
        assert abs(imbalance - 0.333) < 0.01

    def test_get_order_book_imbalance_selling_pressure(self):
        """Test order book imbalance with selling pressure."""
        # ARRANGE
        bids = [OrderBookLevel(price=100.0, quantity=30.0, order_count=3)]
        asks = [OrderBookLevel(price=101.0, quantity=70.0, order_count=7)]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        imbalance = snapshot.get_order_book_imbalance(depth=1)

        # ASSERT
        # (30 - 70) / (30 + 70) = -40 / 100 = -0.4
        assert abs(imbalance - (-0.4)) < 0.01

    def test_detect_walls_buy_wall(self):
        """Test detecting large buy wall."""
        # ARRANGE
        # Create realistic order book with one large wall
        bids = [
            OrderBookLevel(price=100.0, quantity=10.0, order_count=5),
            OrderBookLevel(price=99.5, quantity=100.0, order_count=1),  # Wall
            OrderBookLevel(price=99.0, quantity=12.0, order_count=7),
            OrderBookLevel(price=98.5, quantity=8.0, order_count=3),
            OrderBookLevel(price=98.0, quantity=15.0, order_count=6),
        ]
        asks = [
            OrderBookLevel(price=101.0, quantity=11.0, order_count=6),
            OrderBookLevel(price=101.5, quantity=9.0, order_count=4),
            OrderBookLevel(price=102.0, quantity=13.0, order_count=5),
        ]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        walls = snapshot.detect_walls(threshold_multiplier=3.0)

        # ASSERT
        # Avg size ≈ 22 (176/8), threshold ≈ 66, only 100 should qualify
        assert len(walls["buy_walls"]) == 1
        assert walls["buy_walls"][0].price == 99.5
        assert walls["buy_walls"][0].quantity == 100.0

    def test_detect_walls_sell_wall(self):
        """Test detecting large sell wall."""
        # ARRANGE
        # Create realistic order book with one large wall
        bids = [
            OrderBookLevel(price=100.0, quantity=10.0, order_count=5),
            OrderBookLevel(price=99.5, quantity=12.0, order_count=4),
            OrderBookLevel(price=99.0, quantity=9.0, order_count=3),
        ]
        asks = [
            OrderBookLevel(price=101.0, quantity=11.0, order_count=6),
            OrderBookLevel(price=101.5, quantity=150.0, order_count=2),  # Wall
            OrderBookLevel(price=102.0, quantity=13.0, order_count=5),
            OrderBookLevel(price=102.5, quantity=8.0, order_count=2),
            OrderBookLevel(price=103.0, quantity=14.0, order_count=4),
        ]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        walls = snapshot.detect_walls(threshold_multiplier=3.0)

        # ASSERT
        # Avg size ≈ 28 (227/8), threshold ≈ 84, only 150 should qualify
        assert len(walls["sell_walls"]) == 1
        assert walls["sell_walls"][0].price == 101.5

    def test_get_liquidity_score_high(self):
        """Test liquidity score for liquid market."""
        # ARRANGE
        # Tight spread, good depth, balanced
        bids = [
            OrderBookLevel(price=100.0, quantity=500.0, order_count=50),
            OrderBookLevel(price=99.9, quantity=500.0, order_count=50),
        ]
        asks = [
            OrderBookLevel(price=100.1, quantity=500.0, order_count=50),
            OrderBookLevel(price=100.2, quantity=500.0, order_count=50),
        ]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        score = snapshot.get_liquidity_score()

        # ASSERT
        assert score > 80  # Should be high liquidity

    def test_get_liquidity_score_low(self):
        """Test liquidity score for illiquid market."""
        # ARRANGE
        # Wide spread, shallow depth, imbalanced
        bids = [
            OrderBookLevel(price=100.0, quantity=5.0, order_count=1),
        ]
        asks = [
            OrderBookLevel(price=105.0, quantity=50.0, order_count=1),
        ]
        snapshot = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        # ACT
        score = snapshot.get_liquidity_score()

        # ASSERT
        assert score < 30  # Should be low liquidity


class TestMarketMicrostructure:
    """Test combined microstructure data."""

    def test_get_confirmation_signal_bullish_confirmed(self):
        """Test bullish confirmation with aligned signals."""
        # ARRANGE
        options_data = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=50,
            call_volume=150,
            put_call_ratio=0.33,  # Bullish
            put_open_interest=500,
            call_open_interest=1500,
            total_open_interest=2000
        )

        # Create liquid order book with buying pressure
        bids = [
            OrderBookLevel(price=100.0, quantity=600.0, order_count=50),
            OrderBookLevel(price=99.9, quantity=500.0, order_count=40),
        ]
        asks = [
            OrderBookLevel(price=100.1, quantity=300.0, order_count=30),
            OrderBookLevel(price=100.2, quantity=200.0, order_count=20),
        ]
        l2_data = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        micro = MarketMicrostructure(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            options_data=options_data,
            l2_data=l2_data
        )

        # ACT
        result = micro.get_confirmation_signal()

        # ASSERT
        assert result["has_confirmation"] is True
        assert result["sentiment"] == "BULLISH"
        assert result["liquidity_adequate"] is True
        assert any("Bullish confirmation" in s for s in result["signals"])

    def test_get_confirmation_signal_bearish_confirmed(self):
        """Test bearish confirmation with aligned signals."""
        # ARRANGE
        options_data = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=150,
            call_volume=50,
            put_call_ratio=3.0,  # Bearish
            put_open_interest=1500,
            call_open_interest=500,
            total_open_interest=2000
        )

        # Create liquid order book with selling pressure
        bids = [
            OrderBookLevel(price=100.0, quantity=200.0, order_count=20),
            OrderBookLevel(price=99.9, quantity=300.0, order_count=30),
        ]
        asks = [
            OrderBookLevel(price=100.1, quantity=500.0, order_count=40),
            OrderBookLevel(price=100.2, quantity=600.0, order_count=50),
        ]
        l2_data = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        micro = MarketMicrostructure(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            options_data=options_data,
            l2_data=l2_data
        )

        # ACT
        result = micro.get_confirmation_signal()

        # ASSERT
        assert result["has_confirmation"] is True
        assert result["sentiment"] == "BEARISH"
        assert result["liquidity_adequate"] is True
        assert any("Bearish confirmation" in s for s in result["signals"])

    def test_get_confirmation_signal_no_confirmation(self):
        """Test no confirmation when signals conflict."""
        # ARRANGE
        options_data = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=150,
            call_volume=50,
            put_call_ratio=3.0,  # Bearish
            put_open_interest=1500,
            call_open_interest=500,
            total_open_interest=2000
        )

        # But L2 shows buying pressure (conflict)
        bids = [OrderBookLevel(price=100.0, quantity=100.0, order_count=10)]
        asks = [OrderBookLevel(price=101.0, quantity=30.0, order_count=3)]
        l2_data = Level2Snapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )

        micro = MarketMicrostructure(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            options_data=options_data,
            l2_data=l2_data
        )

        # ACT
        result = micro.get_confirmation_signal()

        # ASSERT
        assert result["has_confirmation"] is False
        assert result["sentiment"] == "BEARISH"
        # Imbalance is positive (bullish) conflicting with bearish sentiment

    def test_get_confirmation_signal_only_options(self):
        """Test confirmation with only options data."""
        # ARRANGE
        options_data = OptionsSnapshot(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            put_volume=50,
            call_volume=150,
            put_call_ratio=0.33,
            put_open_interest=500,
            call_open_interest=1500,
            total_open_interest=2000
        )

        micro = MarketMicrostructure(
            symbol="BTC",
            timestamp=datetime.now(timezone.utc),
            options_data=options_data,
            l2_data=None
        )

        # ACT
        result = micro.get_confirmation_signal()

        # ASSERT
        assert result["sentiment"] == "BULLISH"
        assert "PCR" in result["signals"][0]
        # Can't have full confirmation without L2
        assert result["has_confirmation"] is False
